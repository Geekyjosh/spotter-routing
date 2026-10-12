
cat > backend/weather/analysis.py <<'PY'
from datetime import datetime

from .services import (
    WeatherError,
    fetch_weather_batch,
    forecast_at_arrival,
)


def enrich_routes_with_weather(routes):
    """
    Fetch checkpoint forecasts in batches instead of
    sending a separate request for each checkpoint.
    """
    checkpoints = []
    coordinates = []

    for route in routes:
        for checkpoint in route.get("checkpoints", []):
            checkpoints.append(checkpoint)

            longitude, latitude = checkpoint["coordinates"]
            coordinates.append((latitude, longitude))

    if not checkpoints:
        for route in routes:
            route["weather_checkpoints_available"] = 0
            route["weather_checkpoints_unavailable"] = 0
        return routes

    # Reuse forecasts for identical checkpoint coordinates.
    unique_coordinates = list(dict.fromkeys(coordinates))

    try:
        datasets = fetch_weather_batch(unique_coordinates)
        forecast_lookup = dict(zip(unique_coordinates, datasets))
        batch_error = None
    except WeatherError as exc:
        forecast_lookup = {}
        batch_error = str(exc)

    for checkpoint, coordinate in zip(checkpoints, coordinates):
        try:
            if batch_error:
                raise WeatherError(batch_error)

            arrival_time = datetime.fromisoformat(
                checkpoint["estimated_arrival"]
            )

            forecast = forecast_at_arrival(
                forecast_lookup[coordinate],
                arrival_time,
            )

            checkpoint["weather"] = forecast
            checkpoint["weather_status"] = "available"
            checkpoint.pop("weather_error", None)

        except (WeatherError, ValueError, KeyError, TypeError) as exc:
            checkpoint["weather"] = None
            checkpoint["weather_status"] = "unavailable"
            checkpoint["weather_error"] = str(exc)

    for route in routes:
        route_checkpoints = route.get("checkpoints", [])

        route["weather_checkpoints_available"] = sum(
            checkpoint["weather_status"] == "available"
            for checkpoint in route_checkpoints
        )

        route["weather_checkpoints_unavailable"] = sum(
            checkpoint["weather_status"] == "unavailable"
            for checkpoint in route_checkpoints
        )

    return routes
PY
