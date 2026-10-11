
"""
Weather forecast services for Spotter Routing.
"""

import logging
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry


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


class WeatherError(Exception):
    pass


def fetch_weather(latitude, longitude):
    """
    Fetch hourly weather data from Open-Meteo.

    Retries temporary server errors and rate limits.
    Logs the underlying failure for debugging.
    """

    session = requests.Session()

    retries = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)

    try:
        response = session.get(
            OPEN_METEO_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": ",".join(HOURLY_FIELDS),
                "wind_speed_unit": "mph",
                "temperature_unit": "fahrenheit",
                "precipitation_unit": "inch",
                "timezone": "UTC",
                "forecast_days": 3,
            },
            timeout=(10, 25),
            headers={
                "User-Agent": "SpotterRouting/1.0",
                "Accept": "application/json",
            },
        )

        if not response.ok:
            logger.error(
                "Open-Meteo HTTP %s: %s",
                response.status_code,
                response.text[:500],
            )

        response.raise_for_status()
        data = response.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            raise WeatherError(
                "Weather provider returned no hourly forecasts."
            )

        for field in HOURLY_FIELDS:
            values = hourly.get(field)

            if not isinstance(values, list):
                raise WeatherError(
                    f"Weather provider omitted field: {field}"
                )

            if len(values) != len(times):
                raise WeatherError(
                    f"Weather provider returned incomplete field: {field}"
                )

        return hourly

    except (RequestException, ValueError) as exc:
        logger.exception(
            "Open-Meteo request failed for latitude=%s longitude=%s",
            latitude,
            longitude,
        )

        raise WeatherError(
            "Unable to retrieve weather forecast."
        ) from exc

    finally:
        session.close()


def parse_forecast_time(value):
    return datetime.fromisoformat(value).replace(
        tzinfo=timezone.utc
    )


def format_weather(hourly, index, forecast_time):
    return {
        "forecast_time": forecast_time.isoformat(),
        "temperature_f": hourly["temperature_2m"][index],
        "precipitation_inches": hourly["precipitation"][index],
        "rain_inches": hourly["rain"][index],
        "snowfall_cm": hourly["snowfall"][index],
        "wind_speed_mph": hourly["wind_speed_10m"][index],
        "wind_gusts_mph": hourly["wind_gusts_10m"][index],
        "weather_code": hourly["weather_code"][index],
    }


def get_checkpoint_weather(
    latitude,
    longitude,
    arrival_time,
):
    """
    Retrieve forecast weather at a checkpoint's arrival time.
    """

    if arrival_time.tzinfo is None:
        raise WeatherError(
            "Arrival time must include timezone information."
        )

    hourly = fetch_weather(latitude, longitude)

    forecast_times = [
        parse_forecast_time(value)
        for value in hourly["time"]
    ]

    target_time = arrival_time.astimezone(timezone.utc)

    nearest_index = min(
        range(len(forecast_times)),
        key=lambda index: abs(
            forecast_times[index] - target_time
        ),
    )

    nearest_time = forecast_times[nearest_index]

    if abs(nearest_time - target_time) > timedelta(hours=1):
        raise WeatherError(
            "Weather forecast is unavailable for the requested arrival time."
        )

    return format_weather(
        hourly,
        nearest_index,
        nearest_time,
    )


def get_48_hour_forecast(latitude, longitude):
    """
    Retrieve the next 48 hourly forecasts in UTC.
    """

    hourly = fetch_weather(latitude, longitude)

    now = datetime.now(timezone.utc)

    forecasts = []

    for index, value in enumerate(hourly["time"]):
        forecast_time = parse_forecast_time(value)

        if forecast_time < now:
            continue

        forecasts.append(
            format_weather(hourly, index, forecast_time)
        )

        if len(forecasts) == 48:
            break

    if len(forecasts) < 48:
        raise WeatherError(
            "The forecast provider returned fewer than 48 future hours."
        )

    return forecasts
