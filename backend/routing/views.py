
from datetime import timedelta

from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import RoutingError, get_alternative_routes
from weather.analysis import enrich_routes_with_weather
from weather.risk import score_routes
from .recommendations import recommend_safest_route

@api_view(["GET"])
def health_check(request):
    return Response({
        "status": "ok",
        "service": "Spotter Routing API",
        "version": "1.0.0",
    })


@api_view(["POST"])
def generate_routes(request):
    data = request.data

    if not isinstance(data, dict):
        return Response(
            {"error": "Request body must be a JSON object."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    origin = data.get("origin")
    destination = data.get("destination")
    departure_time = data.get("departureTime")
    load_weight = data.get("loadWeight")
    checkpoint_interval = data.get("checkpointInterval", 25)

    if not isinstance(origin, str) or not origin.strip():
        return Response(
            {"error": "A valid origin is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(destination, str) or not destination.strip():
        return Response(
            {"error": "A valid destination is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if origin.strip().casefold() == destination.strip().casefold():
        return Response(
            {"error": "Origin and destination must be different."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    parsed_departure = (
        parse_datetime(departure_time)
        if isinstance(departure_time, str)
        else None
    )

    if parsed_departure is None or parsed_departure.tzinfo is None:
        return Response(
            {
                "error": (
                    "departureTime must be a valid ISO 8601 "
                    "datetime with a timezone offset."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        weight = float(load_weight)

        if not (0 < weight < float("inf")):
            raise ValueError()

    except (TypeError, ValueError, OverflowError):
        return Response(
            {"error": "Load weight must be a positive finite number."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if (
        type(checkpoint_interval) is not int
        or checkpoint_interval not in (10, 25, 50)
    ):
        return Response(
            {
                "error": (
                    "Checkpoint interval must be "
                    "10, 25, or 50 miles."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = get_alternative_routes(
            origin.strip(),
            destination.strip(),
            checkpoint_interval=checkpoint_interval,
        )

    except RoutingError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # Calculate estimated arrival time for each checkpoint.
    for route in result["routes"]:
        route_distance = route["distance_miles"]
        route_duration = route["duration_minutes"]

        for checkpoint in route["checkpoints"]:
            if route_distance > 0:
                progress = min(
                    checkpoint["distance_miles"] / route_distance,
                    1.0,
                )
            else:
                progress = 0.0

            minutes_from_departure = (
                route_duration * progress
            )

            arrival_time = (
                parsed_departure
                + timedelta(minutes=minutes_from_departure)
            )

            checkpoint["estimated_arrival"] = (
                arrival_time.isoformat()
            )

    # Fetch forecast weather for every route checkpoint.
    result["routes"] = enrich_routes_with_weather(
        result["routes"]
    )
# Calculate weather risk scores for all routes.
    result["routes"] = score_routes(
    result["routes"],
    weight,
)
    recommendation = recommend_safest_route(
    result["routes"]
)
    available_count = sum(
        route["weather_checkpoints_available"]
        for route in result["routes"]
    )

    unavailable_count = sum(
        route["weather_checkpoints_unavailable"]
        for route in result["routes"]
    )

    if unavailable_count == 0:
        weather_status = "complete"
    elif available_count > 0:
        weather_status = "partial"
    else:
        weather_status = "unavailable"

    return Response({
        **result,
        "departure_time": parsed_departure.isoformat(),
        "load_weight_lbs": weight,
        "checkpoint_interval_miles": checkpoint_interval,
        "weather_analysis_status": weather_status,
        "recommendation_status": recommendation["status"],
        "recommendation": recommendation,
    })
