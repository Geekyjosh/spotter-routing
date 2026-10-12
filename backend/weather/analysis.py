
from datetime import datetime

from .services import (
    WeatherError,
    fetch_weather_batch,
    forecast_at_arrival,
)


def enrich_routes_with_weather(routes):
    """
    Fetch weather for all checkpoints in batches,
    preserving route order.
    """

    checkpoints = [
        checkpoint
        for route in routes
        for checkpoint in route.get("checkpoints", [])
    ]

    coordinates = [
        (
            checkpoint["coordinates"][1],
            checkpoint["coordinates"][0],
        )
        for checkpoint in checkpoints
    ]

    unique_coordinates = list(
        dict.fromkeys(coordinates)
    )

    try:
        datasets = fetch_weather_batch(
            unique_coordinates
        )

        forecast_lookup = dict(
            zip(unique_coordinates, datasets)
        )

        batch_error = None

    except WeatherError as exc:
        forecast_lookup = {}
        batch_error = str(exc)

    for checkpoint, coordinate in zip(
        checkpoints,
        coordinates,
    ):
        try:
            if batch_error:
                raise WeatherError(batch_error)

            arrival = datetime.fromisoformat(
                checkpoint["estimated_arrival"]
            )

            checkpoint["weather"] = forecast_at_arrival(
                forecast_lookup[coordinate],
                arrival,
            )

            checkpoint["weather_status"] = "available"
            checkpoint.pop("weather_error", None)

        except (
            WeatherError,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            checkpoint["weather"] = None
            checkpoint["weather_status"] = "unavailable"
            checkpoint["weather_error"] = str(exc)

    for route in routes:
        items = route.get("checkpoints", [])

        route["weather_checkpoints_available"] = sum(
            item.get("weather_status") == "available"
            for item in items
        )

        route["weather_checkpoints_unavailable"] = sum(
            item.get("weather_status") == "unavailable"
            for item in items
        )

    return routes
