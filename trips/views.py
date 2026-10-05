import json
import math
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response


_geocode_lock = threading.Lock()
_geocode_cache = {}
_last_geocode_at = 0.0


def _get_json(url, *, service="free map", user_agent="RoadLedger/1.0 (ELD trip planning demonstration)"):
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json", "Accept-Language": "en"})
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        if exc.code == 403:
            raise ValueError(f"The {service} provider rejected this request (HTTP 403). Please try again shortly.") from exc
        raise ValueError(f"The {service} provider returned HTTP {exc.code}. Please try again shortly.") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"The {service} provider is temporarily unavailable. Please try again shortly.") from exc


def _geocode(query):
    global _last_geocode_at
    query = " ".join(query.split())
    if not query:
        raise ValueError("Enter all three locations to build a trip.")
    key = query.casefold()
    with _geocode_lock:
        if key in _geocode_cache:
            return _geocode_cache[key]
        wait = 1.1 - (time.monotonic() - _last_geocode_at)
        if wait > 0:
            time.sleep(wait)
        _last_geocode_at = time.monotonic()
        results = _get_json("https://photon.komoot.io/api/?" + urlencode({"limit": 1, "lang": "en", "q": query}), service="geocoding")
        features = results.get("features") if isinstance(results, dict) else None
        if not features:
            raise ValueError(f'Could not find "{query}". Try adding a city and state.')
        try:
            feature = features[0]
            properties = feature["properties"]
            coordinates = feature["geometry"]["coordinates"]
            name = ", ".join(str(properties[key]).strip() for key in ("name", "street", "city", "state", "country") if properties.get(key))
            if not name.strip() or len(coordinates) < 2:
                raise ValueError
            place = {"lat": float(coordinates[1]), "lon": float(coordinates[0]), "name": name.strip()}
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ValueError("The geocoding service returned an invalid location. Please try a more specific address.") from exc
        if not math.isfinite(place["lat"]) or not math.isfinite(place["lon"]) or not -90 <= place["lat"] <= 90 or not -180 <= place["lon"] <= 180:
            raise ValueError("The geocoding service returned invalid coordinates. Please try a more specific address.")
        if len(_geocode_cache) >= 256:
            _geocode_cache.pop(next(iter(_geocode_cache)))
        _geocode_cache[key] = place
        return place


def _maneuver_text(step):
    maneuver = step.get("maneuver", {})
    if not isinstance(maneuver, dict):
        maneuver = {}
    kind = maneuver.get("type", "continue")
    modifier = maneuver.get("modifier", "")
    name = step.get("name") or "the road"
    phrases = {"depart": "Start", "arrive": "Arrive", "turn": "Turn", "continue": "Continue",
               "new name": "Continue", "merge": "Merge", "fork": "Keep", "on ramp": "Take the ramp",
               "off ramp": "Take the exit", "roundabout": "Enter the roundabout", "rotary": "Enter the rotary",
               "end of road": "At the end of the road, turn", "uturn": "Make a U-turn", "use lane": "Use the lane"}
    phrase = phrases.get(kind, "Continue")
    if modifier and kind not in ("depart", "arrive", "roundabout", "rotary"):
        phrase += " " + modifier
    return f"{phrase} onto {name}" if kind not in ("depart", "arrive") else f"{phrase} {name}"


def _route_trip(data):
    if not isinstance(data, dict):
        raise ValueError("Trip details must be sent as a JSON object.")
    location_fields = ("current_location", "pickup_location", "dropoff_location")
    for field in location_fields:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 180:
            raise ValueError("Enter all three locations using no more than 180 characters each.")
    places = [_geocode(data[field]) for field in location_fields]
    coordinates = ";".join(f'{p["lon"]},{p["lat"]}' for p in places)
    query = f"{coordinates}?overview=full&geometries=geojson&steps=true"
    routing_urls = (
        f"https://routing.openstreetmap.de/routed-car/route/v1/driving/{query}",
        f"https://router.project-osrm.org/route/v1/driving/{query}",
    )
    routing_error = None
    for url in routing_urls:
        try:
            result = _get_json(url, service="routing")
            break
        except ValueError as exc:
            routing_error = exc
    else:
        raise routing_error or ValueError("The routing providers are temporarily unavailable. Please try again shortly.")
    if not isinstance(result, dict) or result.get("code") != "Ok" or not result.get("routes"):
        raise ValueError("No drivable route was found between these locations.")
    try:
        route = result["routes"][0]
        legs = route["legs"]
        coordinates = route["geometry"]["coordinates"]
        distance = float(route["distance"])
        duration = float(route["duration"])
        pickup_distance = float(legs[0]["distance"])
        if len(legs) != 2 or len(coordinates) < 2 or not all(math.isfinite(value) for value in (distance, duration, pickup_distance)):
            raise ValueError
        directions = []
        for leg in legs:
            for step in leg.get("steps", []):
                if not isinstance(step, dict):
                    continue
                step_distance = float(step.get("distance", 0))
                if math.isfinite(step_distance):
                    directions.append({"text": _maneuver_text(step), "distance_miles": round(step_distance / 1609.344, 1)})
        if distance <= 0 or duration <= 0 or pickup_distance < 0 or pickup_distance > distance:
            raise ValueError
        safe_coordinates = []
        for coordinate in coordinates:
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2 or not all(math.isfinite(float(value)) for value in coordinate[:2]):
                raise ValueError
            lon, lat = float(coordinate[0]), float(coordinate[1])
            if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ValueError
            safe_coordinates.append([lon, lat])
    except (KeyError, TypeError, ValueError, IndexError, OverflowError, AttributeError) as exc:
        raise ValueError("The routing service returned an incomplete route. Please try again shortly.") from exc
    return {"places": places, "geometry": {"type": "LineString", "coordinates": safe_coordinates}, "distance_miles": distance / 1609.344,
            "route_hours": duration / 3600, "pickup_miles": pickup_distance / 1609.344, "directions": directions}


def home(request):
    return render(request, "trips/index.html")


def _validate_trip_inputs(data):
    if not isinstance(data, dict):
        raise ValueError("Trip details must be sent as a JSON object.")
    for field in ("current_location", "pickup_location", "dropoff_location"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 180:
            raise ValueError("Enter all three locations using no more than 180 characters each.")
    cycle_value = data.get("cycle_used", data.get("current_cycle_used"))
    if isinstance(cycle_value, bool):
        raise ValueError("Enter cycle hours as a number from 0 through 70.")
    try:
        cycle_used = float(cycle_value)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Enter cycle hours as a number from 0 through 70.") from exc
    if not math.isfinite(cycle_used) or not 0 <= cycle_used <= 70:
        raise ValueError("Cycle used must be from 0 through 70 hours.")
    time_zone_name = data.get("time_zone", "UTC")
    if not isinstance(time_zone_name, str):
        raise ValueError("Choose a valid home-terminal time zone.")
    try:
        ZoneInfo(time_zone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError("Choose a valid home-terminal time zone.") from exc
    departure_value = data.get("departure")
    if not isinstance(departure_value, str):
        raise ValueError("Choose a valid departure date and time.")
    try:
        datetime.fromisoformat(departure_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Choose a valid departure date and time.") from exc


def _make_plan(data):
    miles = float(data["distance_miles"])
    if not math.isfinite(miles) or miles <= 0 or miles > 20000:
        raise ValueError("Route distance must be greater than zero and no more than 20,000 miles.")
    cycle_used = float(data.get("cycle_used", data.get("current_cycle_used")))
    if not math.isfinite(cycle_used) or not 0 <= cycle_used <= 70:
        raise ValueError("Cycle used must be from 0 through 70 hours.")
    time_zone_name = data.get("time_zone", "UTC")
    try:
        regional_zone = ZoneInfo(time_zone_name)
    except (ZoneInfoNotFoundError, TypeError) as exc:
        raise ValueError("Choose a valid home-terminal time zone.") from exc
    try:
        departure_value = data["departure"]
        if not isinstance(departure_value, str):
            raise ValueError
        departure = datetime.fromisoformat(departure_value.replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Choose a valid departure date and time.") from exc
    standard_reference = datetime(departure.year, 1, 15, 12, tzinfo=regional_zone)
    standard_offset = standard_reference.utcoffset()
    if standard_offset is None:
        raise ValueError("Choose a valid home-terminal time zone.")
    log_zone = timezone(standard_offset)
    start = departure.replace(tzinfo=log_zone) if departure.tzinfo is None else departure.astimezone(log_zone)

    drive_remaining = miles / 55 * 60
    distance_remaining = miles
    now = start.astimezone(timezone.utc)
    cycle_remaining = (70 - cycle_used) * 60
    events = []
    pickup_miles = float(data.get("pickup_miles", 0))
    if not math.isfinite(pickup_miles) or not 0 <= pickup_miles <= miles:
        raise ValueError("Pickup must be located along the current-to-drop-off route.")
    distance_driven = 0.0
    pickup_done = False

    def event(kind, label, minutes, distance=0):
        nonlocal now
        start_at = now
        now += timedelta(minutes=minutes)
        events.append({"type": kind, "label": label, "start": start_at.astimezone(log_zone).isoformat(),
                      "end": now.astimezone(log_zone).isoformat(), "minutes": round(minutes),
                      "distance_miles": round(distance, 1), "distance_exact_miles": distance,
                      "start_miles": round(distance_driven, 1),
                      "cumulative_miles": round(distance_driven + distance, 1)})
        return start_at, now

    shift_elapsed = 0
    driven_today = 0
    driving_since_break = 0
    miles_since_fuel = 0
    while drive_remaining > 0.000001:
        if not pickup_done and distance_driven >= pickup_miles - 0.000001:
            if cycle_remaining < 60:
                event("offduty", "34-hour cycle restart", 34 * 60)
                shift_elapsed = driven_today = driving_since_break = 0
                cycle_remaining = 70 * 60
            event("onduty", "Pickup · load and inspection", 60)
            shift_elapsed += 60
            cycle_remaining -= 60
            driving_since_break = 0
            pickup_done = True
            continue

        drive_limit = min(11 * 60 - driven_today, 14 * 60 - shift_elapsed,
                          8 * 60 - driving_since_break, drive_remaining, cycle_remaining)
        if not pickup_done:
            drive_limit = min(drive_limit, (pickup_miles - distance_driven) / 55 * 60)
        fuel_limit = (1000 - miles_since_fuel) / 55 * 60
        if fuel_limit <= 0.000001:
            duration = 30
            event("onduty", "Fuel stop", duration)
            shift_elapsed += duration
            cycle_remaining -= duration
            miles_since_fuel = 0
            driving_since_break = 0
            continue
        drive_limit = min(drive_limit, fuel_limit)

        if drive_limit <= 0.000001:
            if cycle_remaining <= 0.000001:
                event("offduty", "34-hour cycle restart", 34 * 60)
                shift_elapsed = driven_today = driving_since_break = 0
                cycle_remaining = 70 * 60
            elif driven_today >= 11 * 60 - 0.01 or shift_elapsed >= 14 * 60 - 0.01:
                event("offduty", "10-hour daily rest", 10 * 60)
                shift_elapsed = driven_today = driving_since_break = 0
            elif driving_since_break >= 8 * 60 - 0.01:
                event("onduty", "30-minute break", 30)
                shift_elapsed += 30
                cycle_remaining -= 30
                driving_since_break = 0
            else:
                raise ValueError("The schedule reached an unexpected driving limit.")
            continue

        segment_miles = min(distance_remaining, drive_limit / 60 * 55)
        segment_minutes = segment_miles / 55 * 60
        event("driving", "Drive", segment_minutes, segment_miles)
        distance_remaining -= segment_miles
        distance_driven += segment_miles
        drive_remaining -= segment_minutes
        driven_today += segment_minutes
        shift_elapsed += segment_minutes
        driving_since_break += segment_minutes
        cycle_remaining -= segment_minutes
        miles_since_fuel += segment_miles

        break_due = driving_since_break >= 8 * 60 - 0.01 and drive_remaining > 0.000001
        fuel_due = miles_since_fuel >= 1000 - 0.01 and drive_remaining > 0.000001
        if fuel_due:
            event("onduty", "Fuel stop · 30-minute break" if break_due else "Fuel stop", 30)
            shift_elapsed += 30
            cycle_remaining -= 30
            miles_since_fuel = 0
            driving_since_break = 0
        elif break_due:
            event("onduty", "30-minute break", 30)
            shift_elapsed += 30
            cycle_remaining -= 30
            driving_since_break = 0

        # A drive segment may use the exact remaining window/cycle; rest before next segment.
        if drive_remaining > 0.000001 and (driven_today >= 11 * 60 - 0.01 or shift_elapsed >= 14 * 60 - 0.01):
            event("offduty", "10-hour daily rest", 10 * 60)
            shift_elapsed = driven_today = driving_since_break = 0

    if not pickup_done:
        event("onduty", "Pickup · load and inspection", 60)
        cycle_remaining -= 60
        driving_since_break = 0
    event("onduty", "Drop-off · unload", 60)
    cycle_remaining -= 60
    arrival = now.astimezone(log_zone)
    days = _calendar_logs(start, arrival, events)
    offset_minutes = int(standard_offset.total_seconds() // 60)
    sign = "+" if offset_minutes >= 0 else "-"
    offset_minutes = abs(offset_minutes)
    standard_time_label = f"UTC{sign}{offset_minutes // 60:02d}:{offset_minutes % 60:02d}"
    return {"distance_miles": round(miles, 1), "estimated_drive_hours": round(miles / 55, 1),
            "arrival": arrival.isoformat(), "time_zone": time_zone_name, "standard_time_label": standard_time_label, "events": events, "days": days,
            "cycle_hours_remaining": round(max(cycle_remaining, 0) / 60, 1),
            "assumptions": ["Truck travel estimate: 55 mph average", "1 hour pickup and 1 hour drop-off",
                            "30-minute fuel stop at least every 1,000 miles", "10-hour daily rest; 34-hour cycle restart when needed"]}

def _calendar_logs(start, end, events):
    def mileage_at(moment):
        travelled = 0.0
        for item in events:
            a = datetime.fromisoformat(item["start"]).astimezone(start.tzinfo)
            b = datetime.fromisoformat(item["end"]).astimezone(start.tzinfo)
            if moment < a:
                return travelled
            if a <= moment <= b:
                if item["type"] == "driving":
                    span = max(1, (b.astimezone(timezone.utc) - a.astimezone(timezone.utc)).total_seconds())
                    fraction = (moment.astimezone(timezone.utc) - a.astimezone(timezone.utc)).total_seconds() / span
                    return item["cumulative_miles"] - item["distance_exact_miles"] * (1 - fraction)
                return item["cumulative_miles"]
            travelled = item["cumulative_miles"]
        return travelled

    logs = []
    midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
    keys = ("offduty", "sleeper", "driving", "onduty")
    while midnight < end:
        next_midnight = midnight + timedelta(days=1)
        grid = {key: [0] * 24 for key in keys}
        totals = {key: 0 for key in keys}
        segments = []
        remarks = []
        miles_driven = 0.0
        cursor = midnight
        for item in events:
            event_start = datetime.fromisoformat(item["start"]).astimezone(start.tzinfo)
            event_end = datetime.fromisoformat(item["end"]).astimezone(start.tzinfo)
            a = max(event_start, midnight)
            b = min(event_end, next_midnight)
            if a >= b:
                continue
            key = item["type"]
            if key == "driving":
                miles_driven += item["distance_exact_miles"] * (b - a).total_seconds() / max(1, (datetime.fromisoformat(item["end"]) - datetime.fromisoformat(item["start"])).total_seconds())
            remarks.append({"start": a.isoformat(), "label": item["label"], "cumulative_miles": round(mileage_at(a), 1)})
            if a > cursor:
                segments.append({"status": "offduty", "start_minute": int((cursor - midnight).total_seconds() / 60),
                                 "end_minute": int((a - midnight).total_seconds() / 60)})
            segments.append({"status": key, "start_minute": int((a - midnight).total_seconds() / 60),
                             "end_minute": int((b - midnight).total_seconds() / 60)})
            cursor = max(cursor, b)
        if cursor < next_midnight:
            segments.append({"status": "offduty", "start_minute": int((cursor - midnight).total_seconds() / 60),
                             "end_minute": 1440})
        for segment in segments:
            key = segment["status"]
            position = segment["start_minute"]
            end_position = segment["end_minute"]
            totals[key] += end_position - position
            while position < end_position:
                hour = position // 60
                boundary = min(end_position, (hour + 1) * 60)
                grid[key][hour] += boundary - position
                position = boundary
        logs.append({"number": len(logs) + 1, "date": midnight.date().isoformat(),
                     "totals": {key: round(value) for key, value in totals.items()},
                     "grid": {key: [round(v) for v in values] for key, values in grid.items()},
                     "segments": segments, "events": remarks, "drive_miles": round(miles_driven, 1),
                     "from_miles": round(mileage_at(midnight), 1), "to_miles": round(mileage_at(next_midnight), 1)})
        midnight = next_midnight
    return logs


@api_view(["POST"])
def plan(request):
    try:
        data = request.data
        _validate_trip_inputs(data)
        route = _route_trip(data)
        result = _make_plan({**data, "cycle_used": data.get("cycle_used", data.get("current_cycle_used")),
                             "distance_miles": route["distance_miles"], "pickup_miles": route["pickup_miles"]})
        result.update({"route": route})
        return Response(result)
    except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError) as exc:
        return Response({"error": str(exc) or "Invalid trip details."}, status=400)
