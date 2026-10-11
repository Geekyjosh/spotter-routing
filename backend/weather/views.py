
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .services import WeatherError, get_48_hour_forecast


@require_GET
def hourly_forecast(request):
    """
    Return 48 hours of hourly weather forecasts
    for the requested latitude and longitude.
    """

    try:
        latitude = float(request.GET["latitude"])
        longitude = float(request.GET["longitude"])
    except KeyError:
        return JsonResponse(
            {
                "error": "Latitude and longitude are required."
            },
            status=400,
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {
                "error": "Latitude and longitude must be valid numbers."
            },
            status=400,
        )

    if not (-90 <= latitude <= 90):
        return JsonResponse(
            {"error": "Latitude must be between -90 and 90."},
            status=400,
        )

    if not (-180 <= longitude <= 180):
        return JsonResponse(
            {"error": "Longitude must be between -180 and 180."},
            status=400,
        )

    try:
        forecasts = get_48_hour_forecast(
            latitude,
            longitude,
        )
    except WeatherError as exc:
        return JsonResponse(
            {"error": str(exc)},
            status=503,
        )

    return JsonResponse(
        {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_hours": len(forecasts),
            "forecasts": forecasts,
        }
    )
