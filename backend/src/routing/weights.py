"""Travel-mode permissions, speeds, congestion, and edge cost functions."""

from __future__ import annotations

import re
from typing import Callable, Optional

DRIVE = 1 << 0
BIKE = 1 << 1
WALK = 1 << 2

ALL_MODES = DRIVE | BIKE | WALK
MODE_BITS: dict[str, int] = {"drive": DRIVE, "bike": BIKE, "walk": WALK}

WALK_SPEED_KPH = 5.0
BIKE_SPEED_KPH = 15.0
DEFAULT_DRIVE_KPH = 25.0

MIN_COST = 1e-6

_PERMISSIONS: dict[str, int] = {
    "motorway": DRIVE,
    "motorway_link": DRIVE,
    "trunk": DRIVE,
    "trunk_link": DRIVE,
    "busway": DRIVE,
    "primary": ALL_MODES,
    "primary_link": ALL_MODES,
    "secondary": ALL_MODES,
    "secondary_link": ALL_MODES,
    "tertiary": ALL_MODES,
    "tertiary_link": ALL_MODES,
    "residential": ALL_MODES,
    "unclassified": ALL_MODES,
    "living_street": ALL_MODES,
    "service": ALL_MODES,
    "road": ALL_MODES,
    "pedestrian": BIKE | WALK,
    "cycleway": BIKE | WALK,
    "path": BIKE | WALK,
    "track": BIKE | WALK,
    "footway": WALK,
    "bridleway": WALK,
    "steps": WALK,
    "corridor": WALK,
    "platform": WALK,
}

_UNROUTABLE = frozenset({
    "construction", "proposed", "planned", "abandoned", "disused",
    "razed", "escape", "raceway", "rest_area", "services", "elevator",
})

_DEFAULT_PERMISSION = ALL_MODES

_CLASS_SPEED_KPH: dict[str, float] = {
    "motorway": 80.0, "motorway_link": 60.0,
    "trunk": 60.0, "trunk_link": 50.0,
    "primary": 40.0, "primary_link": 35.0,
    "secondary": 35.0, "secondary_link": 30.0,
    "tertiary": 30.0, "tertiary_link": 25.0,
    "busway": 30.0,
    "residential": 25.0,
    "unclassified": 25.0,
    "road": 25.0,
    "living_street": 15.0,
    "service": 15.0,
}

_WALK_PENALTY: dict[str, float] = {"steps": 2.5, "track": 1.3, "path": 1.1}
_BIKE_PENALTY: dict[str, float] = {"track": 1.25, "path": 1.15}

_TRAFFIC_SENSITIVITY: dict[str, float] = {
    "motorway": 1.0, "motorway_link": 1.0,
    "trunk": 1.0, "trunk_link": 1.0,
    "primary": 1.0, "primary_link": 0.9,
    "secondary": 0.85, "secondary_link": 0.8,
    "tertiary": 0.6, "tertiary_link": 0.6,
    "busway": 0.5,
    "residential": 0.35,
    "unclassified": 0.35,
    "living_street": 0.2,
    "service": 0.2,
}
_DEFAULT_SENSITIVITY = 0.4

_TRAFFIC_INTENSITY: dict[str, float] = {"low": -0.20, "normal": 0.0, "heavy": 0.90}

_MIN_TRAFFIC_MULTIPLIER = 0.5

_ACCESS_KEYS: dict[int, tuple[str, ...]] = {
    DRIVE: ("access", "vehicle", "motor_vehicle", "motorcar"),
    BIKE: ("access", "vehicle", "bicycle"),
    WALK: ("access", "foot"),
}
_ACCESS_DENIED = frozenset({"no", "discouraged", "use_sidepath"})
_ACCESS_GRANTED = frozenset({"yes", "designated", "permissive", "official"})
_ACCESS_RESTRICTED = frozenset({
    "private", "customers", "delivery", "destination", "agricultural", "forestry",
})

PRIVATE_PENALTY = 4.0

_SURFACE_CLASS: dict[str, str] = {
    **dict.fromkeys(("asphalt", "concrete", "concrete:plates", "concrete:lanes",
                     "paved", "paving_stones", "sett", "cobblestone", "metal",
                     "wood", "chipseal"), "paved"),
    **dict.fromkeys(("compacted", "fine_gravel"), "compacted"),
    **dict.fromkeys(("unpaved", "ground", "dirt", "earth", "gravel", "pebblestone",
                     "sand", "mud", "grass", "grass_paver", "rock", "laterite"),
                    "unpaved"),
}
_SURFACE_PENALTY: dict[str, dict[str, float]] = {
    "walk": {"unpaved": 1.1},
    "bike": {"compacted": 1.15, "unpaved": 1.35},
}
_SURFACE_DRIVE_CAP_KPH: dict[str, float] = {"compacted": 30.0, "unpaved": 20.0}

_ROUGH_SMOOTHNESS = frozenset({"bad", "very_bad", "horrible", "very_horrible", "impassable"})
_ROUGH_BIKE_PENALTY = 1.3
_ROUGH_DRIVE_CAP_KPH = 15.0

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_UNPARSEABLE_MAXSPEED = frozenset({"none", "signals", "variable", "unknown", "walk", "default"})

def permissions_for(highway: str) -> int:
    """Bitmask of modes allowed on a road class; 0 means not routable."""
    if highway in _UNROUTABLE:
        return 0
    return _PERMISSIONS.get(highway, _DEFAULT_PERMISSION)

def tag_text(tags: dict, key: str) -> str:
    """A tag's first value, lower-cased; '' when absent."""
    value = tags.get(key)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return ""
    return str(value).split(";")[0].strip().lower()

def access_for(tags: dict) -> tuple[int, int]:
    """(allowed, restricted) mode bitmasks: road class refined by OSM access tags.

    `restricted` marks modes that may use the road only with permission
    (access=private and similar). Routing avoids those rather than forbidding
    them, so a place inside a compound stays reachable.
    """
    highway = tag_text(tags, "highway") or "unclassified"
    baseline = permissions_for(highway)
    if not baseline:
        return 0, 0

    allowed = restricted = 0
    for bit, keys in _ACCESS_KEYS.items():
        verdict = None
        for key in keys:
            value = tag_text(tags, key)
            if value in _ACCESS_DENIED:
                verdict = "no"
            elif value in _ACCESS_GRANTED:
                verdict = "yes"
            elif value in _ACCESS_RESTRICTED:
                verdict = "restricted"
        if verdict == "no":
            continue
        if verdict is None and not (baseline & bit):
            continue
        allowed |= bit
        if verdict == "restricted":
            restricted |= bit
    return allowed, restricted

def directional_maxspeed(tags: dict, direction: str):
    """The raw maxspeed for one direction: maxspeed:<direction>, else maxspeed."""
    return tags.get(f"maxspeed:{direction}") or tags.get("maxspeed")

def parse_maxspeed(raw) -> Optional[float]:
    """Resolve an OSM `maxspeed` tag to km/h, or None if unusable."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        for candidate in raw:
            parsed = parse_maxspeed(candidate)
            if parsed is not None:
                return parsed
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if raw > 0 else None

    text = str(raw).strip().lower()
    if not text:
        return None

    first = re.split(r"[;|,]", text)[0].strip()
    if not first or first in _UNPARSEABLE_MAXSPEED:
        return None

    match = _NUMBER.search(first)
    if match is None:
        return None

    value = float(match.group())
    if value <= 0:
        return None
    if "mph" in first:
        value *= 1.609344
    elif "knot" in first:
        value *= 1.852
    return value

def drive_speed_kph(highway: str, maxspeed_raw) -> float:
    """Driving speed for an edge: tagged value, else road class, else default."""
    tagged = parse_maxspeed(maxspeed_raw)
    if tagged is not None:
        return tagged
    return _CLASS_SPEED_KPH.get(highway, DEFAULT_DRIVE_KPH)

def base_traverse_seconds(mode: str, length_m: float, highway: str, drive_kph: float,
                          tags: Optional[dict] = None) -> float:
    """Free-flow traversal time for one edge, in seconds.

    Surface and smoothness slow walking and cycling by a factor, and cap driving
    speed. A road-class penalty and a surface penalty are not stacked: a `track`
    is already priced as rough, so the larger of the two applies.
    """
    tags = tags or {}
    surface = _SURFACE_CLASS.get(tag_text(tags, "surface"))
    rough = tag_text(tags, "smoothness") in _ROUGH_SMOOTHNESS

    if mode == "walk":
        speed_kph = WALK_SPEED_KPH
        penalty = max(_WALK_PENALTY.get(highway, 1.0),
                      _SURFACE_PENALTY["walk"].get(surface, 1.0))
    elif mode == "bike":
        speed_kph = BIKE_SPEED_KPH
        penalty = max(_BIKE_PENALTY.get(highway, 1.0),
                      _SURFACE_PENALTY["bike"].get(surface, 1.0),
                      _ROUGH_BIKE_PENALTY if rough else 1.0)
    elif mode == "drive":
        speed_kph = drive_kph
        if surface in _SURFACE_DRIVE_CAP_KPH:
            speed_kph = min(speed_kph, _SURFACE_DRIVE_CAP_KPH[surface])
        if rough:
            speed_kph = min(speed_kph, _ROUGH_DRIVE_CAP_KPH)
        speed_kph = max(speed_kph, 1.0)
        penalty = 1.0
    else:
        raise ValueError(f"unknown travel mode: {mode!r}")
    return max((length_m / (speed_kph / 3.6)) * penalty, MIN_COST)

def traffic_multiplier(highway: str, traffic_level: str) -> float:
    """Per-edge congestion factor for driving."""
    intensity = _TRAFFIC_INTENSITY.get(traffic_level, 0.0)
    if intensity == 0.0:
        return 1.0
    sensitivity = _TRAFFIC_SENSITIVITY.get(highway, _DEFAULT_SENSITIVITY)
    return max(_MIN_TRAFFIC_MULTIPLIER, 1.0 + sensitivity * intensity)

def _affects_travel_time(mode: str, traffic_level: str) -> bool:
    return mode == "drive" and _TRAFFIC_INTENSITY.get(traffic_level, 0.0) != 0.0

def min_traffic_multiplier(mode: str, traffic_level: str) -> float:
    """The smallest factor any edge's travel time can be scaled by at this level.

    The A* heuristic divides distance by a top speed to bound the remaining cost.
    When traffic makes edges *cheaper* than their base time, that bound has to be
    widened by this factor or the heuristic can overestimate and stop being
    admissible.
    """
    if not _affects_travel_time(mode, traffic_level):
        return 1.0
    intensity = _TRAFFIC_INTENSITY[traffic_level]
    sensitivities = (*_TRAFFIC_SENSITIVITY.values(), _DEFAULT_SENSITIVITY)
    return min(max(_MIN_TRAFFIC_MULTIPLIER, 1.0 + sensitivity * intensity)
               for sensitivity in sensitivities)

def travel_seconds(edge, mode: str, traffic_level: str) -> float:
    """Travel time for one edge. The single definition of the time cost model."""
    seconds = edge.base_seconds[MODE_BITS[mode]]
    if _affects_travel_time(mode, traffic_level):
        seconds *= traffic_multiplier(edge.highway, traffic_level)
    return seconds

def make_weight_fn(mode: str, objective: str, traffic_level: str,
                   avoid_restricted: bool = True) -> Callable:
    """Build the per-edge cost function: metres for `shortest`, seconds for `fastest`.

    With `avoid_restricted`, private roads cost PRIVATE_PENALTY times more, so a
    route uses one only when there is no reasonable public alternative. The
    penalty steers the search; reported times come from `travel_seconds`.
    """
    if mode not in MODE_BITS:
        raise ValueError(f"unknown travel mode: {mode!r}")
    if objective not in ("fastest", "shortest"):
        raise ValueError(f"unknown objective: {objective!r}")

    mode_bit = MODE_BITS[mode]
    penalty = PRIVATE_PENALTY if avoid_restricted else 1.0

    if objective == "shortest":
        def by_distance(edge) -> float:
            value = edge.length_m
            if edge.restricted & mode_bit:
                value *= penalty
            return max(value, MIN_COST)
        return by_distance

    if not _affects_travel_time(mode, traffic_level):
        def by_time(edge) -> float:
            value = edge.base_seconds[mode_bit]
            if edge.restricted & mode_bit:
                value *= penalty
            return max(value, MIN_COST)
        return by_time

    def by_time_with_traffic(edge) -> float:
        value = travel_seconds(edge, mode, traffic_level)
        if edge.restricted & mode_bit:
            value *= penalty
        return max(value, MIN_COST)
    return by_time_with_traffic
