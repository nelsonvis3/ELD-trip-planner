# RoadLedger — HOS Trip Planner

Plan a truck trip and get the route, the required stops and printable daily duty logs, all based on Hours of Service (HOS) rules for property-carrying drivers.

**Live demo:** `<add Render URL>` · **Walkthrough:** `<add Loom URL>` · **Repo:** `<add GitHub URL>`

> **Disclaimer:** RoadLedger is an educational planning prototype. It is not an ELD record, a compliance system, or a legal determination of HOS compliance.

<!-- Add 2–3 screenshots here: planner form + map, stops list, daily log sheet. -->

## What it does

A driver enters:

- current location, pickup location and drop-off location
- 70-hour/8-day cycle hours already used
- departure time and home-terminal time zone

RoadLedger returns:

- the road route drawn on an interactive map, with distance and turn-by-turn directions
- pickup, drop-off, fuel, break, daily-rest and 34-hour restart events
- estimated arrival and remaining cycle hours
- one printable, ELD-style daily log sheet for every calendar day of the trip

## How it works

```
Browser (React + MapLibre)
        │  POST /api/plan/
        ▼
Django + DRF
  1. Geocode the three locations        → Photon
  2. Request the road route             → FOSSGIS OSRM (fallback: OSRM demo)
  3. Apply HOS planning model           → 55 mph pace, 11/14/8/70 rules
  4. Build events and daily logs        → JSON response
```

The frontend is a single React 18 app compiled in the browser with Babel Standalone, so there is no separate build step. Django serves it as a static asset and does all geocoding, routing and HOS calculation on the backend.

## Tech stack

| Layer | Tools |
| --- | --- |
| Frontend | React 18, JSX via Babel Standalone, MapLibre GL JS, custom responsive CSS |
| Backend | Python, Django, Django REST Framework, Gunicorn, WhiteNoise |
| Map and data | OpenFreeMap (tiles), Photon (geocoding), FOSSGIS OSRM (routing), OpenStreetMap data |
| Hosting | Render (single web service) |

## HOS planning model

| Rule | Modeled as |
| --- | --- |
| Driving limit | Up to 11 hours of driving after 10 consecutive hours off duty |
| Duty window | No driving after the 14th consecutive hour of the work window |
| Break | 30-minute non-driving interruption after 8 cumulative driving hours |
| Cycle | 70 hours in 8 days, from the hours already used |
| Restart | 34-hour restart when the remaining cycle cannot cover the route |
| Pickup / drop-off | 1 hour on duty each |
| Fuel | 30 minutes at every 1,000 route miles |
| Driving pace | 55 mph average |

**Assumptions:** at least 10 hours off duty before departure, no adverse driving conditions, no sleeper-berth split, and the cycle-hours-used value is the only prior cycle information. Old hours are not rolled out of the 8-day window.

The OSRM ETA is used for route information only. HOS driving time always uses the fixed 55 mph estimate. The 34-hour restart is a planning mechanism chosen by the prototype; it is optional under FMCSA rules.

## Daily logs

Each calendar day gets a printable sheet with:

- a 24-hour duty-status graph (Off Duty, Sleeper Berth, Driving, On Duty not driving)
- daily totals and route miles driven that day
- duty-change remarks and the day's events
- blank fields for carrier, vehicle, driver, mileage and other operational data

Sleeper Berth appears in the graph to match the reference log, but the planner does not schedule sleeper-berth time.

## Time zones

The selected IANA zone sets a standard UTC offset that is applied to every daily log. The planner does not switch the clock when a trip crosses a daylight-saving change or another time zone.

Supported zones: `America/New_York`, `America/Chicago`, `America/Denver`, `America/Phoenix`, `America/Los_Angeles`, `America/Anchorage`, `Pacific/Honolulu`. The form defaults to the browser zone when it is one of these, otherwise to `America/Chicago`.

## API

### `POST /api/plan/`

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

`cycle_used` is accepted as an alias of `current_cycle_used`.

The response includes route geometry and distance, directions, geocoded locations, pickup/drop-off/fuel/rest/break events, estimated arrival, remaining cycle hours, and calendar-day logs with hourly duty segments, daily totals and route-mile estimates.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

Open http://127.0.0.1:8000. Internet access is required for React, Babel, MapLibre, map tiles, geocoding and routing.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Private random secret, at least 50 characters in production. The local fallback is for development only. |
| `DJANGO_DEBUG` | `true` locally, `false` in production. |
| `DJANGO_ALLOWED_HOSTS` | Optional comma-separated custom hosts, e.g. `example.com,www.example.com`. On Render, `RENDER_EXTERNAL_HOSTNAME` is accepted automatically. |

## Deploy to Render

Deploy as a single Django web service.

- **Root directory:** `backend`
- **Build command:** `./build.sh` (installs dependencies, collects static files, applies migrations)
- **Start command:** `python -m gunicorn config.wsgi:application`
- **Environment:** `DJANGO_SECRET_KEY=<private random value>`, `DJANGO_DEBUG=false`

Static files are served by WhiteNoise from `staticfiles/`, which `collectstatic` generates and Git ignores. No PostgreSQL service is needed because trip plans are stateless and never stored. Before a production deploy, run `python manage.py check --deploy` with the production environment set.

## Project structure

```
ELD-trip-planner
├── config/            # settings, urls, wsgi, asgi
├── trips/
│   ├── static/trips/  # app.jsx, app.css
│   ├── templates/trips/index.html
│   ├── models.py
│   └── views.py       # /api/plan/ endpoint and planning logic
├── build.sh
├── manage.py
├── package.json
├── requirements.txt
└── README.md
```

## Limitations

- Geocoding, routing and tiles come from public services. They are not truck-specific (no height, weight or restriction awareness), may rate-limit, and are not production-grade. For sustained use, move to providers with documented limits and SLAs.
- Mitigations already in place: request timeouts, sequential geocoding, caching and a routing fallback.
- Trips are not persisted. Saved trips or accounts would require a production database such as PostgreSQL.
- The HOS model follows this project's interpretation of the FMCSA rules and does not cover sleeper-berth splits, adverse conditions or the real 8-day rollover.

## References

- FMCSA — Interstate Truck Driver's Guide to HOS
- FMCSA — Summary of Hours of Service Regulations
