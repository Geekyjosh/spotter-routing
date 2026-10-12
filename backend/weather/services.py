
import logging
from datetime import datetime, timedelta, timezone

import requests
from django.core.cache import cache
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_FIELDS = (
    "temperature_2m",
    "precipitation",
    "rain",
    "snowfall",
    "wind_speed_10m",
    "wind_gusts_10m",
    "weather_code",
)

BATCH_SIZE = 20
CACHE_SECONDS = 900


class WeatherError(Exception):
    pass


def _cache_key(latitude, longitude):
    return f"spotter:weather:v3:{latitude:.6f}:{longitude:.6f}"


def fetch_weather_batch(coordinates):
    """
    Return Open-Meteo datasets in the same order
    as the supplied (latitude, longitude) pairs.
    """
    if not coordinates:
        return []

    results = [None] * len(coordinates)
    missing = []

    for index, (latitude, longitude) in enumerate(coordinates):
        key = _cache_key(latitude, longitude)
        cached = cache.get(key)

        if cached is None:
            missing.append((index, latitude, longitude, key))
        else:
            results[index] = cached

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
                logger.warning(
                    "Open-Meteo returned HTTP 429 (rate limited)"
                )
                raise WeatherError(
                    "Weather provider rate limit reached."
                )

            response.raise_for_status()
            payload = response.json()

        except WeatherError:
            raise

        except (RequestException, ValueError) as exc:
            logger.warning(
                "Open-Meteo request failed: %s", exc
            )
            raise WeatherError(
                "Unable to retrieve weather forecast."
            ) from exc

        # Single-coordinate responses are dictionaries.
        # Multi-coordinate responses are lists.
        datasets = (
            [payload]
            if isinstance(payload, dict)
            else payload
        )

        if (
            not isinstance(datasets, list)
            or len(datasets) != len(batch)
        ):
            raise WeatherError(
                "Unexpected weather provider response."
            )

        for (
            index,
            latitude,
            longitude,
            key,
        ), dataset in zip(batch, datasets):

            if (
                not isinstance(dataset, dict)
                or not isinstance(dataset.get("hourly"), dict)
            ):
                raise WeatherError(
                    "Weather provider returned incomplete hourly data."
                )

            results[index] = dataset
            cache.set(key, dataset, CACHE_SECONDS)

    return results


def fetch_weather(latitude, longitude):
    return fetch_weather_batch(
        [(latitude, longitude)]
    )[0]


def _forecast_row(hourly, index):
    def value(field):
        values = hourly.get(field) or []
        return (
            values[index]
            if index < len(values)
            else None
        )

    return {
        "forecast_time": (
            datetime.fromisoformat(
                hourly["time"][index]
            )
            .replace(tzinfo=timezone.utc)
            .isoformat()
        ),
        "temperature_f": value("temperature_2m"),
        "precipitation_inches": value("precipitation"),
        "rain_inches": value("rain"),
        "snowfall_cm": value("snowfall"),
        "wind_speed_mph": value("wind_speed_10m"),
        "wind_gusts_mph": value("wind_gusts_10m"),
        "weather_code": value("weather_code"),
    }


def forecast_at_arrival(dataset, arrival_time):
    if arrival_time.tzinfo is None:
        raise WeatherError(
            "Arrival time must include timezone information."
        )

    hourly = dataset.get("hourly") or {}
    times = hourly.get("time") or []

    if not times:
        raise WeatherError(
            "Weather forecast contains no hourly data."
        )

    target = (
        arrival_time
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    try:
        parsed = [
            datetime.fromisoformat(t)
            for t in times
        ]

        nearest = min(
            range(len(parsed)),
            key=lambda i: abs(parsed[i] - target),
        )

    except (TypeError, ValueError) as exc:
        raise WeatherError(
            "Weather provider returned invalid forecast times."
        ) from exc

    if abs(parsed[nearest] - target) > timedelta(hours=1):
        raise WeatherError(
            "Weather forecast is unavailable for the requested arrival time."
        )

    return _forecast_row(hourly, nearest)


def get_checkpoint_weather(
    latitude,
    longitude,
    arrival_time,
):
    return forecast_at_arrival(
        fetch_weather(latitude, longitude),
        arrival_time,
    )


def get_48_hour_forecast(latitude, longitude):
    hourly = (
        fetch_weather(latitude, longitude)
        .get("hourly") or {}
    )

    times = hourly.get("time") or []

    now = (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )

    forecasts = []

    for index, value in enumerate(times):
        if datetime.fromisoformat(value) < now:
            continue

        forecasts.append(
            _forecast_row(hourly, index)
        )

        if len(forecasts) == 48:
            break

    if len(forecasts) < 48:
        raise WeatherError(
            "The forecast provider returned fewer than 48 future hours."
        )

    return forecasts
