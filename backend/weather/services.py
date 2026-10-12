
import logging
import os
from datetime import datetime, timedelta, timezone

import requests
from django.core.cache import cache
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

OPENWEATHER_URL = (
    "https://api.openweathermap.org/data/2.5/forecast"
)
CACHE_SECONDS = 1800


class WeatherError(Exception):
    pass


def _cache_key(latitude, longitude):
    return (
        f"spotter:openweather:v1:"
        f"{float(latitude):.3f}:{float(longitude):.3f}"
    )


def _weather_code(openweather_id):
    """Convert OpenWeatherMap condition IDs to WMO codes."""
    if openweather_id is None:
        return None

    code = int(openweather_id)

    if 200 <= code < 300:
        return 95
    if 300 <= code < 400:
        return 51
    if 500 <= code < 600:
        return 65 if code >= 502 else 61
    if 600 <= code < 700:
        return 75 if code >= 602 else 71
    if 700 <= code < 800:
        return 45
    if code == 800:
        return 0
    if code == 801:
        return 1
    if code == 802:
        return 2
    if code in (803, 804):
        return 3

    return 3


def fetch_weather(latitude, longitude):
    latitude = float(latitude)
    longitude = float(longitude)

    key = os.getenv("OPENWEATHER_API_KEY")

    if not key:
        raise WeatherError(
            "OPENWEATHER_API_KEY is not configured."
        )

    cache_key = _cache_key(latitude, longitude)
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    try:
        response = requests.get(
            OPENWEATHER_URL,
            params={
                "lat": latitude,
                "lon": longitude,
                "appid": key,
                "units": "metric",
            },
            timeout=20,
        )

        if response.status_code == 401:
            raise WeatherError(
                "OpenWeatherMap API key is invalid or not active."
            )

        if response.status_code == 403:
            raise WeatherError(
                "OpenWeatherMap access denied. Check your plan."
            )

        if response.status_code == 429:
            raise WeatherError(
                "OpenWeatherMap rate limit reached."
            )

        response.raise_for_status()
        data = response.json()

        if not isinstance(data.get("list"), list):
            raise WeatherError(
                "OpenWeatherMap returned invalid forecast data."
            )

        cache.set(cache_key, data, CACHE_SECONDS)
        return data

    except WeatherError:
        raise

    except (RequestException, ValueError) as exc:
        logger.warning(
            "OpenWeatherMap request failed: %s", exc
        )
        raise WeatherError(
            "Unable to retrieve weather forecast."
        ) from exc


def fetch_weather_batch(coordinates):
    """
    Fetch forecasts for multiple locations.
    OpenWeatherMap's standard forecast API
    requires a separate request per location.
    """
    return [
        fetch_weather(latitude, longitude)
        for latitude, longitude in coordinates
    ]


def _forecast_row(item):
    main = item.get("main") or {}
    wind = item.get("wind") or {}
    rain = item.get("rain") or {}
    snow = item.get("snow") or {}
    weather = item.get("weather") or []

    condition = weather[0] if weather else {}

    # OpenWeatherMap metric values:
    # temperature: Celsius
    # wind: metres/second
    # rain and snow: millimetres per 3-hour period

    temperature = main.get("temp")
    wind_speed = wind.get("speed")
    wind_gust = wind.get("gust")

    rain_mm = rain.get("3h", 0)
    snow_mm = snow.get("3h", 0)

    return {
        "forecast_time": datetime.fromtimestamp(
            item["dt"],
            tz=timezone.utc,
        ).isoformat(),
        "temperature_f": (
            round(temperature * 9 / 5 + 32, 1)
            if temperature is not None
            else None
        ),
        "precipitation_inches": round(
            (rain_mm + snow_mm) / 25.4, 3
        ),
        "rain_inches": round(rain_mm / 25.4, 3),
        "snowfall_cm": round(snow_mm / 10, 2),
        "wind_speed_mph": (
            round(wind_speed * 2.23694, 1)
            if wind_speed is not None
            else None
        ),
        "wind_gusts_mph": (
            round(wind_gust * 2.23694, 1)
            if wind_gust is not None
            else None
        ),
        "weather_code": _weather_code(
            condition.get("id")
        ),
    }


def forecast_at_arrival(dataset, arrival_time):
    if arrival_time.tzinfo is None:
        raise WeatherError(
            "Arrival time must include timezone information."
        )

    entries = dataset.get("list") or []

    if not entries:
        raise WeatherError(
            "No forecast data available."
        )

    target = arrival_time.astimezone(timezone.utc)
    nearest = min(
        entries,
        key=lambda item: abs(
            datetime.fromtimestamp(
                item["dt"],
                tz=timezone.utc,
            ) - target
        ),
    )

    difference = abs(
        datetime.fromtimestamp(
            nearest["dt"],
            tz=timezone.utc,
        ) - target
    )

    if difference > timedelta(hours=2):
        raise WeatherError(
            "No forecast available near the arrival time."
        )

    return _forecast_row(nearest)


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
    """
    Return forecast periods covering the next 48 hours.
    Data is available every 3 hours, not hourly.
    """
    dataset = fetch_weather(latitude, longitude)
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=48)

    forecasts = []

    for item in dataset.get("list", []):
        forecast_time = datetime.fromtimestamp(
            item["dt"],
            tz=timezone.utc,
        )

        if now <= forecast_time <= end:
            forecasts.append(_forecast_row(item))

    if not forecasts:
        raise WeatherError(
            "No forecasts available for the next 48 hours."
        )

    return forecasts
