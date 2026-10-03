"""Reported incidents as routing hazards: roads near one cost more to use.

A hazard never closes a road outright. It multiplies the cost of nearby edges,
so the search goes around it whenever a reasonable detour exists, and still
finds a route, flagged, when the hazard sits on the only way through. In an
emergency a warned route is better than none.

Only corroborated incidents count: a lone report changes nothing, so one prank
cannot reroute anyone. A single credible witness still shows on the map and in
the security queue as "likely" -- that is a warning, not grounds to divert
traffic. Security verifying it makes it count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .snapping import project_onto_edge
from .weights import ALL_MODES, BIKE, DRIVE, WALK

HAZARD_RADIUS_M = 40.0

ROAD_HAZARDS = frozenset({"blocked_road", "accident"})
ROAD_MARGIN_M = 10.0

POLICY: dict[str, dict[str, dict[int, float]]] = {
    "blocked_road": {
        "confirmed": {DRIVE: 50.0, BIKE: 50.0, WALK: 3.0},
        "likely": {DRIVE: 4.0, BIKE: 4.0, WALK: 1.5},
    },
    "flooding": {
        "confirmed": {DRIVE: 10.0, BIKE: 10.0, WALK: 10.0},
        "likely": {DRIVE: 3.0, BIKE: 3.0, WALK: 3.0},
    },
    "accident": {
        "confirmed": {DRIVE: 3.0, BIKE: 1.5},
        "likely": {DRIVE: 1.5},
    },
    "suspicious_activity": {
        "confirmed": {WALK: 3.0, BIKE: 2.0},
        "likely": {WALK: 1.5},
    },
}

_STATUS_ALIASES = {"verified": "confirmed"}

MIN_REPORTS_FOR_LIKELY = 2

def _report_count(incident: dict) -> int:
    """Only a known-single report is filtered; an absent count is trusted."""
    try:
        return int(incident.get("reports", MIN_REPORTS_FOR_LIKELY))
    except (TypeError, ValueError):
        return MIN_REPORTS_FOR_LIKELY

@dataclass(frozen=True)
class Hazard:
    id: int
    kind: str
    label: str
    status: str
    lat: float
    lon: float
    factors: tuple

    def factor(self, mode_bit: int) -> float:
        for bit, value in self.factors:
            if bit == mode_bit:
                return value
        return 1.0

    def summary(self) -> dict:
        return {"id": self.id, "kind": self.kind, "label": self.label,
                "status": self.status}

def hazards_from_incidents(incidents: Iterable[dict]) -> tuple:
    """Hazards for the incidents that routing should respect, as a hashable tuple."""
    found = []
    for incident in incidents:
        status = _STATUS_ALIASES.get(incident.get("status"), incident.get("status"))
        factors = POLICY.get(incident.get("kind"), {}).get(status)
        if not factors:
            continue
        if status == "likely" and _report_count(incident) < MIN_REPORTS_FOR_LIKELY:
            continue
        try:
            lat, lon = float(incident["lat"]), float(incident["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        found.append(Hazard(
            id=incident.get("id"),
            kind=incident["kind"],
            label=incident.get("label") or incident["kind"],
            status=status,
            lat=lat,
            lon=lon,
            factors=tuple(sorted(factors.items())),
        ))
    return tuple(found)

class HazardMap:
    """Which hazards touch which edges, worked out lazily for one request."""

    __slots__ = ("hazards", "_radius", "_near")

    def __init__(self, hazards: Iterable[Hazard], index=None) -> None:
        self.hazards = tuple(hazards)
        self._radius = {id(hazard): self._reach(hazard, index) for hazard in self.hazards}
        self._near: dict[int, tuple] = {}

    @staticmethod
    def _reach(hazard: Hazard, index) -> float:
        """How far from the report a hazard applies, in metres."""
        if hazard.kind not in ROAD_HAZARDS or index is None:
            return HAZARD_RADIUS_M
        road = index.nearest_edge(hazard.lat, hazard.lon, ALL_MODES, HAZARD_RADIUS_M)
        if road is None:
            return -1.0
        return min(road.distance_m + ROAD_MARGIN_M, HAZARD_RADIUS_M)

    def __bool__(self) -> bool:
        return bool(self.hazards)

    def near(self, edge) -> tuple:
        """The hazards that reach an edge."""
        key = id(edge)
        cached = self._near.get(key)
        if cached is None:
            cached = tuple(hazard for hazard in self.hazards
                           if project_onto_edge(edge, hazard.lat, hazard.lon).distance_m
                           <= self._radius[id(hazard)])
            self._near[key] = cached
        return cached

    def factor(self, edge, mode_bit: int) -> float:
        """The strongest multiplier any nearby hazard applies to this mode."""
        return max((hazard.factor(mode_bit) for hazard in self.near(edge)), default=1.0)

    def wrap(self, weight_fn: Callable, mode_bit: int) -> Callable:
        """`weight_fn` with hazard multipliers applied; unchanged when there are none."""
        if not self.hazards:
            return weight_fn

        def with_hazards(edge) -> float:
            return weight_fn(edge) * self.factor(edge, mode_bit)
        return with_hazards

    def crossed(self, edges: Iterable, mode_bit: int) -> list:
        """The hazards a finished route still passes, for warning the traveller."""
        seen: dict = {}
        for edge in edges:
            for hazard in self.near(edge):
                if hazard.factor(mode_bit) > 1.0:
                    seen.setdefault(hazard.id, hazard)
        return [hazard.summary() for hazard in seen.values()]
