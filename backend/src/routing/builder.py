"""Compile parsed OSM road segments into a RouteGraph."""

from __future__ import annotations

import logging

from .graph import Edge, RouteGraph, polyline_length_m
from .weights import (
    BIKE,
    DRIVE,
    WALK,
    access_for,
    base_traverse_seconds,
    directional_maxspeed,
    drive_speed_kph,
    tag_text,
)

logger = logging.getLogger(__name__)

_MODE_NAMES = (("drive", DRIVE), ("bike", BIKE), ("walk", WALK))

_YES = frozenset({"yes", "true", "1"})
_REVERSE = frozenset({"-1", "reverse"})
_NO = frozenset({"no", "false", "0"})
_ROUNDABOUT = frozenset({"roundabout", "circular"})

_DIRECTIONAL_KEYS: dict[int, tuple[str, ...]] = {
    DRIVE: ("access", "vehicle", "motor_vehicle", "motorcar"),
    BIKE: ("access", "vehicle", "bicycle"),
    WALK: ("access", "foot"),
}

def build_route_graph(segments) -> RouteGraph:
    """Build the routing graph from `osm.parse.Segment` records."""
    graph = RouteGraph()
    skipped = pushed = restricted_edges = 0

    for segment in segments:
        tags = segment.tags
        highway = _first(tags.get("highway"), "unclassified")
        allowed, restricted = access_for(tags)
        if not allowed:
            skipped += 1
            continue

        geometry = segment.geometry
        if len(geometry) < 2 or segment.start == segment.end:
            skipped += 1
            continue

        length_m = polyline_length_m(geometry)
        if length_m <= 0:
            skipped += 1
            continue

        graph.add_node(segment.start, geometry[0][0], geometry[0][1])
        graph.add_node(segment.end, geometry[-1][0], geometry[-1][1])

        name = _first(tags.get("name"), "") or ""
        roundabout = tag_text(tags, "junction") in _ROUNDABOUT
        legal = _legal_directions(segment)

        for direction, start, end, points in (
            ("forward", segment.start, segment.end, geometry),
            ("backward", segment.end, segment.start, tuple(reversed(geometry))),
        ):
            mask = 0
            for _, bit in _MODE_NAMES:
                if allowed & bit and legal[direction][bit]:
                    mask |= bit

            drive_kph = drive_speed_kph(highway, directional_maxspeed(tags, direction))
            seconds = {
                bit: base_traverse_seconds(mode, length_m, highway, drive_kph, tags)
                for mode, bit in _MODE_NAMES
            }

            if allowed & BIKE and not mask & BIKE and mask & WALK:
                mask |= BIKE
                seconds[BIKE] = seconds[WALK]
                pushed += 1

            if not mask:
                continue
            if restricted & mask:
                restricted_edges += 1
            graph.add_edge(Edge(
                from_node=start, to_node=end, length_m=length_m,
                highway=highway, name=name, allowed=mask,
                base_seconds=seconds, geometry=points,
                restricted=restricted & mask, roundabout=roundabout,
            ))

    logger.info("RouteGraph built: %d nodes, %d edges (%d bike-pushing, %d private, "
                "%d skipped)", len(graph), graph.edge_count, pushed, restricted_edges,
                skipped)
    stats = graph.mode_stats([bit for _, bit in _MODE_NAMES])
    for label, bit in _MODE_NAMES:
        nodes, edges = stats[bit]
        logger.info("  %-5s %d nodes, %d edges, max %.1f km/h",
                    label, nodes, edges, graph.max_speed_mps(bit) * 3.6)
    return graph

def _legal_directions(segment) -> dict:
    """{"forward"|"backward": {mode bit: legally traversable}} for one segment.

    Driving follows `oneway` (already resolved by the parser). Bicycles follow
    it too unless the way says otherwise; walking is two-way unless tagged.
    """
    tags = segment.tags
    drive = (segment.forward, segment.backward)

    bike = drive
    oneway_bike = tag_text(tags, "oneway:bicycle")
    if oneway_bike in _NO or any(
            tag_text(tags, key).startswith("opposite")
            for key in ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both")):
        bike = (True, True)
    elif oneway_bike in _YES:
        bike = (True, False)
    elif oneway_bike in _REVERSE:
        bike = (False, True)

    walk = (True, True)
    oneway_foot = tag_text(tags, "oneway:foot")
    if oneway_foot in _YES:
        walk = (True, False)
    elif oneway_foot in _REVERSE:
        walk = (False, True)

    legal = {
        "forward": {DRIVE: drive[0], BIKE: bike[0], WALK: walk[0]},
        "backward": {DRIVE: drive[1], BIKE: bike[1], WALK: walk[1]},
    }
    for bit, keys in _DIRECTIONAL_KEYS.items():
        for direction in ("forward", "backward"):
            for key in keys:
                if tag_text(tags, f"{key}:{direction}") in _NO:
                    legal[direction][bit] = False
    return legal

def _first(value, default):
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        return value[0] if value else default
    return value
