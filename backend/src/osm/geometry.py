"""Planar geometry for OSM elements: ring area, centroid, polyline length."""

from __future__ import annotations

from math import cos, radians
from typing import Sequence

_M_PER_DEG_LAT = 111_132.0

def local_scale(lat: float) -> tuple[float, float]:
    """Metres per degree of latitude and longitude at this latitude."""
    return _M_PER_DEG_LAT, _M_PER_DEG_LAT * cos(radians(lat))

def ring_centroid(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Area-weighted centroid of a closed ring of (lat, lon) vertices."""
    ring = _closed(points)
    if len(ring) < 4:
        return _vertex_mean(points)

    lat0 = sum(p[0] for p in ring) / len(ring)
    m_lat, m_lon = local_scale(lat0)

    twice_area = 0.0
    cx = 0.0
    cy = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(ring, ring[1:]):
        x1, y1 = lon1 * m_lon, lat1 * m_lat
        x2, y2 = lon2 * m_lon, lat2 * m_lat
        cross = x1 * y2 - x2 * y1
        twice_area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross

    if abs(twice_area) < 1e-9:
        return _vertex_mean(points)

    area6 = twice_area * 3.0
    return (cy / area6) / m_lat, (cx / area6) / m_lon

def _closed(points: Sequence[tuple[float, float]]) -> list:
    ring = list(points)
    if len(ring) >= 2 and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring

def _vertex_mean(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    unique = list(dict.fromkeys(points))
    if not unique:
        raise ValueError("cannot take the centroid of an empty geometry")
    return (sum(p[0] for p in unique) / len(unique),
            sum(p[1] for p in unique) / len(unique))


def point_in_ring(lat: float, lon: float, ring: Sequence[tuple[float, float]]) -> bool:
    """Ray casting. A point exactly on an edge counts as inside."""
    points = _closed(ring)
    if len(points) < 4:
        return False
    inside = False
    for index in range(len(points) - 1):
        y1, x1 = points[index]
        y2, x2 = points[index + 1]
        if (y1 > lat) != (y2 > lat):
            span = y2 - y1
            if span == 0:
                continue
            crossing = x1 + (lat - y1) * (x2 - x1) / span
            if crossing == lon:
                return True
            if crossing > lon:
                inside = not inside
    return inside


def ring_area(points: Sequence[tuple[float, float]]) -> float:
    """Unsigned area in square metres, for choosing the largest of several rings."""
    closed = _closed(points)
    if len(closed) < 4:
        return 0.0
    mean_lat = sum(point[0] for point in closed[:-1]) / (len(closed) - 1)
    lat_m, lon_m = local_scale(mean_lat)
    total = 0.0
    for index in range(len(closed) - 1):
        y1, x1 = closed[index]
        y2, x2 = closed[index + 1]
        total += (x1 * lon_m) * (y2 * lat_m) - (x2 * lon_m) * (y1 * lat_m)
    return abs(total) / 2.0
