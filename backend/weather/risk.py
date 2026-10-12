
def _risk_band(value, thresholds):
    for index, threshold in enumerate(thresholds):
        if value < threshold:
            return index
    return len(thresholds)


def calculate_checkpoint_risk(weather, load_weight_lbs):
    if weather is None:
        return {
            "score": None,
            "level": "unknown",
            "severity": "unknown",
            "factors": ["Weather forecast unavailable"],
        }

    wind_speed = weather.get("wind_speed_mph")
    wind_gusts = weather.get("wind_gusts_mph")

    if wind_speed is None and wind_gusts is None:
        return {
            "score": None,
            "level": "unknown",
            "severity": "unknown",
            "factors": ["Wind forecast unavailable"],
        }

    wind = max(
        wind_speed or 0,
        wind_gusts or 0,
    )

    rain = weather.get("rain_inches_per_hour")
    snow = weather.get("snow_inches_per_hour")

    if rain is None or snow is None:
        return {
            "score": None,
            "level": "unknown",
            "severity": "unknown",
            "factors": ["Hourly precipitation rates unavailable"],
        }

    weight = float(load_weight_lbs)

    wind_band = _risk_band(
        wind, (25, 35, 45, 55)
    )

    # The final threshold is exclusive:
    # exactly 1.0 rain / 3.0 snow is Severe.
    rain_band = _risk_band(
        rain, (0.10, 0.25, 0.50, 1.000000001)
    )

    snow_band = _risk_band(
        snow, (0.5, 1.0, 2.0, 3.000000001)
    )

    # Handle the exact boundary explicitly.
    if rain > 1.0:
        rain_band = 4
    elif rain >= 0.50:
        rain_band = 3

    if snow > 3.0:
        snow_band = 4
    elif snow >= 2.0:
        snow_band = 3

    factors = []

    if wind_band:
        factors.append(f"Wind: {wind:.1f} mph")

    if rain_band:
        factors.append(f"Rain: {rain:.2f} in/hr")

    if snow_band:
        factors.append(f"Snow: {snow:.2f} in/hr")

    if wind >= 55:
        wind_band = 4
        factors.append("No travel: wind >=55 mph")

    elif wind >= 45 and weight > 30000:
        wind_band = 4
        factors.append(
            "No travel: heavy load and high wind"
        )

    elif wind >= 35 and weight > 40000:
        wind_band = max(wind_band, 3)
        factors.append(
            "Severe: heavy load and strong wind"
        )

    severity_band = max(
        wind_band,
        rain_band,
        snow_band,
    )

    severity_names = [
        "low",
        "moderate",
        "high",
        "severe",
        "no_travel",
    ]

    # Preserve the existing frontend API contract.
    display_levels = [
        "low",
        "moderate",
        "high",
        "high",
        "high",
    ]

    return {
        "score": severity_band * 25,
        "level": display_levels[severity_band],
        "severity": severity_names[severity_band],
        "factors": factors,
    }


def score_routes(routes, load_weight_lbs):
    for route in routes:
        checkpoints = route.get("checkpoints", [])

        known_scores = []
        unknown_count = 0
        severe_miles = 0.0
        high_miles = 0.0

        for index, checkpoint in enumerate(checkpoints):
            risk = calculate_checkpoint_risk(
                checkpoint.get("weather"),
                load_weight_lbs,
            )

            checkpoint["risk"] = risk

            if risk["score"] is None:
                unknown_count += 1
                continue

            known_scores.append(risk["score"])

            # Assign each checkpoint's risk to the
            # segment immediately following it.
            if index + 1 < len(checkpoints):
                segment_miles = max(
                    0.0,
                    checkpoints[index + 1]["distance_miles"]
                    - checkpoint["distance_miles"],
                )
            else:
                segment_miles = 0.0

            if risk["severity"] in (
                "severe",
                "no_travel",
            ):
                severe_miles += segment_miles

            elif risk["severity"] == "high":
                high_miles += segment_miles

        # The destination is already included by
        # generate_checkpoints(), so no extra segment
        # is added beyond the final checkpoint.

        average_score = (
            round(sum(known_scores) / len(known_scores), 1)
            if known_scores
            else None
        )

        maximum_score = (
            max(known_scores)
            if known_scores
            else None
        )

        route["risk_summary"] = {
            "average_score": average_score,
            "maximum_score": maximum_score,
            "severe_miles": round(severe_miles, 2),
            "high_miles": round(high_miles, 2),
            "known_checkpoints": len(known_scores),
            "unknown_checkpoints": unknown_count,
            "assessment_complete": (
                unknown_count == 0
                and bool(known_scores)
            ),
        }

    return routes
