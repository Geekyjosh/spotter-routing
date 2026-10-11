
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .services import WeatherError, get_checkpoint_weather


MAX_WEATHER_WORKERS = 5


def fetch_checkpoint_forecast(checkpoint):
    """
    Fetch weather at a checkpoint's estimated arrival time.
    """
    longitude, latitude = checkpoint["coordinates"]

    arrival_time = datetime.fromisoformat(
        checkpoint["estimated_arrival"]
    )

    try:
        forecast = get_checkpoint_weather(
            latitude=latitude,
            longitude=longitude,
            arrival_time=arrival_time,
        )

        return {
            **checkpoint,
            "weather": forecast,
            "weather_status": "available",
        }

    except (WeatherError, ValueError, KeyError, TypeError) as exc:
        return {
            **checkpoint,
            "weather": None,
            "weather_status": "unavailable",
            "weather_error": str(exc),
        }


def enrich_routes_with_weather(routes):
    """
    Add weather forecasts to checkpoints on all routes.

    A bounded thread pool prevents unlimited
    simultaneous weather API requests.
    """
    tasks = {}
    results = {}

    with ThreadPoolExecutor(
        max_workers=MAX_WEATHER_WORKERS
    ) as executor:
        for route_index, route in enumerate(routes):
            for checkpoint_index, checkpoint in enumerate(
                route.get("checkpoints", [])
            ):
                future = executor.submit(
                    fetch_checkpoint_forecast,
                    checkpoint,
                )

                tasks[future] = (
                    route_index,
                    checkpoint_index,
                )

        for future in as_completed(tasks):
            route_index, checkpoint_index = tasks[future]

            results[
                (route_index, checkpoint_index)
            ] = future.result()

    for route_index, route in enumerate(routes):
        route["checkpoints"] = [
            results[(route_index, checkpoint_index)]
            for checkpoint_index in range(
                len(route.get("checkpoints", []))
            )
        ]

        route["weather_checkpoints_available"] = sum(
            checkpoint["weather_status"] == "available"
            for checkpoint in route["checkpoints"]
        )

        route["weather_checkpoints_unavailable"] = sum(
            checkpoint["weather_status"] == "unavailable"
            for checkpoint in route["checkpoints"]
        )

    return routes
