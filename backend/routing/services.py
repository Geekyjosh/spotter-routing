
import logging
import math

import requests
from requests.exceptions import RequestException


logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"

HEADERS = {
    "User-Agent": "SpotterRoutingAssessment/1.0 (development)",
    "Accept": "application/json",
}

METERS_PER_MILE = 1609.344
EARTH_RADIUS_MILES = 3958.7613

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


class RoutingError(Exception):
    pass


def geocode_location(location):
    normalized = " ".join(
        location.strip().lower().split()
    )

    if normalized in KNOWN_LOCATIONS:
        longitude, latitude = KNOWN_LOCATIONS[normalized]

        return {
            "coordinates": [longitude, latitude],
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
        "label": result.get("display_name", location),
    }


def haversine_miles(point_a, point_b):
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
    coordinates = geometry.get("coordinates", [])

    if not coordinates:
        return []

    interval_miles = float(interval_miles)

    if interval_miles <= 0:
        raise ValueError(
            "Checkpoint interval must be greater than zero."
        )

    checkpoints = [{
        "index": 0,
        "coordinates": coordinates[0],
        "distance_miles": 0.0,
    }]

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
                start[0] + (end[0] - start[0]) * fraction
            )
            latitude = (
                start[1] + (end[1] - start[1]) * fraction
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


def _request_osrm(coordinates, alternatives=False):
    coordinate_string = ";".join(
        f"{point[0]},{point[1]}"
        for point in coordinates
    )

    url = f"{OSRM_URL}/{coordinate_string}"

    try:
        response = requests.get(
            url,
            params={
                "overview": "full",
                "geometries": "geojson",
                "alternatives": (
                    "true" if alternatives else "false"
                ),
                "steps": "false",
            },
            headers=HEADERS,
            timeout=45,
        )

        response.raise_for_status()
        data = response.json()

    except (RequestException, ValueError) as exc:
        logger.warning("OSRM request failed: %s", exc)
        raise RoutingError(
            "Unable to retrieve routes from the routing provider."
        ) from exc

    if data.get("code") != "Ok":
        raise RoutingError(
            data.get("message", "Routing request failed.")
        )

    return data.get("routes", [])


def _sample_route(geometry, sample_count=20):
    """
    Sample coordinates at approximately equal
    positions along the geometry.
    """
    coordinates = geometry.get("coordinates", [])

    if len(coordinates) < 2:
        return coordinates

    cumulative = [0.0]

    for index in range(1, len(coordinates)):
        cumulative.append(
            cumulative[-1]
            + haversine_miles(
                coordinates[index - 1],
                coordinates[index],
            )
        )

    total = cumulative[-1]

    if total <= 0:
        return [coordinates[0]]

    samples = []
    segment_index = 1

    for index in range(sample_count + 1):
        target = total * index / sample_count

        while (
            segment_index < len(cumulative) - 1
            and cumulative[segment_index] < target
        ):
            segment_index += 1

        start_distance = cumulative[segment_index - 1]
        end_distance = cumulative[segment_index]

        fraction = (
            (target - start_distance)
            / (end_distance - start_distance)
            if end_distance > start_distance
            else 0.0
        )

        start = coordinates[segment_index - 1]
        end = coordinates[segment_index]

        samples.append([
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction,
        ])

    return samples


def _is_distinct_route(candidate, existing_routes):
    """
    Reject nearly identical routes.

    Compare corresponding distance-based samples,
    not just total distance or duration.
    """
    candidate_samples = _sample_route(
        candidate["geometry"]
    )

    if not candidate_samples:
        return False

    for existing in existing_routes:
        existing_samples = _sample_route(
            existing["geometry"]
        )

        if len(candidate_samples) != len(existing_samples):
            continue

        differences = [
            haversine_miles(a, b)
            for a, b in zip(
                candidate_samples,
                existing_samples,
            )
        ]

        average_difference = (
            sum(differences) / len(differences)
        )

        # Less than one mile average separation
        # is treated as essentially the same route.
        if average_difference < 1.0:
            return False

    return True


def _candidate_waypoints(start, end):
    """
    Produce potential intermediate coordinates
    on either side of the origin-destination line.

    OSRM snaps them to actual roads.
    """
    start_lon, start_lat = start
    end_lon, end_lat = end

    midpoint_lon = (start_lon + end_lon) / 2
    midpoint_lat = (start_lat + end_lat) / 2

    lat_miles_per_degree = 69.0
    lon_miles_per_degree = max(
        10.0,
        69.0 * abs(
            math.cos(math.radians(midpoint_lat))
        ),
    )

    east_miles = (
        end_lon - start_lon
    ) * lon_miles_per_degree

    north_miles = (
        end_lat - start_lat
    ) * lat_miles_per_degree

    length = math.hypot(east_miles, north_miles)

    if length < 10:
        return []

    # Perpendicular unit vector.
    perp_east = -north_miles / length
    perp_north = east_miles / length

    offsets = [
        min(12, length * 0.12),
        -min(12, length * 0.12),
        min(20, length * 0.20),
        -min(20, length * 0.20),
    ]

    candidates = []

    for offset in offsets:
        lon = (
            midpoint_lon
            + perp_east * offset / lon_miles_per_degree
        )
        lat = (
            midpoint_lat
            + perp_north * offset / lat_miles_per_degree
        )

        candidates.append([
            round(lon, 6),
            round(lat, 6),
        ])

    return candidates


def _find_additional_route(start, end, existing_routes):
    """
    Try to find one more real OSRM route.

    Never construct a fake route by drawing a line.
    """
    if not existing_routes:
        return None

    shortest_distance = min(
        route["distance"]
        for route in existing_routes
    )

    shortest_duration = min(
        route["duration"]
        for route in existing_routes
    )

    candidates = []

    for waypoint in _candidate_waypoints(start, end):
        try:
            results = _request_osrm(
                [start, waypoint, end],
                alternatives=False,
            )
        except RoutingError:
            continue

        for route in results:
            if route["distance"] > shortest_distance * 1.5:
                continue

            if route["duration"] > shortest_duration * 1.5:
                continue

            if not _is_distinct_route(
                route,
                existing_routes,
            ):
                continue

            candidates.append(route)

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda route: route["duration"],
    )


def get_alternative_routes(
    origin,
    destination,
    checkpoint_interval=25,
):
    origin_data = geocode_location(origin)
    destination_data = geocode_location(destination)

    start = origin_data["coordinates"]
    end = destination_data["coordinates"]

    provider_routes = _request_osrm(
        [start, end],
        alternatives=True,
    )

    if not provider_routes:
        raise RoutingError(
            "No available driving routes were found."
        )

    # Keep up to three distinct routes.
    selected = []

    for route in provider_routes:
        if _is_distinct_route(route, selected):
            selected.append(route)

        if len(selected) >= 3:
            break

    # Try additional real road routes when OSRM
    # supplies fewer than three alternatives.
    while len(selected) < 3:
        extra = _find_additional_route(
            start,
            end,
            selected,
        )

        if extra is None:
            break

        selected.append(extra)

    routes = []

    for index, route in enumerate(selected[:3]):
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

    return {
        "origin": origin_data,
        "destination": destination_data,
        "routes": routes,
        "route_count": len(routes),
        "routing_provider": "OSRM",
        "truck_restrictions_verified": False,
    }
