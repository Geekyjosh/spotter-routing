
def recommend_safest_route(routes):
    """
    Recommend a route using illustrative weather risk scores.

    Only routes with complete forecast coverage are eligible.
    Prioritize maximum risk, then average risk, then duration.
    """

    eligible_routes = [
        route
        for route in routes
        if route.get("risk_summary", {}).get(
            "assessment_complete", False
        )
    ]

    if not eligible_routes:
        return {
            "status": "unavailable",
            "recommended_route_id": None,
            "reason": (
                "No route has complete weather forecast coverage. "
                "A reliable comparison cannot be made."
            ),
        }

    ranked_routes = sorted(
        eligible_routes,
        key=lambda route: (
            route["risk_summary"]["maximum_score"],
            route["risk_summary"]["average_score"],
            route["duration_minutes"],
        ),
    )

    recommended = ranked_routes[0]
    summary = recommended["risk_summary"]

    incomplete_count = len(routes) - len(eligible_routes)

    if incomplete_count:
        recommendation_status = "provisional"
        explanation = (
            f"{recommended['name']} has the lowest evaluated "
            "weather risk among routes with complete forecasts. "
            f"{incomplete_count} route(s) were excluded because "
            "their forecast coverage was incomplete."
        )
    else:
        recommendation_status = "complete"
        explanation = (
            f"{recommended['name']} is preferred based on "
            "the lowest maximum checkpoint risk, followed by "
            "average weather risk and estimated travel time."
        )

    return {
        "status": recommendation_status,
        "recommended_route_id": recommended["id"],
        "recommended_route_name": recommended["name"],
        "average_risk_score": summary["average_score"],
        "maximum_risk_score": summary["maximum_score"],
        "estimated_duration_minutes": recommended["duration_minutes"],
        "reason": explanation,
        "evaluated_route_count": len(eligible_routes),
        "excluded_route_count": incomplete_count,
        "truck_restrictions_verified": False,
    }
