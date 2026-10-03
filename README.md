# KNUST Emergency Response GIS

**A web-based GIS that finds the nearest emergency help on and around the KNUST
campus, and the fastest way to reach it.**

When something goes wrong on campus — a medical emergency, a fire, an accident,
a security threat — the first questions are *where is the nearest help?* and
*how do I get there quickly?* Straight-line distance answers the first question
badly: the clinic that looks closest may be across a fence, at the end of a
one-way street, or a long detour by road.

This system answers both questions using the real road network. It ranks every
hospital, clinic, police post, fire station and security office by **actual
travel time**, routes you there with turn-by-turn directions, and shows which
parts of campus are well served by emergency services and which are not.

At its core is a routing engine built from scratch for this project: the road
graph, the priority queue, the shortest-path search, the spatial index that
snaps a point to the nearest road, and the turn-by-turn instructions. It is
roughly 2,500 lines of dependency-free Python (1,654 in `routing/`, 491 in
`router.py`, 378 parsing OpenStreetMap).

Built by **Obrempong Kwabena Osei-Wusu**, Geomatic Engineering, KNUST.

---

## Contents

- [Features](#features)
- [Study area](#study-area)
- [How the routing works](#how-the-routing-works)
- [Where the data comes from](#where-the-data-comes-from)
- [Architecture](#architecture)
- [Running it locally](#running-it-locally)
- [Configuration](#configuration)
- [Accounts, roles and trust](#accounts-roles-and-trust)
- [API](#api)
- [Tests](#tests)
- [Deployment](#deployment)
- [Project layout](#project-layout)
- [Design principles](#design-principles)
- [Acknowledgements](#acknowledgements)
- [Licence](#licence)

---

## Features

**Find the nearest help.** Choose a service — medical, police, fire or campus
security — and every facility is ranked by how long it takes to reach over the
road network from where you are. On a phone, this is two taps from opening the
app.

**Get directions.** Routes for driving, cycling or walking, with turn-by-turn
instructions and an adjustable traffic level (clear, normal or heavy).

**See response coverage.** A map layer colours every road by how long help
would take to reach it from the nearest facility:

| Colour | Travel time |
|---|---|
| Green | under 2 min |
| Yellow | 2–5 min |
| Orange | 5–10 min |
| Red | 10–15 min |
| Purple | over 15 min, or no road access |

Coverage can be shown for all services together or for medical, police or fire
alone, and it follows the chosen travel mode and traffic level. It shows at a
glance where emergency services are well placed and where the gaps are.

**Report incidents, and route around them.** Users can report flooding, a
blocked road, an accident or suspicious activity. Reports at the same spot are
grouped together and only gain confidence when independent accounts confirm
them. Once a report is corroborated, routes, nearest-service rankings and
coverage all steer around it automatically. A lone report is shown on the map
and raised with security, but never diverts traffic on its own, so one false
report cannot close a road.

**Call for help.** The national emergency number and campus security are one
tap away on every screen, with no account needed.

**Keep the map current.** Campus security can add places that OpenStreetMap is
missing by long-pressing the map, and they become routable immediately.
Administrators manage roles, added places and every report from a dedicated
admin screen.

---

## Study area

The map covers a **3.5 km radius** around the campus centre (6.6745° N,
1.5716° W). That includes the campus itself and the surrounding communities —
Bomso, Ayeduase, Ahinsan and Asokore Mampong — whose hospitals, pharmacies and
police posts a real emergency would use.

The network holds about **6,100 junctions and 15,300 road segments**, and
**741 routable places**.

---

## How the routing works

Everything in `backend/src/routing/` was written for this project.

### The road graph

`builder.py` turns OpenStreetMap roads into a directed graph. Each road is split
at every junction, so an intersection is a real decision point. Edges are stored
in flat parallel arrays, which keeps the whole network in a few megabytes and
makes the search loop fast.

Each road segment records which travel modes may use it (drive, bike, walk),
decided separately for each direction:

- **Road class** sets the starting point: a motorway is not walkable, a footpath
  is not drivable.
- **Access tags** refine it, with the most specific tag winning: `access`,
  `vehicle`, `motor_vehicle`, `motorcar`, `bicycle` and `foot`. For example,
  `vehicle=no` closes a road to cars and bikes but not to walkers, and
  `bicycle=yes` opens a footpath to bikes.
- **Private roads** (`access=private` and similar, such as car-park aisles and
  compound roads) are kept but avoided: they cost four times as much, so a route
  uses one only when there is no reasonable public alternative. Reported travel
  times and coverage always use the real time.
- **One-way roads** bind cars and bikes. Walkers can go both ways. A cyclist
  facing a one-way can still walk the bike, at walking speed, wherever walking
  is allowed. `oneway:bicycle=no`, contraflow cycle lanes and direction-specific
  tags such as `vehicle:backward=no` are respected.

One graph serves all three modes, and the search only follows segments open to
the chosen mode in the direction of travel.

### Travel cost

`weights.py` holds a single cost model shared by routing, ranking and coverage,
so the three always agree:

| Mode  | Speed | Road type | Surface |
|-------|-------|-----------|---------|
| Walk  | 5 km/h | steps ×2.5, tracks ×1.3, paths ×1.1 | unpaved ×1.1 |
| Bike  | 15 km/h | tracks ×1.25, paths ×1.15 | compacted ×1.15, unpaved ×1.35, rough ×1.3 |
| Drive | 25 km/h by default | the road's own speed limit when recorded, per direction | at most 30 km/h on compacted, 20 on unpaved, 15 on rough |

Where a road type and its surface both slow travel, the larger factor applies,
not both, so a dirt track is not penalised twice.

**These speeds are routing-model assumptions, not data from OpenStreetMap.**
OpenStreetMap supplies only the classifications — the road type, `surface`,
`smoothness` and, on a few roads, a speed limit. The base speeds come from
reference routers (OSRM's 5 km/h walking and 15 km/h cycling) and Ghana's urban
speed limits; the surface and smoothness factors are this project's own
estimates. All of them live in named tables in `weights.py`, so they can be
calibrated against measured journey times on campus.

Traffic changes driving time only: clear −20%, normal unchanged, heavy +90%,
scaled by how congestion-prone each class of road is.

### The search

`dijkstra.py` implements **Dijkstra's algorithm** and **A\*** on a hand-written
binary min-heap with decrease-key (`priority_queue.py`), so improving a node's
cost is O(log n).

A\* estimates the remaining time as straight-line distance divided by the
fastest speed possible for the current mode and traffic level. Using the
fastest possible speed guarantees the estimate never exceeds the true remaining
time, so A\* always returns the optimal route.

Routes are rebuilt edge by edge, so the drawn path follows the exact shape of
each road.

### Directions

`instructions.py` first works out the manoeuvre at each junction — depart,
turn, continue, roundabout — and only then writes the text. Roundabouts become
a single step that names the exit ("At the roundabout, take the 2nd exit onto
Andrews Road"), counting the exits the route passes. A short unnamed link
between two stretches of the same named road is treated as part of that road,
so it does not add a needless step.

### Joining the network

People are rarely standing exactly on a road. `snapping.py` builds a spatial
grid over the network and finds the nearest point on the nearest road segment.
`overlay.py` then adds a temporary node at that exact point for the length of
one request. This routes you to the building you are beside, not to the end of
the street.

Several nearby roads are considered for each endpoint, which matters on
one-way and divided roads where the closest road may point the wrong way.

### Nearest services and coverage

**Nearest** runs a single search outward from the user and reads off the
facilities in the order it reaches them, instead of planning one route per
facility.

**Coverage** is a **multi-source Dijkstra**: every chosen facility starts at
time zero together, and one sweep labels every road with the time from the
closest one. The results are grouped into the colour bands above.

### Reported incidents

`hazards.py` turns corroborated incident reports into routing costs. Roads
near a **likely** or **confirmed** report cost more to use, so the search finds
a way around it whenever a reasonable one exists:

| Incident | Confirmed | Likely | Reaches |
|---|---|---|---|
| Blocked road | cars and bikes ×50, walkers ×3 | cars and bikes ×4, walkers ×1.5 | the road it was reported on |
| Flooding | everyone ×10 | everyone ×3 | everything within 40 m |
| Accident | cars ×3, bikes ×1.5 | cars ×1.5 | the road it was reported on |
| Suspicious activity | walkers ×3, bikes ×2 | walkers ×1.5 | everything within 40 m |

A hazard never closes a road outright. When it sits on the only way through,
the route is still given, with a warning that it passes the reported hazard —
in an emergency, a warned route is better than none. Reported travel times stay
the real driving or walking time, and unverified reports have no effect. Like
the surface speeds, these multipliers are the model's own assumptions, kept in
one table so they can be tuned.

The server re-reads live incidents at most every 30 seconds, and immediately
after a report is made, overridden or resolved.

### Reachability

At start-up the server finds the largest connected part of the road network and
leaves out places that cannot be reached from it. A facility that a responder
cannot actually get to is worse than none, so it is never offered.

---

## Where the data comes from

**Roads and places** come from **OpenStreetMap**, downloaded through the
[Overpass API](https://overpass-api.de) by `osm/overpass.py`, parsed by
`osm/parse.py`, and saved as JSON in `backend/src/cache/`. The saved copy is
part of the repository, so the server starts in about a tenth of a second
instead of waiting on Overpass, which is slow for an area this size.

**Campus knowledge** that OpenStreetMap lacks — correct names, phone numbers,
opening hours and missing places — is kept in
`backend/src/data/campus_places.json` and merged over the OpenStreetMap data by
`places.py`, which also catches duplicates within 30 m.

**Places added in the app** by campus security are stored in the database and
merged in the same way.

**Map backgrounds** are Esri World Imagery (satellite) and OpenStreetMap
(streets), both credited in the interface as their terms require.

---

## Architecture

```
┌──────────────────┐        ┌─────────────────────┐        ┌──────────────┐
│  Next.js client  │ ─────► │   FastAPI backend   │ ─────► │   Supabase   │
│  React + Leaflet │  HTTPS │  routing in memory  │  SQL   │   Postgres   │
└──────────────────┘        └─────────────────────┘        └──────────────┘
        │                             │                           │
        │ Supabase access token       │ verifies the token        │ auth
        └─────────────────────────────┴───────────────────────────┘
```

The road graph is built once at start-up and kept in memory, so a route takes a
few milliseconds.

The database stores what must survive a restart: accounts, roles, incident
reports and added places. The road network lives in memory and in the cached
OpenStreetMap files.

**Backend:** Python, with FastAPI, Uvicorn and psycopg as its only
dependencies. All graph and geometry code is the project's own.

**Frontend:** Next.js 16, React 19, React Leaflet, TanStack Query,
Tailwind CSS 4, Lucide icons and Supabase JS.

**Database and sign-in:** Supabase (PostgreSQL and Supabase Auth).

---

## Running it locally

### Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- A Supabase project, only for sign-in, incident reports and added places. The
  map, routing, nearest services and coverage all work without one.

### 1. Start the backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd src
python main.py            # http://127.0.0.1:8000
```

The road data is already included, so the server is ready in under a second.
If the cache is ever removed, the first start downloads it again from Overpass,
which takes a few minutes.

### 2. Start the frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev               # http://localhost:3000
```

Open http://localhost:3000. To switch on sign-in and reports, fill in the
settings described next.

---

## Configuration

Each half of the app reads its settings from a `.env.local` file. Start from the
`.env.example` in each folder.

### Backend — `backend/.env.local`

```bash
cp backend/.env.example backend/.env.local
```

Every value is optional; fill in the database and Supabase values to switch on
sign-in, incident reports and added places.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | Postgres connection string from Supabase (**Project Settings → Database**). |
| `DATABASE_CONNECT_TIMEOUT_S` | `10` | Seconds to wait when connecting to the database. |
| `SUPABASE_URL` | — | Project URL (**Project Settings → API**). Needed to check sign-ins. |
| `SUPABASE_PUBLISHABLE_KEY` | — | The publishable key from the same page. |
| `SUPABASE_TIMEOUT_S` | `10` | Seconds to wait when Supabase checks a sign-in. |
| `TOKEN_CACHE_TTL_S` | `60` | How long a checked sign-in is trusted before checking again. |
| `ADMIN_EMAILS` | — | Owner email(s), comma-separated. These accounts are admin on every sign-in and cannot be demoted. |
| `CAMPUS_SECURITY_PHONE` | — | Number shown in the emergency contacts. |
| `CAMPUS_SECURITY_LABEL` | `KNUST Security` | Label for that number. |
| `INCIDENT_REPORTS_PER_HOUR` | `3` | How many incident reports one account can send per hour. |
| `ALLOWED_ORIGINS` | — | Comma-separated web addresses allowed to call the API directly in production. |

Use the **publishable** Supabase key. The secret (`service_role`) key bypasses
row-level security and belongs in neither these files nor the browser.

The database tables are created automatically from `backend/src/schema.sql`
when the backend starts, so a new Supabase project is ready after the first
start.

The study area (campus centre, 3.5 km radius, snapping distances) is set in
`backend/src/config.py`.

### Frontend — `frontend/.env.local`

| Variable | Default | Purpose |
|---|---|---|
| `API_ORIGIN` | `http://localhost:8000` | Where the backend runs. The frontend forwards its `/api/*` requests there. |
| `NEXT_PUBLIC_SUPABASE_URL` | — | The same project URL as the backend. |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | — | The same publishable key as the backend. |

Restart both the backend and the frontend after changing these files.

---

## Accounts, roles and trust

**Sign-in** uses Supabase Auth with email and password. New accounts confirm
their address through an emailed link, and *Forgot password* sends a reset link.
The backend never handles passwords: it checks each request's Supabase access
token and briefly caches the result.

**Calling for help and using the map never require an account.**

Roles are **sets of permissions, not a ladder**, and an account can hold
**several at once**. Campus security answers incidents; keeping the map correct
is a different job, so it is a different role — and one person can do both.

| Role | report | resolve incidents | add places | edit/remove places | manage roles |
|---|:--:|:--:|:--:|:--:|:--:|
| `student` | ✓ | | | | |
| `security` | ✓ | ✓ | | | |
| `mapper` | ✓ | | ✓ | | |
| `admin` | ✓ | ✓ | ✓ | ✓ | ✓ |

What an account may do is the **union** of the roles it holds, so a student who
is also a mapper can report *and* add places, and a security officer who is also
a mapper keeps incident resolution as well. Everyone is a `student` implicitly.
Roles live in `students.roles` and are toggled per account on `/admin`.

**Managing roles.** Administrators change roles from the admin screen
(`/admin`), which is linked from the sidebar for admins. Owner accounts, set
with `ADMIN_EMAILS`, are always admin and cannot be demoted, so the project can
never be locked out. An admin can also *view the app as* a lower role to check
what others see; this only ever reduces access, and every action stays recorded
against the real account.

**Trust.** Accounts with a `knust.edu.gh` or `st.knust.edu.gh` address carry
full weight (1.0). Other addresses can sign in, but their reports weigh 0.25,
so a report needs more independent confirmation before it is shown as
confirmed. Confidence never reaches 100% from reports alone.

---

## API

Interactive documentation is available at `/docs` while the backend is running.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Whether the server is ready. |
| `GET` | `/health/db` | Whether the database is reachable. Also keeps the server and database awake when pinged regularly. |
| `GET` | `/bounds` | The service area. |
| `GET` | `/locations` | Every routable place. |
| `GET` | `/categories` | Service categories with counts and subtypes. |
| `GET` | `/config/public` | Emergency contact numbers. |
| `POST` | `/route` | A route between two points, with directions. |
| `POST` | `/nearest` | Facilities of one category, ranked by travel time. |
| `POST` | `/coverage` | Coverage bands as map lines. |
| `GET` | `/auth/me` | The signed-in account, created on first use. |
| `POST` | `/auth/forget` | Sign-out: drops the token from the server's cache. |
| `GET` / `POST` | `/incidents` | List incidents, or report one. |
| `GET` | `/incidents/queue` | Every report, including closed ones. Security and above. |
| `POST` | `/incidents/{id}/resolve`, `/incidents/{id}/override` | Security and above. |
| `POST` | `/places` | Add a place. Mappers and admins. |
| `PATCH` / `DELETE` | `/places/{id}` | Edit or remove a place. Admin only. |
| `GET` | `/admin/students` | Every account and its roles. Admin only. |
| `POST` | `/admin/students/{id}/role` | Set an account's roles. Admin only. |

---

## Tests

```bash
cd backend/src
python -m unittest discover -s tests -t .
```

The backend has **422 tests**. **357** run anywhere; the other **65** cover
accounts, roles, incident reports and place storage and need a database. To run
them, start a local Postgres and set `TEST_DATABASE_URL` to it. They refuse to
run against any non-local database, so they can never touch the live data.

Static checks:

```bash
python -m pyflakes backend/src                      # unused imports, undefined names
cd frontend && npx tsc --noEmit && npx eslint . && npx next build
```

**Continuous integration.** GitHub Actions runs the full backend suite, against
a temporary PostgreSQL database, on every push and pull request that changes
the backend.

---

## Deployment

| Part | Host | Notes |
|---|---|---|
| Backend | Render | Described in `render.yaml`. Set the backend variables from [Configuration](#configuration) in the service's Environment settings. |
| Frontend | Vercel | Set `API_ORIGIN` to the Render URL, plus the two Supabase variables. |
| Database and sign-in | Supabase | Add the deployed frontend address to the Auth redirect allow-list, so confirmation and reset links return to the app. |

**Database connection.** Prefer Supabase's **session** pooler (port 5432). The
transaction pooler (port 6543) also works; the backend detects it and adjusts
automatically.

**Staying awake.** Free Supabase projects pause after about a week without
activity, and free Render services sleep after 15 minutes without traffic.

- `.github/workflows/keepalive.yml` touches the database every two days, so
  Supabase never pauses. It uses the `DATABASE_URL` repository secret.
- To keep the backend responsive at all times, point a free uptime monitor
  (such as UptimeRobot) at `https://<your-render-url>/health/db` every
  5 minutes. This keeps both the server and the database awake.

---

## Project layout

```
backend/src/
  api.py              endpoints, validation, role checks
  main.py             entry point
  config.py           study area and settings
  data_loader.py      builds and caches the graph at start-up
  router.py           route planning, nearest services, coverage, reachability
  places.py           campus places layer, categories, subtypes
  incidents.py        grouping reports, confirmation, confidence
  accounts.py         roles and trust tiers
  auth.py             linking sign-ins to accounts
  supabase_auth.py    token checking and caching
  db.py, store.py     database connection, schema, place storage
  schema.sql          the complete database schema
  osm/                Overpass client, OpenStreetMap parsing, geometry
  routing/
    builder.py        OpenStreetMap roads to a directed graph
    graph.py          graph storage and distance helpers
    weights.py        the shared cost model
    priority_queue.py binary min-heap with decrease-key
    dijkstra.py       Dijkstra and A*
    snapping.py       spatial grid and point-to-road snapping
    overlay.py        temporary nodes for off-road start and end points
    instructions.py   turn-by-turn directions
    hazards.py        reported incidents as routing costs
  tests/              422 tests

frontend/
  app/                pages: map, sign-in, admin, creator
  components/
    Map.tsx           the map, its controls and layers
    BottomSheet.tsx   the phone panel
    phone/            the phone-first emergency flow
    sidebar/          the desktop planner
    map/              markers, legend, coverage key, help buttons
  lib/                API client, data queries, sign-in, hooks

.github/workflows/
  backend-tests.yml   runs the test suite on every backend change
  keepalive.yml       keeps the Supabase database awake
```

---

## Design principles

**One cost model.** Routing, ranking and coverage all use the same travel-time
function. If they disagreed, the app would tell the user one thing and show
another.

**Measure, don't assume.** The hardest bugs were found by measuring: an A\*
estimate that was provably wrong even though it never produced a worse route; a
clinic 90 m ahead on a one-way street that the ranking dropped while routing to
it worked; and a confidence score that rounded to exactly 100%.

**The phone comes first.** Someone in an emergency is holding a phone, not
sitting at a desk. The phone interface is designed on its own terms — two taps
to a route, one question at a time, plain words — rather than as the desktop
layout squeezed narrow.

**Every control earns its place.** Anything not needed in the moment sits
behind *More*.

---

## Acknowledgements

Above all, thanks to **God**, the source of every good thing.

To **Dr. Kwame Obeng**, whose mentorship, wisdom and belief shaped not only this
work but its author.

Built with [OpenStreetMap](https://www.openstreetmap.org/copyright) data,
© OpenStreetMap contributors, and Esri World Imagery for satellite tiles.

---

## Licence

The code is released under the [MIT Licence](LICENSE). You may use, copy,
modify and share it, including in your own projects, as long as you keep the
copyright notice and the licence text with it.

The map data is covered separately. Roads and places come from OpenStreetMap
and stay under the
[Open Database Licence (ODbL)](https://www.openstreetmap.org/copyright), so any
use of the data must credit © OpenStreetMap contributors. Satellite imagery is
provided by Esri under its own terms of use.
