# ENA–Spotter assessment handoff

The form requires all three links. Fill these in after the corresponding artifact exists:

- GitHub code: `PENDING — choose a repository and publish this checkout`
- Loom walkthrough (3–5 minutes): `PENDING — record and share the video`
- Hosted app: `PENDING — deploy the Render blueprint and smoke-check the public route flow`

## Suggested Loom run-through (about 4 minutes)

1. **0:00–0:30 — Product:** explain that RoadLedger takes current location, pickup, drop-off, cycle hours and departure time, then produces a route, schedule and printable daily logs.
2. **0:30–1:15 — Live trip:** enter a test such as Chicago, IL → Denver, CO → Phoenix, AZ with 42 cycle hours used. Show the map, route markers, estimated driving pace, pickup/drop-off work, rests and fuel stops. State that the public map services use a car routing profile.
3. **1:15–2:10 — Schedule:** point out the stop timeline and the 11-hour driving, 14-hour window, 30-minute interruption, 70/8 cycle, 10-hour rest and optional 34-hour restart assumptions. Explain that actual daily prior logs are not inputs.
4. **2:10–3:00 — Daily log:** show more than one calendar sheet, the 24-hour graph, four duty rows, totals, remarks and Print. Open print preview if time permits.
5. **3:00–4:00 — Code and boundaries:** show the React presentation and Django endpoint/planner, identify the OpenStreetMap/Nominatim/OSRM services, then mention the 55 mph truck estimate, blank driver/carrier fields and that this is not a certified ELD or compliance determination.

Before submitting the form, replace the pending entries above with the real GitHub, Loom and hosted-app URLs. Do not share the form with placeholder values.
