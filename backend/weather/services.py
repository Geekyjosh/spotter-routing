
cat > backend/weather/services.py <<'PY'
import logging
from datetime import datetime, timezone

import requests
from django.core.cache import cache
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_FIELDS = [
    "temperature_2m",
    "precipitation",
    "rain",
    "snowfall",
    "wind_speed_10m",
    "wind_gusts_10m",
    "weather_code",
]

CACHE_SECONDS = 900
BATCH_SIZE = 20


class WeatherError(Exception):
    pass


def fetch_weather_batch(coordinates):
    """
    Coordinates are (latitude, longitude) pairs.
    Returns forecast datasets in the same order.
    """
    if not coordinates:
        return []

    results = [None] * len(coordinates)
    missing = []

    for index, (latitude, longitude) in enumerate(coordinates):
        key = f"spotter_weather_v2:{latitude:.5f}:{longitude:.5f}"
        cached = cache.get(key)

        if cached is not None:
            results[index] = cached
        else:
            missing.append((index, latitude, longitude, key))

    for start in range(0, len(missing), BATCH_SIZE):
        batch = missing[start:start + BATCH_SIZE]

        params = {
            "latitude": ",".join(str(item[1]) for item in batch),
            "longitude": ",".join(str(item[2]) for item in batch),
            "hourly": ",".join(HOURLY_FIELDS),
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "inch",
            "timezone": "UTC",
            "forecast_days": 3,
        }

        try:
            response = requests.get(
                OPEN_METEO_URL,
                params=params,
                timeout=30,
            )

            if response.status_code == 429:
                logger.warning("Open-Meteo rate limit (HTTP 429)")
                raise WeatherError(
                    "Weather provider rate limit reached."
                )

            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, dict):
                payload = [payload]

            if not isinstance(payload, list) or len(payload) != len(batch):
                raise WeatherError(
                    "Unexpected weather provider response."
                )

            for item, dataset in zip(batch, payload):
                index, latitude, longitude, key = item

                if not isinstance(dataset, dict) or not isinstance(
                    dataset.get("hourly"), dict
                ):
                    raise WeatherError(
                        "Incomplete weather forecast response."
                    )

                results[index] = dataset
                cache.set(key, dataset, CACHE_SECONDS)

        except WeatherError:
            raise
        except (RequestException, ValueError, TypeError) as exc:
            logger.warning("Weather request failed: %s", exc)
            raise WeatherError(
                "Unable to retrieve weather forecast."
            ) from exc

    return results


def fetch_weather(latitude, longitude):
    return fetch_weather_batch([(latitude, longitude)])[0]


def forecast_at_arrival(dataset, arrival_time):
    hourly = dataset["hourly"]
    times = hourly["time"]

    if not times:
        raise WeatherError("No forecast hours available.")

    if arrival_time.tzinfo is None:
        raise WeatherError("Arrival time must include a timezone.")

    target = arrival_time.astimezone(timezone.utc).replace(tzinfo=None)

    parsed_times = [datetime.fromisoformat(value) for value in times]

    closest_index = min(
        range(len(parsed_times)),
        key=lambda index: abs(
            (parsed_times[index] - target).total_seconds()
        ),
    )

    # Do not silently use stale forecasts for distant dates.
    if abs(
        (parsed_times[closest_index] - target).total_seconds()
    ) > 3600:
        raise WeatherError(
            "Arrival time is outside the available forecast."
        )

    def field(name):
        values = hourly.get(name, [])
        return values[closest_index] if closest_index < len(values) else None

    return {
        "forecast_time": times[closest_index],
        "temperature_f": field("temperature_2m"),
        "precipitation_inches": field("precipitation"),
        "rain_inches": field("rain"),
        "snowfall_cm": field("snowfall"),
        "wind_speed_mph": field("wind_speed_10m"),
        "wind_gusts_mph": field("wind_gusts_10m"),
        "weather_code": field("weather_code"),
    }


def get_checkpoint_weather(latitude, longitude, arrival_time):
    dataset = fetch_weather(latitude, longitude)
    return forecast_at_arrival(dataset, arrival_time)


def get_48_hour_forecast(latitude, longitude):
    dataset = fetch_weather(latitude, longitude)
    hourly = dataset["hourly"]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    forecasts = []

    for time_string in hourly.get("time", []):
        forecast_time = datetime.fromisoformat(time_string)

        if forecast_time <= now:
            continue

        forecasts.append(
            forecast_at_arrival(
                dataset,
                forecast_time.replace(tzinfo=timezone.utc),
            )
        )

        if len(forecasts) == 48:
            break

    return forecasts
PY
