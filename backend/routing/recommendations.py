
def recommend_safest_route(routes):
    eligible = [
        route
        for route in routes
        if route.get("risk_summary", {}).get(
            "assessment_complete", False
        )
    ]

    if not eligible:
        return {
            "status": "unavailable",
            "recommended_route_id": None,
            "reason": (
                "No route has complete weather forecast coverage. "
                "A reliable comparison cannot be made."
            ),
        }

    ranked = sorted(
        eligible,
        key=lambda route: (
            route["risk_summary"]["severe_miles"],
            route["risk_summary"]["high_miles"],
            route["risk_summary"]["average_score"],
            route["duration_minutes"],
        ),
    )

    recommended = ranked[0]
    summary = recommended["risk_summary"]

    excluded_count = (
        len(routes) - len(eligible)
    )

    if excluded_count:
        status = "provisional"
        reason = (
            f"{recommended['name']} ranks best among "
            "routes with complete forecasts. "
            "Other routes have incomplete weather coverage."
        )
    else:
        status = "complete"
        reason = (
            f"{recommended['name']} is preferred based on "
            "fewest severe miles, fewest high-risk miles, "
            "lowest average risk, and shortest travel time."
        )

    return {
        "status": status,
        "recommended_route_id": recommended["id"],
        "recommended_route_name": recommended["name"],
        "average_risk_score": summary["average_score"],
        "maximum_risk_score": summary["maximum_score"],
        "severe_miles": summary["severe_miles"],
        "high_miles": summary["high_miles"],
        "estimated_duration_minutes": (
            recommended["duration_minutes"]
        ),
        "reason": reason,
        "evaluated_route_count": len(eligible),
        "excluded_route_count": excluded_count,
        "truck_restrictions_verified": False,
    }
