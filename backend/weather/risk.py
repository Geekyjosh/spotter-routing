
def calculate_checkpoint_risk(weather, load_weight_lbs):
    """
    Calculate an illustrative weather risk score from 0 to 100.

    Higher scores indicate more severe weather conditions.
    Thresholds are application heuristics, not validated
    truck-safety standards.
    """

    if weather is None:
        return {
            "score": None,
            "level": "unknown",
            "factors": ["Weather forecast unavailable"],
        }

    score = 0
    factors = []

    gusts = weather.get("wind_gusts_mph") or 0
    rain = weather.get("rain_inches") or 0
    snow = weather.get("snowfall_cm") or 0

    # Wind gust risk
    if gusts >= 50:
        score += 45
        factors.append("Severe wind gusts")
    elif gusts >= 35:
        score += 30
        factors.append("Strong wind gusts")
    elif gusts >= 25:
        score += 15
        factors.append("Moderate wind gusts")

    # Rain risk
    if rain >= 0.3:
        score += 30
        factors.append("Heavy rainfall")
    elif rain >= 0.1:
        score += 20
        factors.append("Moderate rainfall")
    elif rain > 0:
        score += 5
        factors.append("Light rainfall")

    # Snow risk
    if snow >= 5:
        score += 35
        factors.append("Heavy snowfall")
    elif snow >= 1:
        score += 20
        factors.append("Moderate snowfall")
    elif snow > 0:
        score += 10
        factors.append("Light snowfall")

    # Illustrative load-weight sensitivity:
    # lighter loads receive an additional wind-risk penalty.
    if load_weight_lbs < 15000 and gusts >= 25:
        score += 15
        factors.append("Light load increases wind exposure")
    elif load_weight_lbs < 30000 and gusts >= 35:
        score += 10
        factors.append("Load weight increases wind sensitivity")

    score = min(score, 100)

    if score >= 70:
        level = "high"
    elif score >= 35:
        level = "moderate"
    else:
        level = "low"

    return {
        "score": score,
        "level": level,
        "factors": factors,
    }


def score_routes(routes, load_weight_lbs):
    """
    Score available weather checkpoints for each route.
    Routes with missing forecasts are marked incomplete.
    """

    for route in routes:
        known_scores = []
        unknown_count = 0

        for checkpoint in route.get("checkpoints", []):
            risk = calculate_checkpoint_risk(
                checkpoint.get("weather"),
                load_weight_lbs,
            )

            checkpoint["risk"] = risk

            if risk["score"] is None:
                unknown_count += 1
            else:
                known_scores.append(risk["score"])

        if known_scores:
            average_score = round(
                sum(known_scores) / len(known_scores),
                1,
            )
            maximum_score = max(known_scores)
        else:
            average_score = None
            maximum_score = None

        route["risk_summary"] = {
            "average_score": average_score,
            "maximum_score": maximum_score,
            "known_checkpoints": len(known_scores),
            "unknown_checkpoints": unknown_count,
            "assessment_complete": unknown_count == 0
            and len(known_scores) > 0,
        }

    return routes
