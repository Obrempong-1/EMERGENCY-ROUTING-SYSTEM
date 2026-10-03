"""Projecting a coordinate onto the nearest road, rather than the nearest junction."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, floor, inf, radians
from typing import Iterator, Optional

from .graph import Edge, RouteGraph, haversine_m

_M_PER_DEG_LAT = 111_132.0
_DEFAULT_CELL_M = 120.0
_MAX_RINGS = 48

@dataclass
class Projection:
    __slots__ = ("edge", "lat", "lon", "distance_m", "along_m")

    edge: Edge
    lat: float
    lon: float
    distance_m: float
    along_m: float

def _road_key(edge) -> tuple:
    """Identity of the physical road, shared by both directions of a two-way street."""
    tail, head = edge.from_node, edge.to_node
    low, high = (tail, head) if tail <= head else (head, tail)
    return (low, high, edge.highway, edge.name)

def project_onto_edge(edge: Edge, lat: float, lon: float) -> Projection:
    """Nearest point on an edge's geometry to (lat, lon)."""
    m_lat = _M_PER_DEG_LAT
    m_lon = _M_PER_DEG_LAT * cos(radians(lat))
    px, py = lon * m_lon, lat * m_lat

    best_distance = inf
    best_lat = best_lon = 0.0
    best_along = 0.0
    travelled = 0.0

    for (alat, alon), (blat, blon) in zip(edge.geometry, edge.geometry[1:]):
        ax, ay = alon * m_lon, alat * m_lat
        bx, by = blon * m_lon, blat * m_lat
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy

        if span == 0.0:
            t = 0.0
        else:
            t = ((px - ax) * dx + (py - ay) * dy) / span
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)

        cx, cy = ax + t * dx, ay + t * dy
        distance = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

        if distance < best_distance:
            best_distance = distance
            best_lat, best_lon = cy / m_lat, cx / m_lon
            best_along = travelled + haversine_m(alat, alon, best_lat, best_lon)

        travelled += haversine_m(alat, alon, blat, blon)

    return Projection(edge, best_lat, best_lon, best_distance, best_along)

def split_geometry(edge: Edge, lat: float, lon: float, along_m: float) -> tuple:
    """Geometry of the edge before and after the projection point."""
    head: list = []
    tail: list = []
    travelled = 0.0
    crossed = False

    for index, (plat, plon) in enumerate(edge.geometry):
        if index > 0:
            previous = edge.geometry[index - 1]
            travelled += haversine_m(previous[0], previous[1], plat, plon)
        if not crossed and travelled >= along_m:
            crossed = True
            head.append((lat, lon))
            tail.append((lat, lon))
        (tail if crossed else head).append((plat, plon))

    if not crossed:
        head.append((lat, lon))
        tail = [(lat, lon), edge.geometry[-1]]
    if len(head) < 2:
        head = [edge.geometry[0], (lat, lon)]
    if len(tail) < 2:
        tail = [(lat, lon), edge.geometry[-1]]
    return tuple(head), tuple(tail)

def slice_geometry(edge: Edge, start: Projection, end: Projection) -> tuple:
    """Geometry of an edge between two projections, assuming start precedes end."""
    points = [(start.lat, start.lon)]
    travelled = 0.0
    for index, (plat, plon) in enumerate(edge.geometry):
        if index > 0:
            previous = edge.geometry[index - 1]
            travelled += haversine_m(previous[0], previous[1], plat, plon)
        if start.along_m < travelled < end.along_m:
            points.append((plat, plon))
    points.append((end.lat, end.lon))
    if len(points) < 2:
        return ((start.lat, start.lon), (end.lat, end.lon))
    return tuple(points)

class EdgeIndex:

    __slots__ = ("_cells", "_cell_m", "_lat_step", "_lon_step")

    def __init__(self, graph: RouteGraph, cell_m: float = _DEFAULT_CELL_M) -> None:
        if cell_m <= 0:
            raise ValueError("cell_m must be positive")

        self._cell_m = cell_m
        latitudes = [lat for lat, _ in graph.nodes.values()]
        mean_lat = sum(latitudes) / len(latitudes) if latitudes else 0.0
        self._lat_step = cell_m / _M_PER_DEG_LAT
        self._lon_step = cell_m / max(_M_PER_DEG_LAT * cos(radians(mean_lat)), 1.0)

        self._cells: dict[tuple[int, int], list] = {}
        for edges in graph.adj.values():
            for edge in edges:
                for cell in self._covered_cells(edge.geometry):
                    self._cells.setdefault(cell, []).append(edge)

    def _covered_cells(self, geometry) -> set:
        """Every cell any vertex falls in, plus the cells between consecutive ones."""
        cells = set()
        for (alat, alon), (blat, blon) in zip(geometry, geometry[1:]):
            ai, aj = self._cell_of(alat, alon)
            bi, bj = self._cell_of(blat, blon)
            for i in range(min(ai, bi), max(ai, bi) + 1):
                for j in range(min(aj, bj), max(aj, bj) + 1):
                    cells.add((i, j))
        if not cells and geometry:
            cells.add(self._cell_of(geometry[0][0], geometry[0][1]))
        return cells

    def _cell_of(self, lat: float, lon: float) -> tuple[int, int]:
        return floor(lat / self._lat_step), floor(lon / self._lon_step)

    def nearest_edge(
        self,
        lat: float,
        lon: float,
        mode_bit: int,
        max_distance_m: float,
    ) -> Optional[Projection]:
        """Closest permitted road to the point, or None beyond `max_distance_m`."""
        candidates = self.nearest_edges(lat, lon, mode_bit, max_distance_m, limit=1)
        return candidates[0] if candidates else None

    def nearest_edges(
        self,
        lat: float,
        lon: float,
        mode_bit: int,
        max_distance_m: float,
        limit: int = 4,
    ) -> list:
        """The `limit` nearest permitted roads, in ascending distance.

        Distinct *roads*, not distinct edges: a two-way street is stored as two
        directed edges with identical geometry, so counting both would halve the
        number of genuinely different placements a caller can retry.
        """
        if max_distance_m <= 0 or not self._cells or limit < 1:
            return []

        rings_needed = min(int(max_distance_m / self._cell_m) + 1, _MAX_RINGS)
        centre_i, centre_j = self._cell_of(lat, lon)
        found: list = []
        seen: set = set()
        best_distance = inf

        for ring in range(rings_needed + 1):
            if found and best_distance <= (ring - 1) * self._cell_m and len(found) >= limit:
                break
            for edge in self._ring_edges(centre_i, centre_j, ring):
                if not (edge.allowed & mode_bit):
                    continue
                key = _road_key(edge)
                if key in seen:
                    continue
                seen.add(key)
                candidate = project_onto_edge(edge, lat, lon)
                if candidate.distance_m <= max_distance_m:
                    found.append(candidate)
                    best_distance = min(best_distance, candidate.distance_m)

        found.sort(key=lambda projection: projection.distance_m)
        return found[:limit]

    def _ring_edges(self, centre_i: int, centre_j: int, ring: int) -> Iterator:
        cells = self._cells
        if ring == 0:
            yield from cells.get((centre_i, centre_j), ())
            return
        for offset in range(-ring, ring + 1):
            yield from cells.get((centre_i - ring, centre_j + offset), ())
            yield from cells.get((centre_i + ring, centre_j + offset), ())
        for offset in range(-ring + 1, ring):
            yield from cells.get((centre_i + offset, centre_j - ring), ())
            yield from cells.get((centre_i + offset, centre_j + ring), ())
