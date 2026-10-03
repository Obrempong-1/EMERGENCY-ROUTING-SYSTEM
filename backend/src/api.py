"""HTTP API for the KNUST emergency routing service."""

from __future__ import annotations

import logging
import threading
import os
import time
from contextlib import asynccontextmanager
from typing import Literal, Optional, get_args

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import accounts
import auth
import config
import data_loader
import db
import incidents
import places
import supabase_auth
from router import NoRouteError, RoutingService, SnapError
from routing.graph import haversine_m
from routing.hazards import hazards_from_incidents
from routing.weights import DRIVE, WALK

logger = logging.getLogger(__name__)

DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

TransportMode = Literal["drive", "walk", "bike"]
TrafficLevel = Literal["low", "normal", "heavy"]
Objective = Literal["fastest", "shortest"]
Algorithm = Literal["astar", "dijkstra"]
EmergencyCategory = Literal[
    "medical", "police", "fire_station", "security", "administration", "student_services"
]

assert set(get_args(EmergencyCategory)) == set(data_loader.CATEGORY_NAMES)

class ServiceState:
    """Process-wide, read-only-after-startup application state."""

    __slots__ = ("routing", "locations", "osm_locations", "error", "places_version")

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.routing: Optional[RoutingService] = None
        self.locations: list = []
        self.osm_locations: list = []
        self.error: Optional[str] = None
        self.places_version: int = 0

state = ServiceState()
_coverage_cache: dict = {}
_COVERAGE_CACHE_LIMIT = 8

_HAZARD_TTL_S = 30.0
_hazards: dict = {"loaded_at": None, "hazards": ()}
_hazard_lock = threading.Lock()

def current_hazards() -> tuple:
    """Corroborated incidents as routing hazards, reloaded at most every 30 seconds.

    A database hiccup keeps the last known hazards rather than failing the route:
    routing must keep working even when reports cannot be read.
    """
    with _hazard_lock:
        loaded_at = _hazards["loaded_at"]
        if loaded_at is not None and time.monotonic() - loaded_at < _HAZARD_TTL_S:
            return _hazards["hazards"]
        try:
            _hazards["hazards"] = hazards_from_incidents(incidents.live())
        except Exception:
            logger.warning("Could not load incidents for routing; using the last known set",
                           exc_info=True)
        _hazards["loaded_at"] = time.monotonic()
        return _hazards["hazards"]

def forget_hazards() -> None:
    """Make the next request reload incidents, after a report or a decision on one."""
    with _hazard_lock:
        _hazards["loaded_at"] = None

def _only_reachable(service, locations: list) -> list:
    """Drop places no route could reach, so every marker on the map is a real destination."""
    stranded = service.unreachable(locations)
    if not stranded:
        return locations

    dropped = {id(place) for place, _ in stranded}
    for place, reason in stranded:
        logger.info("Not routable, leaving it off the map: %s (%s)", place["name"], reason)
    logger.warning("%d of %d places are not routable and were left off the map",
                   len(stranded), len(locations))
    return [place for place in locations if id(place) not in dropped]

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        if db.configured():
            db.apply_schema()
            logger.info("Database ready")
        problem = config.auth_misconfigured()
        if problem:
            logger.error("Authentication is unavailable: %s", problem)
        elif db.configured():
            logger.info("Authentication ready (Supabase project %s)", config.SUPABASE_URL)
        logger.info("Loading map data")
        state.routing = RoutingService.from_segments(data_loader.load_segments())
        state.osm_locations = data_loader.load_osm_locations()
        state.locations = _only_reachable(
            state.routing, data_loader.get_locations(state.osm_locations))
        state.error = None
        logger.info("Ready with %d locations", len(state.locations))
    except Exception as exc:
        state.routing = None
        state.locations = []
        state.error = f"{type(exc).__name__}: {exc}"
        logger.exception("Startup failed")
    yield
    state.reset()
    db.close()

app = FastAPI(title="KNUST GIS Emergency Routing API", lifespan=lifespan)
@app.exception_handler(RequestValidationError)
def invalid_request(_request, exc: RequestValidationError) -> JSONResponse:
    """Report validation failures without echoing the offending value back.

    Pydantic includes the rejected input in its error detail. For NaN or Infinity
    that value cannot be serialised into JSON, which turned a client error into a
    500 on every endpoint that takes a float.
    """
    problems = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
        message = error.get("msg", "is invalid")
        problems.append(f"{field}: {message}" if field else message)
    return JSONResponse(status_code=422,
                        content={"detail": "; ".join(problems) or "Invalid request."})

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

def require_service() -> RoutingService:
    if state.routing is None:
        raise HTTPException(
            status_code=503,
            detail=f"Routing engine not ready: {state.error or 'still loading'}",
        )
    return state.routing

class RouteRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lon: float = Field(..., ge=-180, le=180)
    dest_lat: float = Field(..., ge=-90, le=90)
    dest_lon: float = Field(..., ge=-180, le=180)
    objective: Objective = "fastest"
    transport_mode: TransportMode = "drive"
    traffic_level: TrafficLevel = "normal"
    algorithm: Algorithm = "astar"
    destination_name: Optional[str] = Field(default=None, max_length=200)

class NearestRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    category: EmergencyCategory = "medical"
    transport_mode: TransportMode = "drive"
    traffic_level: TrafficLevel = "normal"
    limit: int = Field(default=3, ge=1, le=10)
    subtype: Optional[str] = Field(default=None, max_length=40)

@app.get("/")
async def root():
    return {"status": "ok", "service": "KNUST Emergency GIS backend"}

@app.get("/health")
async def health(response: Response):
    service = state.routing
    if service is None:
        response.status_code = 503
    return {
        "ready": service is not None,
        "error": state.error,
        "locations": len(state.locations),
        "places_version": state.places_version,
        "graph_nodes": len(service.graph) if service else 0,
        "graph_edges": service.graph.edge_count if service else 0,
    }

@app.get("/health/db")
def health_db(response: Response):
    """Touch the database, so an uptime monitor keeps both this server and Supabase awake."""
    if not db.configured():
        return {"database": "not configured"}
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception:
        logger.warning("Database health check failed", exc_info=True)
        response.status_code = 503
        return {"database": "unreachable"}
    return {"database": "ok"}

@app.get("/config/public")
async def public_config():
    """Settings the browser needs, including the configurable security line."""
    contacts = [
        {"id": "national", "label": "National emergency", "number": "112", "primary": True},
        {"id": "police", "label": "Police", "number": "191", "primary": False},
        {"id": "fire", "label": "Fire service", "number": "192", "primary": False},
        {"id": "ambulance", "label": "Ambulance", "number": "193", "primary": False},
    ]
    if config.CAMPUS_SECURITY_PHONE:
        contacts.insert(1, {
            "id": "campus_security",
            "label": config.CAMPUS_SECURITY_LABEL,
            "number": config.CAMPUS_SECURITY_PHONE,
            "primary": True,
        })
    return {"emergency_contacts": contacts}

@app.get("/bounds")
async def bounds():
    return config.service_bounds()

@app.get("/locations")
def list_locations():
    require_service()
    return state.locations

@app.post("/route")
def calculate_route(request: RouteRequest):
    service = require_service()
    try:
        plan = service.plan(
            request.origin_lat,
            request.origin_lon,
            request.dest_lat,
            request.dest_lon,
            transport_mode=request.transport_mode,
            objective=request.objective,
            traffic_level=request.traffic_level,
            algorithm=request.algorithm,
            destination_name=request.destination_name,
            hazards=current_hazards(),
        )
    except SnapError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NoRouteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "objective": request.objective,
        "transport_mode": request.transport_mode,
        "traffic_level": request.traffic_level,
        "distance_km": plan.distance_km,
        "time_min": plan.time_min,
        "path": plan.path,
        "instructions": plan.instructions,
        "snap": plan.snap,
        "diagnostics": plan.diagnostics,
        "hazards": plan.hazards,
    }

@app.post("/nearest")
def nearest_facilities(request: NearestRequest):
    service = require_service()
    candidates = [loc for loc in state.locations if loc.get("category") == request.category]

    wanted = None
    if request.subtype:
        wanted = places.subtype_types(request.category, request.subtype)
        if wanted is None:
            raise HTTPException(
                status_code=422,
                detail=f"{request.subtype!r} is not a kind of {request.category}.")
        candidates = [loc for loc in candidates if loc.get("type") in wanted]

    if not candidates:
        label = f"{request.subtype} " if request.subtype else ""
        raise HTTPException(
            status_code=404,
            detail=f"No {label}{request.category} facilities are mapped in the service area.",
        )
    try:
        results = service.nearest_facilities(
            request.lat,
            request.lon,
            candidates,
            transport_mode=request.transport_mode,
            traffic_level=request.traffic_level,
            limit=request.limit,
            hazards=current_hazards(),
        )
    except SnapError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"category": request.category, "subtype": request.subtype,
            "results": results}

@app.get("/categories")
def list_categories():
    require_service()
    counts = {}
    for entry in state.locations:
        counts[entry["category"]] = counts.get(entry["category"], 0) + 1

    def subtypes_for(name: str) -> list:
        options = []
        for option in places.SUBTYPES.get(name, ()):
            wanted = set(option["types"])
            options.append({
                "key": option["key"],
                "label": option["label"],
                "types": sorted(wanted),
                "count": sum(1 for entry in state.locations
                             if entry["category"] == name and entry.get("type") in wanted),
            })
        return options

    return [
        {
            "category": name,
            "label": places.CATEGORY_LABELS[name],
            "subtypes": subtypes_for(name),
            "count": counts.get(name, 0),
        }
        for name in data_loader.CATEGORY_NAMES
    ]

class NewPlaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=places.MAX_NAME_LENGTH)
    category: EmergencyCategory
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    type: Optional[str] = Field(default=None, max_length=60)
    phone: Optional[str] = Field(default=None, max_length=40)
    opening_hours: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=300)

_place_write_lock = threading.Lock()

@app.post("/places", status_code=201)
def create_place(request: NewPlaceRequest, response: Response,
                 authorization: Optional[str] = Header(default=None),
                 x_acting_role: Optional[str] = Header(default=None)):
    """Add a campus place OSM does not have. Mappers and admins, and attributable."""
    editor = require_place_author(authorization, x_acting_role)

    service = require_service()
    payload = request.model_dump()

    errors = places.validate_new_place(payload, config.service_bounds())
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    walkable = service.index.nearest_edge(
        payload["lat"], payload["lon"], WALK, config.PIN_SNAP_TOLERANCE_M)
    if walkable is None:
        raise HTTPException(
            status_code=422,
            detail=(f"That point is more than {int(config.PIN_SNAP_TOLERANCE_M)} m from "
                    "any path, so no route could reach it. Place it nearer a road."),
        )

    with _place_write_lock:
        return _store_place(payload, editor, service, response, walkable)

def _store_place(payload: dict, editor: dict, service, response: Response,
                 walkable) -> dict:
    """Serialised so the duplicate check, the write and the version bump are one unit."""
    name_key = places.normalise_name(payload["name"])
    for entry in state.locations:
        if places.normalise_name(entry["name"]) != name_key:
            continue
        if haversine_m(payload["lat"], payload["lon"], entry["lat"],
                       entry["lon"]) <= config.PLACE_DUPLICATE_RADIUS_M:
            raise HTTPException(
                status_code=409,
                detail=f"{entry['name']} already exists within "
                       f"{int(config.PLACE_DUPLICATE_RADIUS_M)} m of that point.",
            )

    taken = {entry["id"] for entry in state.locations}
    place = {
        "id": places.slug_id(payload["name"], taken),
        "created_by": editor["id"],
        "name": payload["name"].strip(),
        "category": payload["category"],
        "type": payload["type"] or payload["category"],
        "lat": payload["lat"],
        "lon": payload["lon"],
        "phone": payload["phone"],
        "opening_hours": payload["opening_hours"],
        "description": payload["description"],
        "source": "curated",
    }

    place = data_loader.place_store().add(place)
    state.locations = data_loader.get_locations(state.osm_locations)
    state.places_version += 1
    response.headers["Location"] = f"/locations#{place['id']}"

    drivable = service.index.nearest_edge(
        payload["lat"], payload["lon"], DRIVE, config.PIN_SNAP_TOLERANCE_M)

    return {
        "place": place,
        "places_version": state.places_version,
        "drive_reachable": drivable is not None,
        "snap_m": round(walkable.distance_m, 1),
    }

class CoverageRequest(BaseModel):
    categories: Optional[list] = None
    transport_mode: TransportMode = "drive"
    traffic_level: TrafficLevel = "normal"

@app.post("/coverage")
def response_coverage(request: CoverageRequest):
    """Travel time from the nearest emergency facility to every road."""
    service = require_service()

    requested = request.categories or ["medical", "police", "fire_station"]
    unknown = [c for c in requested if c not in data_loader.CATEGORY_NAMES]
    if unknown:
        raise HTTPException(status_code=422,
                            detail=f"Unknown categories: {', '.join(unknown)}")

    wanted = set(requested)
    hazards = current_hazards()
    key = (tuple(sorted(wanted)), request.transport_mode, request.traffic_level,
           state.places_version, tuple((h.id, h.status) for h in hazards))
    cached = _coverage_cache.get(key)
    if cached is not None:
        return cached

    facilities = [loc for loc in state.locations if loc["category"] in wanted]
    if not facilities:
        raise HTTPException(status_code=404,
                            detail="No facilities are mapped for those categories.")

    try:
        result = service.coverage(
            facilities,
            transport_mode=request.transport_mode,
            traffic_level=request.traffic_level,
            hazards=hazards,
        )
    except NoRouteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result["categories"] = sorted(wanted)
    if len(_coverage_cache) >= _COVERAGE_CACHE_LIMIT:
        _coverage_cache.clear()
    _coverage_cache[key] = result
    return result

def within_service_area(lat: float, lon: float) -> bool:
    bounds = config.service_bounds()
    return (bounds["min_lat"] <= lat <= bounds["max_lat"]
            and bounds["min_lon"] <= lon <= bounds["max_lon"])

def _bearer(authorization: Optional[str]) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()

def current_student(authorization: Optional[str], acting_role: Optional[str] = None):
    try:
        student = auth.student_for_token(_bearer(authorization))
    except auth.AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    return _acting(student, acting_role)

def _acting(student, acting_role: Optional[str]):
    """Let an account view the app as a lesser role. Never as a greater one."""
    if student is None or not acting_role:
        return student

    wanted = acting_role.strip().lower()
    if wanted not in accounts.ROLES:
        raise HTTPException(status_code=422,
                            detail=f"Unknown role: {acting_role!r}.")
    if not accounts.may_act_as(student.get("roles") or student["role"], wanted):
        raise HTTPException(
            status_code=403,
            detail="You can only act as a role with the same or less access than your own.")

    return {**student,
            "roles": list(accounts.normalise_roles([wanted])),
            "role": wanted,
            "real_roles": student.get("roles") or [student["role"]],
            "real_role": student["role"]}

def require_student(authorization: Optional[str], acting_role: Optional[str] = None) -> dict:
    student = current_student(authorization, acting_role)
    if student is None:
        raise HTTPException(status_code=401, detail="Sign in to do that.")
    return student

def require_can(capability: str, authorization: Optional[str],
                acting_role: Optional[str] = None) -> dict:
    """The account, provided the role it is acting as holds this permission."""
    student = require_student(authorization, acting_role)
    if not accounts.can(student.get("roles") or student["role"], capability):
        raise HTTPException(status_code=403,
                            detail=accounts.DENIED.get(capability, "You cannot do that."))
    return student

def require_place_author(authorization: Optional[str],
                         acting_role: Optional[str] = None) -> dict:
    return require_can(accounts.ADD_PLACES, authorization, acting_role)

def require_place_editor(authorization: Optional[str],
                         acting_role: Optional[str] = None) -> dict:
    return require_can(accounts.EDIT_PLACES, authorization, acting_role)

def require_responder(authorization: Optional[str],
                      acting_role: Optional[str] = None) -> dict:
    return require_can(accounts.RESOLVE_INCIDENTS, authorization, acting_role)

def require_admin(authorization: Optional[str],
                  acting_role: Optional[str] = None) -> dict:
    return require_can(accounts.MANAGE_ROLES, authorization, acting_role)

@app.get("/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None),
            x_acting_role: Optional[str] = Header(default=None)):
    """The signed-in student, created on first use from the verified Supabase account.

    Returns `null` rather than an error when there is no database: no accounts can
    exist, so "nobody is signed in" is the truthful answer.
    """
    problem = config.auth_misconfigured()
    if problem:
        raise HTTPException(status_code=503, detail=problem)
    return {"student": current_student(authorization, x_acting_role)}

@app.post("/auth/forget", status_code=204)
def auth_forget(authorization: Optional[str] = Header(default=None)):
    """Drop a token from the verification cache, so signing out takes effect at once."""
    token = _bearer(authorization)
    if token:
        supabase_auth.forget(token)
    return Response(status_code=204)

IncidentKind = Literal["suspicious_activity", "accident", "flooding", "blocked_road"]
assert set(get_args(IncidentKind)) == set(incidents.KINDS)

class ReportIncidentRequest(BaseModel):
    kind: IncidentKind
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    note: Optional[str] = Field(default=None, max_length=incidents.MAX_NOTE_LENGTH)

class OverrideRequest(BaseModel):
    override: Literal["verified", "false"]

@app.get("/incidents")
def list_incidents():
    """Live hazards. Expired and resolved clusters are filtered out on read."""
    return {"kinds": [{"kind": kind, "label": incidents.KIND_LABELS[kind],
                       "ttl_hours": hours}
                      for kind, hours in incidents.KIND_TTL_HOURS.items()],
            "incidents": incidents.live()}

@app.post("/incidents", status_code=201)
def report_incident(payload: ReportIncidentRequest,
                    authorization: Optional[str] = Header(default=None),
                    x_acting_role: Optional[str] = Header(default=None)):
    """Report a hazard. Requires an account so every report is accountable."""
    student = require_student(authorization, x_acting_role)
    if not within_service_area(payload.lat, payload.lon):
        raise HTTPException(
            status_code=422,
            detail="Reports are only accepted from on or near the KNUST campus.")
    try:
        result = incidents.report(student, payload.kind, payload.lat, payload.lon,
                                  payload.note)
    except incidents.IncidentError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    forget_hazards()
    return result

@app.post("/incidents/{cluster_id}/override")
def override_incident(cluster_id: int, payload: OverrideRequest,
                      authorization: Optional[str] = Header(default=None),
                      x_acting_role: Optional[str] = Header(default=None)):
    require_responder(authorization, x_acting_role)
    try:
        result = incidents.set_override(cluster_id, payload.override)
    except incidents.IncidentError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    forget_hazards()
    return result

@app.post("/incidents/{cluster_id}/resolve", status_code=204)
def resolve_incident(cluster_id: int,
                     authorization: Optional[str] = Header(default=None),
                     x_acting_role: Optional[str] = Header(default=None)):
    require_responder(authorization, x_acting_role)
    try:
        incidents.resolve(cluster_id)
    except incidents.IncidentError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    forget_hazards()
    return Response(status_code=204)

AccountRole = Literal["student", "security", "mapper", "admin"]

class RoleRequest(BaseModel):
    roles: list[AccountRole] = Field(..., min_length=1, max_length=len(accounts.ROLES))

class EditPlaceRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1,
                                max_length=places.MAX_NAME_LENGTH)
    category: Optional[EmergencyCategory] = None
    type: Optional[str] = Field(default=None, max_length=60)
    phone: Optional[str] = Field(default=None, max_length=40)
    opening_hours: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=300)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)

@app.get("/admin/students")
def admin_students(authorization: Optional[str] = Header(default=None),
                   x_acting_role: Optional[str] = Header(default=None)):
    """Every account, with its role and current report weight."""
    require_admin(authorization, x_acting_role)
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, role, trust, knust_verified, created_at, roles"
                " FROM students ORDER BY created_at DESC")
            rows = cur.fetchall()
        conn.commit()

    return {"students": [
        {"id": row[0], "email": row[1],
         "roles": list(accounts.normalise_roles(row[6])),
         "role": accounts.primary_role(row[6]), "trust": float(row[3]),
         "knust_verified": bool(row[4]), "created_at": row[5].isoformat(),
         "owner": row[1] in config.ADMIN_EMAILS}
        for row in rows
    ]}

@app.post("/admin/students/{student_id}/role")
def admin_set_role(student_id: int, payload: RoleRequest,
                   authorization: Optional[str] = Header(default=None),
                   x_acting_role: Optional[str] = Header(default=None)):
    """Assign the set of roles. An admin cannot remove their own admin access."""
    editor = require_admin(authorization, x_acting_role)
    wanted = accounts.normalise_roles(payload.roles)
    primary = accounts.primary_role(wanted)

    if student_id == editor["id"] and "admin" not in wanted:
        raise HTTPException(
            status_code=409,
            detail="You cannot remove your own admin access. Ask another admin.")

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE students SET role = %s, roles = %s"
                        " WHERE id = %s AND (%s = 'admin' OR NOT email = ANY(%s))"
                        " RETURNING id, email, role, roles",
                        (primary, list(wanted), student_id, primary,
                         list(config.ADMIN_EMAILS)))
            row = cur.fetchone()
            if row is None:
                cur.execute("SELECT 1 FROM students WHERE id = %s", (student_id,))
                exists = cur.fetchone() is not None
        conn.commit()

    if row is None and exists:
        raise HTTPException(
            status_code=409,
            detail="That is an owner account, so it always stays admin.")
    if row is None:
        raise HTTPException(status_code=404, detail="No such account.")

    logger.info("Admin %s set %s to %s", editor["email"], row[1], list(row[3]))
    return {"id": row[0], "email": row[1], "role": row[2],
            "roles": list(accounts.normalise_roles(row[3]))}

@app.get("/incidents/queue")
def incident_queue(authorization: Optional[str] = Header(default=None),
                   x_acting_role: Optional[str] = Header(default=None)):
    """Every report, including expired, resolved and ones marked false."""
    require_responder(authorization, x_acting_role)
    return {"incidents": incidents.all_clusters()}

@app.patch("/places/{place_id:path}")
def edit_place(place_id: str, payload: EditPlaceRequest,
               authorization: Optional[str] = Header(default=None),
               x_acting_role: Optional[str] = Header(default=None)):
    """Correct a curated place."""
    require_place_editor(authorization, x_acting_role)
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to change.")

    with _place_write_lock:
        if not data_loader.place_store().update(place_id, changes):
            raise HTTPException(status_code=404, detail="No such curated place.")
        state.locations = data_loader.get_locations(state.osm_locations)
        state.places_version += 1

    return {"id": place_id, "changed": sorted(changes),
            "places_version": state.places_version}

@app.delete("/places/{place_id:path}", status_code=204)
def remove_place(place_id: str,
                 authorization: Optional[str] = Header(default=None),
                 x_acting_role: Optional[str] = Header(default=None)):
    """Remove a curated place that should not be on the map."""
    require_place_editor(authorization, x_acting_role)
    with _place_write_lock:
        if not data_loader.place_store().remove(place_id):
            raise HTTPException(status_code=404, detail="No such curated place.")
        state.locations = data_loader.get_locations(state.osm_locations)
        state.places_version += 1
    return Response(status_code=204)
