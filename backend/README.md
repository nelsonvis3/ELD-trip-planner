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

`POST /api/plan/` accepts JSON (either `current_cycle_used` or `cycle_used`) and returns route geometry and directions, stop events, estimated arrival, cycle balance, and 24-hour sheets with status segments and totals.

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Denver, CO",
  "dropoff_location": "Phoenix, AZ",
  "current_cycle_used": 42,
  "departure": "2026-10-04T08:00",
  "time_zone": "America/Chicago"
}
```

The selected home-terminal IANA zone determines the standard UTC offset for the departure year. That fixed standard-time offset is used consistently across all sheets, including dates that cross daylight-saving changes. The app defaults to the browser’s zone when it is one of the listed U.S. zones; otherwise it uses America/Chicago. The home-terminal zone can be changed in the trip form.

## Environment variables

- `DJANGO_SECRET_KEY`: set a private random value of at least 50 characters in Vercel before deployment. The local fallback is for development only.
- `DJANGO_DEBUG`: `true` locally, `false` for a hosted service.
- `DJANGO_ALLOWED_HOSTS`: optional comma-separated custom hosts. Vercel deployment domains ending in `.vercel.app` are allowed automatically.

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

Regulatory references: [FMCSA Interstate Truck Driver’s Guide to HOS](https://www.fmcsa.dot.gov/sites/fmcsa.dot.gov/files/2022-04/FMCSA-HOS-395-DRIVERS-GUIDE-TO-HOS%282022-04-28%29_0.pdf) and [FMCSA HOS summary](https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations).

## Map and geocoding

Leaflet displays OpenStreetMap tiles, OSRM provides car-profile route geometry and turn data, and Nominatim converts each location query to coordinates. The backend serializes and spaces uncached geocoding requests to comply with Nominatim’s one-request-per-second public-service limit. OpenStreetMap attribution is shown in the map. These public community services have no availability guarantee and do not provide truck-specific routing; use a hosted or self-operated provider before sustained public traffic.

## Deploy to Vercel

This repository keeps Django in `backend/`. Create a Vercel project from the GitHub repository and set **Root Directory** to `backend`; Vercel detects `manage.py`, deploys Django as a Python function, runs `collectstatic`, and serves static assets through its CDN, as described in [Vercel’s Django deployment guide](https://vercel.com/docs/frameworks/full-stack/django). The checked-in `vercel.json` selects the Django framework and allows up to 60 seconds for the route-planning function. Add `DJANGO_SECRET_KEY` as a Vercel environment variable before deploying. `DJANGO_DEBUG` defaults to `false` on Vercel. The project does not require Render, Gunicorn, or a database service. Trips are stateless and are not stored. Confirm a real trip and print preview on the deployed URL before assessment submission.

## Assessment handoff

The assessment form requires GitHub, Loom, and hosted-app URLs. The checkout has a local Git commit but no configured GitHub remote yet. Publish this repository to GitHub, deploy the `backend/` root on Vercel, and record the 3–5 minute walkthrough. Put those three real links here and submit them in the ENA–Spotter form.
