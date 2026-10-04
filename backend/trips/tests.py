from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import TestCase

from . import views


class HosPlannerTests(TestCase):
    def make_plan(self, miles=1500, pickup_miles=120, **overrides):
        data = {
            "distance_miles": miles,
            "pickup_miles": pickup_miles,
            "cycle_used": 42,
            "departure": "2026-03-08T01:00",
            "time_zone": "America/Chicago",
        }
        data.update(overrides)
        return views._make_plan(data)

    def assert_hos_limits(self, result, cycle_used):
        events = result["events"]
        shift_start = datetime.fromisoformat(events[0]["start"]).astimezone(timezone.utc)
        shift_driving = driving_since_break = 0
        cycle_on_duty = cycle_used * 60
        for event in events:
            end = datetime.fromisoformat(event["end"]).astimezone(timezone.utc)
            if event["type"] == "driving":
                shift_driving += event["minutes"]
                driving_since_break += event["minutes"]
                self.assertLessEqual(shift_driving, 660)
                self.assertLessEqual(driving_since_break, 480)
                self.assertLessEqual(end, shift_start + timedelta(hours=14))
                self.assertLess(cycle_on_duty, 4200)
                cycle_on_duty += event["minutes"]
            elif event["type"] == "onduty":
                cycle_on_duty += event["minutes"]
                if event["minutes"] >= 30:
                    driving_since_break = 0
            if event["label"] == "10-hour daily rest":
                shift_start, shift_driving, driving_since_break = end, 0, 0
            elif event["label"] == "34-hour cycle restart":
                shift_start, shift_driving, driving_since_break, cycle_on_duty = end, 0, 0, 0

    def test_fuel_stops_are_inserted_at_each_thousand_miles(self):
        result = self.make_plan(miles=2200, pickup_miles=120)
        stops = [event for event in result["events"] if event["label"].startswith("Fuel stop")]
        self.assertEqual([event["start_miles"] for event in stops], [1000, 2000])
        self.assertTrue(all(event["minutes"] == 30 for event in stops))

    def test_logs_use_home_terminal_standard_time_across_dst_boundary(self):
        result = self.make_plan(miles=1, pickup_miles=0, departure="2026-03-08T01:30")
        self.assertEqual(result["standard_time_label"], "UTC-06:00")
        self.assertTrue(result["events"][0]["start"].endswith("-06:00"))
        self.assertEqual(sum(result["days"][0]["totals"].values()), 1440)

    def test_short_local_trip_is_not_dropped_by_minute_rounding(self):
        result = self.make_plan(miles=0.005, pickup_miles=0.005, cycle_used=69.5)
        driving = [event for event in result["events"] if event["type"] == "driving"]
        self.assertEqual(len(driving), 1)
        self.assertAlmostEqual(driving[0]["distance_exact_miles"], 0.005)
        self.assertFalse(any(event["label"] == "34-hour cycle restart" for event in result["events"]))

    def test_accepts_the_assessment_cycle_field_name(self):
        result = views._make_plan({
            "distance_miles": 1,
            "pickup_miles": 0,
            "current_cycle_used": 42,
            "departure": "2026-10-04T08:00",
            "time_zone": "America/Chicago",
        })
        self.assertLess(result["cycle_hours_remaining"], 28)

    def test_home_page_references_django_static_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/trips/app.css")
        self.assertContains(response, "/static/trips/app.jsx")

    @patch("trips.views._route_trip")
    def test_plan_endpoint_accepts_current_cycle_used(self, route_trip):
        route_trip.return_value = {
            "places": [
                {"lat": 41.8, "lon": -87.6, "name": "Chicago"},
                {"lat": 39.7, "lon": -105.0, "name": "Denver"},
                {"lat": 33.4, "lon": -112.0, "name": "Phoenix"},
            ],
            "geometry": {"type": "LineString", "coordinates": [[-87.6, 41.8], [-105, 39.7], [-112, 33.4]]},
            "distance_miles": 10,
            "pickup_miles": 2,
            "route_hours": 1,
            "directions": [],
        }
        response = self.client.post("/api/plan/", data={
            "current_location": "Chicago, IL",
            "pickup_location": "Denver, CO",
            "dropoff_location": "Phoenix, AZ",
            "current_cycle_used": 42,
            "departure": "2026-10-04T08:00",
            "time_zone": "America/Chicago",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["route"]["distance_miles"], 10)
        route_trip.assert_called_once()

    def test_long_trip_produces_complete_24_hour_log_sheets(self):
        result = self.make_plan(miles=2200, pickup_miles=300, departure="2026-10-04T08:00")
        self.assertGreater(len(result["days"]), 1)
        for day in result["days"]:
            self.assertEqual(sum(day["totals"].values()), 1440)
            self.assertEqual(set(day["grid"]), {"offduty", "sleeper", "driving", "onduty"})
            self.assertEqual(sum(map(sum, day["grid"].values())), 1440)
        self.assert_hos_limits(result, cycle_used=42)

    def test_rejects_invalid_cycle_and_timezone(self):
        with self.assertRaisesRegex(ValueError, "Cycle used"):
            self.make_plan(cycle_used=70.1)
        with self.assertRaisesRegex(ValueError, "time zone"):
            self.make_plan(time_zone="Not/AZone")
        with self.assertRaisesRegex(ValueError, "cycle hours as a number"):
            views._validate_trip_inputs({
                "current_location": "Chicago", "pickup_location": "Denver", "dropoff_location": "Phoenix",
                "current_cycle_used": True, "departure": "2026-10-04T08:00", "time_zone": "America/Chicago",
            })

    def test_full_cycle_starts_with_a_34_hour_restart(self):
        result = self.make_plan(miles=10, pickup_miles=0, cycle_used=70)
        self.assertEqual(result["events"][0]["label"], "34-hour cycle restart")
        self.assertEqual(result["events"][0]["minutes"], 2040)
        self.assert_hos_limits(result, cycle_used=70)

    @patch("trips.views._geocode")
    @patch("trips.views._get_json")
    def test_malformed_route_response_is_a_clear_validation_error(self, get_json, geocode):
        geocode.side_effect = [
            {"lat": 41.8, "lon": -87.6, "name": "Chicago"},
            {"lat": 39.7, "lon": -105.0, "name": "Denver"},
            {"lat": 33.4, "lon": -112.0, "name": "Phoenix"},
        ]
        get_json.return_value = {"code": "Ok", "routes": [{}]}
        with self.assertRaisesRegex(ValueError, "incomplete route"):
            views._route_trip({"current_location": "Chicago", "pickup_location": "Denver", "dropoff_location": "Phoenix"})

    @patch("trips.views._geocode")
    @patch("trips.views._get_json")
    def test_route_response_preserves_pickup_leg_and_directions(self, get_json, geocode):
        geocode.side_effect = [
            {"lat": 41.8, "lon": -87.6, "name": "Chicago"},
            {"lat": 39.7, "lon": -105.0, "name": "Denver"},
            {"lat": 33.4, "lon": -112.0, "name": "Phoenix"},
        ]
        get_json.return_value = {"code": "Ok", "routes": [{
            "legs": [
                {"distance": 1609.344, "steps": [{"distance": 500, "name": "I-90", "maneuver": {"type": "depart"}}]},
                {"distance": 3220, "steps": []},
            ],
            "geometry": {"type": "LineString", "coordinates": [[-87.6, 41.8], [-105, 39.7], [-112, 33.4]]},
            "distance": 4829.344,
            "duration": 360,
        }]}
        route = views._route_trip({"current_location": "Chicago", "pickup_location": "Denver", "dropoff_location": "Phoenix"})
        self.assertAlmostEqual(route["pickup_miles"], 1)
        self.assertEqual(route["directions"][0]["text"], "Start I-90")
        self.assertEqual(len(route["geometry"]["coordinates"]), 3)

    @patch("trips.views._route_trip")
    def test_api_converts_invalid_trip_to_400(self, route_trip):
        response = self.client.post("/api/plan/", data={
            "current_location": "Chicago, IL",
            "pickup_location": "Denver, CO",
            "dropoff_location": "Phoenix, AZ",
            "cycle_used": 42,
            "departure": "not-a-date",
            "time_zone": "America/Chicago",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Choose a valid departure date and time.")
        route_trip.assert_not_called()
