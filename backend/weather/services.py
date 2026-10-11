
from datetime import datetime, timezone, timedelta

import requests
from requests.exceptions import RequestException


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherError(Exception):
    pass


def get_checkpoint_weather(
    latitude,
    longitude,
    arrival_time,
):
    """
    Retrieve forecast weather for a route checkpoint
    at the estimated arrival time.

    Coordinates are latitude, longitude.
    Arrival time must be timezone-aware.
    """

    if arrival_time.tzinfo is None:
        raise WeatherError(
            "Arrival time must include timezone information."
        )

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": (
                    "temperature_2m,"
                    "precipitation,"
                    "rain,"
                    "snowfall,"
                    "wind_speed_10m,"
                    "wind_gusts_10m,"
                    "weather_code"
                ),
                "wind_speed_unit": "mph",
                "temperature_unit": "fahrenheit",
                "precipitation_unit": "inch",
                "timezone": "UTC",
                "forecast_days": 3,
            },
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

    except (RequestException, ValueError) as exc:
        raise WeatherError(
            "Unable to retrieve weather forecast."
        ) from exc

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    if not times:
        raise WeatherError(
            "Weather forecast contains no hourly data."
        )

    target_time = arrival_time.astimezone(
        timezone.utc
    )

    forecast_times = [
        datetime.fromisoformat(
            value
        ).replace(tzinfo=timezone.utc)
        for value in times
    ]

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

    return {
        "forecast_time": nearest_time.isoformat(),
        "temperature_f": hourly["temperature_2m"][nearest_index],
        "precipitation_inches": hourly["precipitation"][nearest_index],
        "rain_inches": hourly["rain"][nearest_index],
        "snowfall_cm": hourly["snowfall"][nearest_index],
        "wind_speed_mph": hourly["wind_speed_10m"][nearest_index],
        "wind_gusts_mph": hourly["wind_gusts_10m"][nearest_index],
        "weather_code": hourly["weather_code"][nearest_index],
    }

def get_48_hour_forecast(latitude, longitude):
    """
    Retrieve the next 48 hourly weather forecasts
    for a specific geographic location.

    Returns hourly data in UTC.
    """

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": (
                    "temperature_2m,"
                    "precipitation,"
                    "rain,"
                    "snowfall,"
                    "wind_speed_10m,"
                    "wind_gusts_10m,"
                    "weather_code"
                ),
                "wind_speed_unit": "mph",
                "temperature_unit": "fahrenheit",
                "precipitation_unit": "inch",
                "timezone": "UTC",
                "forecast_days": 3,
            },
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

    except (RequestException, ValueError) as exc:
        raise WeatherError(
            "Unable to retrieve 48-hour weather forecast."
        ) from exc

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    if not times:
        raise WeatherError(
            "Weather forecast contains no hourly data."
        )

    now = datetime.now(timezone.utc)

    forecasts = []

    for index, value in enumerate(times):
        forecast_time = datetime.fromisoformat(
            value
        ).replace(tzinfo=timezone.utc)

        if forecast_time < now:
            continue

        forecasts.append({
            "forecast_time": forecast_time.isoformat(),
            "temperature_f": hourly["temperature_2m"][index],
            "precipitation_inches": hourly["precipitation"][index],
            "rain_inches": hourly["rain"][index],
            "snowfall_cm": hourly["snowfall"][index],
            "wind_speed_mph": hourly["wind_speed_10m"][index],
            "wind_gusts_mph": hourly["wind_gusts_10m"][index],
            "weather_code": hourly["weather_code"][index],
        })

        if len(forecasts) == 48:
            break

    if len(forecasts) < 48:
        raise WeatherError(
            "The forecast provider returned fewer than 48 future hours."
        )

    return forecasts
