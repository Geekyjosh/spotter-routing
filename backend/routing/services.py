
import math
import logging

import requests
from requests.exceptions import RequestException


logger = logging.getLogger(__name__)


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


# Fallback coordinates for common assessment demo cities.
# Coordinate order: longitude, latitude.
KNOWN_LOCATIONS = {
    "new york": (-74.0060, 40.7128),
    "new york, ny": (-74.0060, 40.7128),
    "new york city": (-74.0060, 40.7128),
    "nyc": (-74.0060, 40.7128),

    "philadelphia": (-75.1652, 39.9526),
    "philadelphia, pa": (-75.1652, 39.9526),

    "boston": (-71.0589, 42.3601),
    "boston, ma": (-71.0589, 42.3601),

    "washington, dc": (-77.0369, 38.9072),
    "washington dc": (-77.0369, 38.9072),

    "chicago": (-87.6298, 41.8781),
    "chicago, il": (-87.6298, 41.8781),

    "los angeles": (-118.2437, 34.0522),
    "los angeles, ca": (-118.2437, 34.0522),

    "atlanta": (-84.3880, 33.7490),
    "atlanta, ga": (-84.3880, 33.7490),

    "dallas": (-96.7970, 32.7767),
    "dallas, tx": (-96.7970, 32.7767),

    "houston": (-95.3698, 29.7604),
    "houston, tx": (-95.3698, 29.7604),

    "miami": (-80.1918, 25.7617),
    "miami, fl": (-80.1918, 25.7617),

    "seattle": (-122.3321, 47.6062),
    "seattle, wa": (-122.3321, 47.6062),

    "denver": (-104.9903, 39.7392),
    "denver, co": (-104.9903, 39.7392),
}


def geocode_location(location):
    """
    Convert a location name into coordinates.

    Known demo cities use predefined coordinates.
    Other locations use OpenStreetMap Nominatim.
    """

    normalized = " ".join(
        location.strip().lower().split()
    )

    if normalized in KNOWN_LOCATIONS:
        longitude, latitude = KNOWN_LOCATIONS[normalized]

        return {
            "coordinates": [
                longitude,
                latitude,
            ],
            "label": location,
        }

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
        logger.warning(
            "Geocoding failed for %s: %s",
            location,
            exc,
        )

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
        "label": result.get(
            "display_name",
            location,
        ),
    }


def haversine_miles(point_a, point_b):
    """
    Calculate approximate distance between
    geographic coordinates.

    Coordinate order: [longitude, latitude].
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

    value = min(
        1.0,
        max(0.0, value),
    )

    return (
        2
        * EARTH_RADIUS_MILES
        * math.asin(math.sqrt(value))
    )


def generate_checkpoints(
    geometry,
    interval_miles,
):
    """
    Generate checkpoints along a route.

    Includes the starting point, regular
    distance checkpoints, and destination.
    """

    coordinates = geometry.get(
        "coordinates",
        [],
    )

    if not coordinates:
        return []

    interval_miles = float(
        interval_miles
    )

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

    for index in range(
        1,
        len(coordinates),
    ):
        start = coordinates[index - 1]
        end = coordinates[index]

        segment_distance = haversine_miles(
            start,
            end,
        )

        if segment_distance <= 0:
            continue

        segment_end_distance = (
            distance_traveled
            + segment_distance
        )

        while next_checkpoint <= segment_end_distance:
            fraction = (
                next_checkpoint
                - distance_traveled
            ) / segment_distance

            fraction = max(
                0.0,
                min(1.0, fraction),
            )

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
                    next_checkpoint,
                    2,
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
                distance_traveled,
                2,
            ),
        })

    return checkpoints


def get_alternative_routes(
    origin,
    destination,
    checkpoint_interval=25,
):
    """
    Generate alternative driving routes
    between the origin and destination.
    """

    origin_data = geocode_location(
        origin
    )

    destination_data = geocode_location(
        destination
    )

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
        logger.warning(
            "OSRM routing error: %s",
            exc,
        )

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
