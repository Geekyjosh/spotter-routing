
from django.test import SimpleTestCase

from weather.risk import (
    calculate_checkpoint_risk,
    score_routes,
)
from routing.recommendations import recommend_safest_route


def make_weather(
    wind=0,
    gusts=0,
    rain=0,
    snow=0,
):
    return {
        "wind_speed_mph": wind,
        "wind_gusts_mph": gusts,
        "rain_inches_per_hour": rain,
        "snow_inches_per_hour": snow,
    }


class WeatherRiskTests(SimpleTestCase):

    def check_severity(
        self,
        expected,
        weight=25000,
        **weather,
    ):
        result = calculate_checkpoint_risk(
            make_weather(**weather),
            weight,
        )

        self.assertEqual(
            result["severity"],
            expected,
        )

    def test_low_wind(self):
        self.check_severity("low", wind=24)

    def test_moderate_wind(self):
        self.check_severity("moderate", wind=25)

    def test_high_wind(self):
        self.check_severity("high", wind=35)

    def test_severe_wind(self):
        self.check_severity("severe", wind=45)

    def test_no_travel_wind(self):
        self.check_severity("no_travel", wind=55)

    def test_no_travel_for_heavy_load(self):
        self.check_severity(
            "no_travel",
            wind=45,
            weight=35000,
        )

    def test_severe_for_very_heavy_load(self):
        self.check_severity(
            "severe",
            wind=35,
            weight=45000,
        )

    def test_heavy_load_boundary(self):
        self.check_severity(
            "severe",
            wind=45,
            weight=30000,
        )

    def test_moderate_rain(self):
        self.check_severity(
            "moderate",
            rain=0.10,
        )

    def test_high_rain(self):
        self.check_severity(
            "high",
            rain=0.25,
        )

    def test_severe_rain(self):
        self.check_severity(
            "severe",
            rain=0.50,
        )

    def test_no_travel_rain(self):
        self.check_severity(
            "no_travel",
            rain=1.01,
        )

    def test_moderate_snow(self):
        self.check_severity(
            "moderate",
            snow=0.5,
        )

    def test_high_snow(self):
        self.check_severity(
            "high",
            snow=1.0,
        )

    def test_severe_snow(self):
        self.check_severity(
            "severe",
            snow=2.0,
        )

    def test_no_travel_snow(self):
        self.check_severity(
            "no_travel",
            snow=3.01,
        )

    def test_unknown_weather(self):
        result = calculate_checkpoint_risk(
            None,
            25000,
        )

        self.assertIsNone(result["score"])
        self.assertEqual(
            result["severity"],
            "unknown",
        )

    def test_missing_precipitation_rates(self):
        result = calculate_checkpoint_risk(
            {
                "wind_speed_mph": 15,
                "wind_gusts_mph": 20,
            },
            25000,
        )

        self.assertEqual(
            result["severity"],
            "unknown",
        )
        
    def test_rain_exact_no_travel_boundary(self):
        self.check_severity("severe", rain=1.0)

    def test_rain_above_no_travel_boundary(self):
        self.check_severity("no_travel", rain=1.01)

    def test_snow_exact_no_travel_boundary(self):
        self.check_severity("severe", snow=3.0)

    def test_snow_above_no_travel_boundary(self):
        self.check_severity("no_travel", snow=3.01)



class RouteRecommendationTests(SimpleTestCase):

    def make_route(
        self,
        route_id,
        severe_miles,
        high_miles,
        average_score,
        duration,
    ):
        return {
            "id": route_id,
            "name": route_id,
            "duration_minutes": duration,
            "risk_summary": {
                "severe_miles": severe_miles,
                "high_miles": high_miles,
                "average_score": average_score,
                "maximum_score": average_score,
                "assessment_complete": True,
            },
        }

    def test_fewest_severe_miles_wins(self):
        routes = [
            self.make_route(
                "route-1", 20, 0, 20, 60
            ),
            self.make_route(
                "route-2", 0, 30, 50, 120
            ),
        ]

        result = recommend_safest_route(routes)

        self.assertEqual(
            result["recommended_route_id"],
            "route-2",
        )

    def test_fewest_high_miles_wins(self):
        routes = [
            self.make_route(
                "route-1", 0, 15, 20, 60
            ),
            self.make_route(
                "route-2", 0, 0, 50, 120
            ),
        ]

        result = recommend_safest_route(routes)

        self.assertEqual(
            result["recommended_route_id"],
            "route-2",
        )

    def test_average_risk_breaks_tie(self):
        routes = [
            self.make_route(
                "route-1", 0, 0, 30, 60
            ),
            self.make_route(
                "route-2", 0, 0, 10, 120
            ),
        ]

        result = recommend_safest_route(routes)

        self.assertEqual(
            result["recommended_route_id"],
            "route-2",
        )

    def test_shortest_time_breaks_tie(self):
        routes = [
            self.make_route(
                "route-1", 0, 0, 10, 120
            ),
            self.make_route(
                "route-2", 0, 0, 10, 60
            ),
        ]

        result = recommend_safest_route(routes)

        self.assertEqual(
            result["recommended_route_id"],
            "route-2",
        )

    def test_incomplete_routes_are_excluded(self):
        complete = self.make_route(
            "route-1", 0, 0, 20, 100
        )

        incomplete = self.make_route(
            "route-2", 0, 0, 0, 50
        )

        incomplete["risk_summary"][
            "assessment_complete"
        ] = False

        result = recommend_safest_route(
            [complete, incomplete]
        )

        self.assertEqual(
            result["recommended_route_id"],
            "route-1",
        )

        self.assertEqual(
            result["status"],
            "provisional",
        )

    def test_no_complete_routes(self):
        result = recommend_safest_route([])

        self.assertEqual(
            result["status"],
            "unavailable",
        )

        self.assertIsNone(
            result["recommended_route_id"]
        )


class RouteMileageTests(SimpleTestCase):

    def test_severe_and_high_mileage(self):
        routes = [{
            "id": "route-1",
            "name": "Route 1",
            "duration_minutes": 120,
            "checkpoints": [
                {
                    "distance_miles": 0,
                    "weather": make_weather(wind=45),
                },
                {
                    "distance_miles": 25,
                    "weather": make_weather(wind=35),
                },
                {
                    "distance_miles": 50,
                    "weather": make_weather(wind=10),
                },
                {
                    "distance_miles": 75,
                    "weather": make_weather(wind=10),
                },
            ],
        }]

        result = score_routes(
            routes,
            25000,
        )

        summary = result[0]["risk_summary"]

        self.assertEqual(
            summary["severe_miles"],
            25,
        )

        self.assertEqual(
            summary["high_miles"],
            25,
        )

        self.assertTrue(
            summary["assessment_complete"]
        )
