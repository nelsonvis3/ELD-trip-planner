# RoadLedger — HOS Trip Planner

Full-stack Django and React trip-planning prototype for property-carrying drivers.

RoadLedger lets a driver enter a current location, pickup location, drop-off location, available 70/8 cycle hours, departure time, and home-terminal time zone. Django geocodes the locations, requests a road route, applies the project's Hours of Service planning assumptions, and returns route instructions, operational stops, estimated arrival, and printable calendar-day duty logs. React renders the planning workspace and interactive map.

> **Planning disclaimer:** RoadLedger is an educational planning prototype. It is not an ELD record, compliance system, or legal determination of Hours of Service compliance.

## Run locally

Create and activate a virtual environment, install the Python dependencies, and start Django:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Open http://127.0.0.1:8000.

The application requires internet access for React, Babel, MapLibre, map tiles, geocoding, and routing. Route lookup and HOS planning are performed by Django on the backend.

## Architecture and stack

### Frontend

* React 18
* JSX compiled in the browser with Babel Standalone
* Responsive custom CSS
* MapLibre GL JS
* Browser-based rendering with no separate frontend build step

The frontend is served by Django as a static asset and communicates with the backend through `POST /api/plan/`.

### Backend

* Python
* Django
* Django REST Framework
* WhiteNoise for static files
* Gunicorn for production serving

Django handles:

* location geocoding
* road routing requests
* route geometry and directions
* HOS schedule calculation
* fuel, break, daily-rest, and cycle-restart events
* calendar-day duty-log generation

### Map and external services

* **MapLibre GL JS** for map rendering
* **OpenFreeMap** for vector map tiles and map styling
* **Photon** for geocoding
* **FOSSGIS OSRM-compatible routing service** for primary car routing
* **Project OSRM demo service** as routing fallback
* **OpenStreetMap** data and attribution

These services are public external dependencies. They do not provide truck-specific routing and may impose rate limits or experience temporary availability issues.

## API

### `POST /api/plan/`

Accepts JSON containing the trip inputs and returns the planned route and HOS schedule.

Example request:

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

The API accepts either `current_cycle_used` or `cycle_used`.

The response includes:

* route geometry
* route distance
* turn-by-turn directions
* geocoded locations
* pickup and drop-off events
* fuel stops
* required rest and break events
* estimated arrival
* remaining cycle hours
* calendar-day duty logs
* hourly duty-status segments
* daily totals and route-mile estimates

## Time zone handling

The selected home-terminal IANA time zone determines the standard UTC offset used by the planner.

That standard-time offset is applied consistently across all generated daily logs. The planner does not switch the displayed clock when a trip crosses a daylight-saving transition or enters another time zone.

The form defaults to the browser's detected time zone when it is one of the supported U.S. zones. Otherwise, it defaults to `America/Chicago`.

Supported zones include:

```text
America/New_York
America/Chicago
America/Denver
America/Phoenix
America/Los_Angeles
America/Anchorage
Pacific/Honolulu
```

## HOS planning model and boundaries

The planner is based on the project's interpretation of the FMCSA Hours of Service rules for property-carrying drivers and the supplied assessment requirements.

The current prototype models:

* Up to 11 hours of driving after at least 10 consecutive hours off duty.
* No driving after the 14th consecutive hour from the start of the work window.
* A 30-minute non-driving interruption after 8 cumulative driving hours.
* A 70-hour/8-day cycle balance supplied as hours already used.
* A 34-hour cycle restart when the remaining cycle balance would otherwise prevent completing the route.
* One hour on duty for pickup.
* One hour on duty for drop-off.
* A 30-minute fuel stop at each 1,000 route miles.
* A 55 mph average truck pace for estimated driving time.

### Planning assumptions

The planner assumes:

* the driver has completed at least 10 consecutive hours off duty before departure;
* no adverse driving conditions are present;
* no sleeper-berth split is used;
* the supplied cycle-hours-used value is the only prior cycle information available;
* old hours are not rolled out of the eight-day window;
* fuel stops take 30 minutes;
* pickup takes one hour;
* drop-off takes one hour.

The 34-hour restart is selected by the prototype as a planning mechanism when the cycle balance is exhausted. The restart itself is optional under the FMCSA rules and is not intended to represent a real driver's complete regulatory history.

OSRM's car-routing ETA is used for route information and turn instructions, but it is not used to determine HOS driving time. The HOS schedule uses the project's fixed 55 mph planning estimate.

## Daily logs

For each calendar day covered by the trip, RoadLedger generates an ELD-style printable daily sheet containing:

* 24-hour duty-status graph
* Off Duty time
* Sleeper Berth row
* Driving time
* On Duty (not driving)
* daily duty totals
* route miles driven that day
* estimated route position
* duty-change remarks
* pickup, fuel, rest, break, and drop-off events
* blank fields for carrier, vehicle, driver, mileage, and other operational information

Sleeper Berth is included as a graph category to match the supplied log reference, but the current planner does not schedule sleeper-berth time.

The generated sheets are intended as a planning visualization rather than an official ELD record.

## Storage

Trip plans are **stateless** and are not persisted.

There are currently no application models used to store trips, routes, drivers, or planning results. The project retains Django's default SQLite configuration for the framework's built-in database functionality, but trip-planning results are returned directly from the API and are not stored as application records.

Because no trip data needs to survive a deployment, the application does not require a separate production database for its current scope.

## Environment variables

The application supports the following environment variables:

### `DJANGO_SECRET_KEY`

Private random secret used by Django.

A strong value of at least 50 characters should be configured in the hosted environment. The local fallback exists only for development and must not be used as a production secret.

### `DJANGO_DEBUG`

Controls Django debug mode.

Local development:

```text
DJANGO_DEBUG=true
```

Production:

```text
DJANGO_DEBUG=false
```

Debug mode must remain disabled in production.

### `DJANGO_ALLOWED_HOSTS`

Optional comma-separated list of custom hosts.

Example:

```text
example.com,www.example.com
```

On Render, the application also uses the platform-provided `RENDER_EXTERNAL_HOSTNAME` so the generated `.onrender.com` hostname can be accepted automatically.

## Deploy to Render

RoadLedger is deployed as a single Django web service.

The repository contains the Django project under the `backend/` directory, so the Render service should use:

```text
Root Directory:
backend
```

### Build command

Render should run:

```bash
./build.sh
```

The build script installs the Python dependencies, collects static files, and applies Django migrations.

### Start command

The production web server is:

```bash
python -m gunicorn config.wsgi:application
```

### Required environment variables

Configure these variables in the Render service:

```text
DJANGO_SECRET_KEY=<private random value>
DJANGO_DEBUG=false
```

`DJANGO_ALLOWED_HOSTS` is optional when using the automatically provided Render hostname. Add it when using custom domains.

### Static files

Django uses:

```text
STATIC_URL = /static/
STATIC_ROOT = staticfiles/
```

WhiteNoise serves the collected static files in production.

The `staticfiles/` directory is generated by `collectstatic` and is intentionally excluded from Git.

### No database service

The current version does not require a Render PostgreSQL database because trip plans are not persisted.

If the application later adds persistent trip history, user accounts, saved routes, or other database-backed features, the deployment architecture should be revisited and a production database such as PostgreSQL should be introduced.

## External service considerations

RoadLedger depends on public services for:

* geocoding
* road routing
* map tiles and styles

Public routing and geocoding infrastructure should not be treated as guaranteed production infrastructure.

For sustained public usage, the application should move to dedicated or self-operated providers with documented rate limits, availability, and usage policies.

The current prototype includes request timeouts, sequential geocoding, caching, and a routing fallback to reduce unnecessary failures during normal demonstration use.

## Security and production notes

The project keeps its production secret outside source control through environment variables.

The following files and directories should not be committed:

```text
.venv/
.env
db.sqlite3
staticfiles/
node_modules/
__pycache__/
*.py[cod]
```

The source files used to build and serve the application should remain committed, including:

```text
manage.py
config/
trips/
requirements.txt
build.sh
package.json
package-lock.json
README.md
```

Before a production deployment, run Django's deployment checks with the production environment configured:

```bash
python manage.py check --deploy
```

## Project structure

```text
backend/
├── config/
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── trips/
│   ├── migrations/
│   ├── static/
│   │   └── trips/
│   │       ├── app.css
│   │       └── app.jsx
│   ├── templates/
│   │   └── trips/
│   │       └── index.html
│   ├── models.py
│   └── views.py
├── build.sh
├── manage.py
├── package.json
├── package-lock.json
├── requirements.txt
├── .gitignore
└── README.md
```

`staticfiles/` is generated during deployment and is intentionally not part of the repository.

## Regulatory references

* [FMCSA — Interstate Truck Driver's Guide to HOS](https://www.fmcsa.dot.gov/sites/fmcsa.dot.gov/files/2022-04/FMCSA-HOS-395-DRIVERS-GUIDE-TO-HOS%282022-04-28%29_0.pdf)
* [FMCSA — Summary of Hours of Service Regulations](https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations)

## Assessment handoff

The assessment requires three public links:

```text
GitHub repository
Hosted application
Loom walkthrough
```

Before submission:

1. Push the final project to GitHub.
2. Deploy the `backend/` Django application to Render.
3. Verify the hosted planner with a real multi-stop trip.
4. Verify the route appears correctly on the map.
5. Verify the daily logs and print preview.
6. Record the final 3–5 minute walkthrough.
7. Add the three final URLs to the assessment submission.

## Project status

RoadLedger is a portfolio and assessment prototype demonstrating:

* Django backend development
* REST API design
* external API integration
* geocoding and routing
* React UI development
* interactive mapping with MapLibre
* HOS scheduling logic
* printable operational documents
* production deployment of a Django application
* separation of development and production configuration
