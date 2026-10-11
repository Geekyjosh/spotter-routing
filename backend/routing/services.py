
import math

import requests
from requests.exceptions import RequestException


class RoutingError(Exception):
    pass


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"

HEADERS = {
    "User-Agent": "SpotterRoutingAssessment/1.0 (development)",
    "Accept": "application/json",
}

METERS_PER_MILE = 1609.344
EARTH_RADIUS_MILES = 3958.7613


def geocode_location(location):
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": location,
                "format": "json",
                "limit": 1,
            },
            headers=HEADERS,
            timeout=20,
        )

        response.raise_for_status()
        results = response.json()

    except (RequestException, ValueError) as exc:
        print("GEOCODING ERROR:", repr(exc))
        raise RoutingError(
            "Unable to find the requested location."
        ) from exc

    if not results:
        raise RoutingError(
            f"No location found for: {location}"
        )

    result = results[0]

    return {
        "coordinates": [
            float(result["lon"]),
            float(result["lat"]),
        ],
        "label": result.get("display_name", location),
    }


def haversine_miles(point_a, point_b):
    """
    Calculate the approximate distance between two
    geographic coordinates.

    Coordinates use [longitude, latitude].
    """
    lon1, lat1 = map(math.radians, point_a)
    lon2, lat2 = map(math.radians, point_b)

    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1

    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    value = min(1.0, max(0.0, value))

    return (
        2
        * EARTH_RADIUS_MILES
        * math.asin(math.sqrt(value))
    )


def generate_checkpoints(geometry, interval_miles):
    """
    Generate checkpoints along a route's geometry.

    Includes the starting point, regular interval
    checkpoints, and the destination.
    """
    coordinates = geometry.get("coordinates", [])

    if not coordinates:
        return []

    interval_miles = float(interval_miles)

    if interval_miles <= 0:
        raise ValueError(
            "Checkpoint interval must be greater than zero."
        )

    checkpoints = [
        {
            "index": 0,
            "coordinates": coordinates[0],
            "distance_miles": 0.0,
        }
    ]

    if len(coordinates) == 1:
        return checkpoints

    distance_traveled = 0.0
    next_checkpoint = interval_miles

    for index in range(1, len(coordinates)):
        start = coordinates[index - 1]
        end = coordinates[index]

        segment_distance = haversine_miles(start, end)

        if segment_distance <= 0:
            continue

        segment_end_distance = (
            distance_traveled + segment_distance
        )

        while next_checkpoint <= segment_end_distance:
            fraction = (
                next_checkpoint - distance_traveled
            ) / segment_distance

            fraction = max(0.0, min(1.0, fraction))

            longitude = (
                start[0]
                + (end[0] - start[0]) * fraction
            )

            latitude = (
                start[1]
                + (end[1] - start[1]) * fraction
            )

            checkpoints.append({
                "index": len(checkpoints),
                "coordinates": [
                    round(longitude, 6),
                    round(latitude, 6),
                ],
                "distance_miles": round(
                    next_checkpoint, 2
                ),
            })

            next_checkpoint += interval_miles

        distance_traveled = segment_end_distance

    destination = coordinates[-1]

    if haversine_miles(
        checkpoints[-1]["coordinates"],
        destination,
    ) > 0.001:
        checkpoints.append({
            "index": len(checkpoints),
            "coordinates": destination,
            "distance_miles": round(
                distance_traveled, 2
            ),
        })

    return checkpoints


def get_alternative_routes(
    origin,
    destination,
    checkpoint_interval=25,
):
    origin_data = geocode_location(origin)
    destination_data = geocode_location(destination)

    start = origin_data["coordinates"]
    end = destination_data["coordinates"]

    coordinates = (
        f"{start[0]},{start[1]};"
        f"{end[0]},{end[1]}"
    )

    url = f"{OSRM_URL}/{coordinates}"

    try:
        response = requests.get(
            url,
            params={
                "overview": "full",
                "geometries": "geojson",
                "alternatives": "true",
                "steps": "false",
            },
            headers=HEADERS,
            timeout=45,
        )

        response.raise_for_status()
        data = response.json()

    except (RequestException, ValueError) as exc:
        print("OSRM ROUTING ERROR:", repr(exc))
        raise RoutingError(
            "Unable to retrieve routes from the routing provider."
        ) from exc

    if data.get("code") != "Ok":
        raise RoutingError(
            data.get(
                "message",
                "Routing request failed.",
            )
        )

    routes = []

    for index, route in enumerate(
        data.get("routes", [])
    ):
        geometry = route["geometry"]

        checkpoints = generate_checkpoints(
            geometry,
            checkpoint_interval,
        )

        routes.append({
            "id": f"route-{index + 1}",
            "name": f"Route {index + 1}",
            "distance_miles": round(
                route["distance"] / METERS_PER_MILE,
                2,
            ),
            "duration_minutes": round(
                route["duration"] / 60,
                1,
            ),
            "geometry": geometry,
            "checkpoints": checkpoints,
            "checkpoint_count": len(checkpoints),
        })

    if not routes:
        raise RoutingError(
            "No available driving routes were found."
        )

    return {
        "origin": origin_data,
        "destination": destination_data,
        "routes": routes,
        "route_count": len(routes),
        "routing_provider": "OSRM",
        "truck_restrictions_verified": False,
    }
