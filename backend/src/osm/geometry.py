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
