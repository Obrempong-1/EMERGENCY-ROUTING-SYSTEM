"""Turn raw Overpass elements into road segments and placed facilities."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Iterator, Optional

from .geometry import ring_centroid

logger = logging.getLogger(__name__)

_ONEWAY_FORWARD = frozenset({"yes", "true", "1"})
_ONEWAY_REVERSE = frozenset({"-1", "reverse"})
_ONEWAY_NEGATIVE = frozenset({"no", "false", "0"})
_IMPLIED_ONEWAY_HIGHWAY = frozenset({"motorway", "motorway_link", "trunk_link"})
_IMPLIED_ONEWAY_JUNCTION = frozenset({"roundabout", "circular"})

@dataclass
class Segment:
    """A stretch of one OSM way running between two junctions."""

    __slots__ = ("start", "end", "geometry", "tags", "forward", "backward")

    start: int
    end: int
    geometry: tuple
    tags: dict
    forward: bool
    backward: bool

@dataclass
class Facility:
    __slots__ = ("osm_id", "name", "tags", "lat", "lon")

    osm_id: str
    name: str
    tags: dict
    lat: float
    lon: float

def index_nodes(elements: list) -> dict:
    """{node id: (lat, lon)} for every node element present."""
    nodes = {}
    for element in elements:
        if element.get("type") != "node":
            continue
        try:
            nodes[int(element["id"])] = (float(element["lat"]), float(element["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
    return nodes

def _ways(elements: list) -> Iterator[tuple]:
    for element in elements:
        if element.get("type") != "way":
            continue
        refs = element.get("nodes") or []
        if len(refs) < 2:
            continue
        yield int(element["id"]), [int(r) for r in refs], element.get("tags") or {}

def road_segments(elements: list, nodes: dict) -> list:
    """Split every highway way at its junctions and return the resulting segments."""
    highway_ways = [(wid, refs, tags) for wid, refs, tags in _ways(elements)
                    if tags.get("highway")]

    usage = Counter()
    for _wid, refs, _tags in highway_ways:
        for ref in set(refs):
            usage[ref] += 1

    segments: list[Segment] = []
    missing = 0

    for _wid, refs, tags in highway_ways:
        forward, backward = _direction(tags)
        seen = Counter(refs)

        current: list[int] = []
        for position, ref in enumerate(refs):
            current.append(ref)
            is_endpoint = position in (0, len(refs) - 1)
            is_junction = usage[ref] > 1 or seen[ref] > 1 or is_endpoint

            if len(current) >= 2 and is_junction:
                geometry = []
                for node_id in current:
                    coords = nodes.get(node_id)
                    if coords is None:
                        geometry = []
                        break
                    geometry.append(coords)

                if len(geometry) >= 2 and current[0] != current[-1]:
                    segments.append(Segment(
                        start=current[0],
                        end=current[-1],
                        geometry=tuple(geometry),
                        tags=tags,
                        forward=forward,
                        backward=backward,
                    ))
                elif not geometry:
                    missing += 1
                current = [ref]

    if missing:
        logger.warning("%d segments dropped: Overpass omitted some member nodes", missing)
    logger.info("Parsed %d road segments from %d highway ways",
                len(segments), len(highway_ways))
    return segments

def _direction(tags: dict) -> tuple[bool, bool]:
    """(traversable start->end, traversable end->start) for motor vehicles."""
    raw = str(tags.get("oneway", "")).strip().lower()
    if raw in _ONEWAY_FORWARD:
        return True, False
    if raw in _ONEWAY_REVERSE:
        return False, True
    if raw not in _ONEWAY_NEGATIVE:
        if str(tags.get("junction", "")).lower() in _IMPLIED_ONEWAY_JUNCTION:
            return True, False
        if str(tags.get("highway", "")).lower() in _IMPLIED_ONEWAY_HIGHWAY:
            return True, False
    return True, True

def facilities(elements: list, nodes: dict, type_keys: tuple) -> list:
    """Named nodes and ways, each reduced to a single representative point."""
    placed: list[Facility] = []
    skipped = 0

    for element in elements:
        tags = element.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        if not any(key in tags for key in type_keys):
            continue

        kind = element.get("type")
        if kind == "node":
            try:
                lat, lon = float(element["lat"]), float(element["lon"])
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
        elif kind == "way":
            refs = [int(r) for r in (element.get("nodes") or [])]
            points = [nodes[r] for r in refs if r in nodes]
            if len(points) < 2:
                skipped += 1
                continue
            lat, lon = ring_centroid(points)
        else:
            continue

        placed.append(Facility(
            osm_id=f"{kind}/{element['id']}",
            name=str(name),
            tags=tags,
            lat=lat,
            lon=lon,
        ))

    if skipped:
        logger.warning("%d named features skipped: no usable geometry", skipped)
    logger.info("Parsed %d placed facilities", len(placed))
    return placed

def tag_value(tags: dict, keys: tuple, default: str) -> str:
    for key in keys:
        value = tags.get(key)
        if value:
            return str(value)
    return default

def clean_tag(tags: dict, key: str) -> Optional[str]:
    value = tags.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
