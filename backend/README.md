# RoadLedger — HOS trip planner

Full-stack Django and React trip-planning prototype for property-carrying drivers. Enter a current location, pickup, drop-off, available 70/8 cycle hours, and departure time. Django geocodes the locations, requests a route, applies the planning assumptions, and returns route instructions, stops, and printable calendar-day duty logs. React displays the result and map.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Open `http://127.0.0.1:8000`. The app needs internet access for React, Leaflet, map tiles, geocoding, and routing. Map lookup is performed by Django so the HOS and route calculation stay on the backend.

## Architecture and stack

- **Frontend:** React 18, JSX compiled in the browser by Babel Standalone, responsive CSS, and Leaflet.
- **Backend:** Django with Django REST Framework; Django calls Nominatim and OSRM, runs the HOS schedule, and generates the daily log graph data.
- **Map services:** OpenStreetMap tiles, Nominatim geocoding, OSRM car-profile routing.
- **Storage:** no trip persistence. Django's default SQLite configuration is not used to store trip plans.

## API

`POST /api/plan/` accepts JSON and returns route geometry and directions, stop events, estimated arrival, cycle balance, and 24-hour sheets with status segments and totals.

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Denver, CO",
  "dropoff_location": "Phoenix, AZ",
  "cycle_used": 42,
  "departure": "2026-10-04T08:00",
  "time_zone": "America/Chicago"
}
```

The selected home-terminal IANA time zone is used for the departure, daily sheet boundaries, event times and arrival display. It defaults to the browser's zone and can be changed in the trip form.

## Environment variables

- `DJANGO_SECRET_KEY`: set a private random value in production. The local fallback is for development only.
- `DJANGO_DEBUG`: `true` locally, `false` for a hosted service.
- `DJANGO_ALLOWED_HOSTS`: comma-separated hosts; Render's assigned hostname is included automatically.

## HOS model and boundaries

The planner follows the supplied FMCSA Interstate Truck Driver’s Guide to Hours of Service for Property Carriers (April 2022) and FMCSA’s current summary for property-carrying drivers:

- Up to 11 hours driving after at least 10 consecutive hours off duty.
- No driving after the 14th consecutive hour from the start of the work window.
- A 30-minute non-driving interruption after 8 cumulative driving hours.
- A 70-hour/8-day cycle balance, supplied as hours already used.
- A 34-hour restart when remaining cycle hours are exhausted before the route is complete. This prototype chooses the restart to continue planning; FMCSA describes it as optional.
- One hour on duty for pickup and one hour on duty for drop-off.
- A 30-minute on-duty fuel stop at each 1,000 route miles. The assessment gives the fueling interval, but not its duration; 30 minutes is an explicit planning assumption.
- A 55 mph average estimates truck driving time from the road distance. OSRM’s car ETA is shown only as route information and is not used to decide HOS.

The schedule assumes the driver is eligible to begin work after at least 10 consecutive hours off duty; this prior rest is not an input and is not included before the trip's departure in the generated sheets. No adverse driving conditions or sleeper-berth split are modeled. The input only gives total cycle hours used, not the driver's dated on-duty history for all eight prior days. Consequently, the planner does not roll old hours out of the 8-day window. It generates ELD-style logs, not an ELD record, certification, or compliance determination. Duty details, location reports, vehicle, carrier, driver, mileage and shipping document fields absent from the request remain blank or estimated. Review the trip and confirm it against the actual driver's records before use.

The printed daily sheet follows the attached blank log reference: one 24-hour calendar sheet per date, continuous graph rows for Off Duty, Sleeper, Driving and On Duty, status totals, remarks, and fields for carrier/vehicle/driver details. Sleeper time is present as a graph row, but this model does not schedule sleeper time.

## Map and geocoding

Leaflet displays OpenStreetMap tiles, OSRM provides car-profile route geometry and turn data, and Nominatim converts each location query to coordinates. The backend serializes and spaces uncached geocoding requests to comply with Nominatim’s one-request-per-second public-service limit. OpenStreetMap attribution is shown in the map. These public community services have no availability guarantee and do not provide truck-specific routing; use a hosted or self-operated provider before sustained public traffic.

## Deploy

`render.yaml` describes a Render web service using Gunicorn and WhiteNoise. Connect the repository to Render and apply the blueprint to create a hosted version. Trips are stateless and are not stored. A production deployment still needs a real route smoke-check and print review.

## Assessment handoff

The assessment form requires GitHub, Loom, and hosted-app URLs. This checkout has no GitHub remote or commits yet. After publishing and recording the 3–5 minute walkthrough, put those three links here and submit them in the ENA–Spotter form.
