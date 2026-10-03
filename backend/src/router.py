"""Routing service: snapping, search selection, and result assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import config
from routing import (
    MODE_BITS,
    dijkstra_from_many,
    RouteGraph,
    a_star,
    build_route_graph,
    dijkstra,
    dijkstra_to_many,
    make_weight_fn,
)
from routing.hazards import HazardMap
from routing.instructions import build_instructions
from routing.overlay import GraphOverlay
from routing.snapping import EdgeIndex, Projection, slice_geometry, split_geometry
from routing.weights import WALK_SPEED_KPH, min_traffic_multiplier, travel_seconds

_ACCESS_SPEED_MPS = WALK_SPEED_KPH / 3.6
_DIAGNOSTIC_SNAP_LIMIT_M = 50_000.0
_JUNCTION_SNAP_M = 0.5
_COVERAGE_BANDS = (120.0, 300.0, 600.0, 900.0)
_COVERAGE_MAX_SECONDS = _COVERAGE_BANDS[-1]
_FALLBACK_MAX_SPEED_MPS = 25.0
_SNAP_CANDIDATES = 4
_MAX_SNAP_ATTEMPTS = 8

class SnapError(Exception):
    """A coordinate could not be attached to the road network."""

    def __init__(self, which: str, distance_m: Optional[float]) -> None:
        self.which = which
        self.distance_m = distance_m
        if distance_m is None:
            detail = (
                f"The {which} is not on the campus road network. "
                "Routing covers the mapped KNUST area only."
            )
        else:
            detail = (
                f"The {which} is {int(distance_m)} m from the nearest usable road, "
                f"beyond the {int(config.SNAP_TOLERANCE_M)} m limit. "
                "Move closer to a road or choose a mapped facility."
            )
        super().__init__(detail)

class NoRouteError(Exception):
    """No path exists between two snapped nodes for the requested mode."""

@dataclass
class RoutePlan:
    distance_km: float
    time_min: float
    path: list
    instructions: list
    snap: dict
    diagnostics: dict
    hazards: list = field(default_factory=list)

class RoutingService:
    __slots__ = ("graph", "index")

    def __init__(self, graph: RouteGraph) -> None:
        self.graph = graph
        self.index = EdgeIndex(graph)

    @classmethod
    def from_segments(cls, segments) -> "RoutingService":
        return cls(build_route_graph(segments))

    def plan(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        transport_mode: str = "drive",
        objective: str = "fastest",
        traffic_level: str = "normal",
        algorithm: str = "astar",
        destination_name: Optional[str] = None,
        hazards: Sequence = (),
    ) -> RoutePlan:
        mode_bit = MODE_BITS[transport_mode]
        hazard_map = HazardMap(hazards, self.index)

        origins = self._candidates("origin", origin_lat, origin_lon, mode_bit)
        destinations = self._candidates("destination", dest_lat, dest_lon, mode_bit)

        weight_fn = hazard_map.wrap(
            make_weight_fn(transport_mode, objective, traffic_level), mode_bit)
        scale = self._heuristic_scale(objective, mode_bit, transport_mode, traffic_level)

        result = None
        origin = origins[0]
        destination = destinations[0]

        for origin, destination in self._attempts(origins, destinations):
            overlay = GraphOverlay(self.graph)
            source = self._attach_origin(overlay, origin, mode_bit)
            target = self._attach_destination(overlay, destination, mode_bit)
            self._link_if_same_edge(overlay, origin, source, destination, target, mode_bit)

            if algorithm == "dijkstra":
                attempt = dijkstra(overlay, source, target, weight_fn, mode_bit)
            else:
                attempt = a_star(overlay, source, target, weight_fn, mode_bit, scale)

            if attempt.found:
                result = attempt
                break

        if result is None:
            raise NoRouteError(
                f"No {transport_mode} route exists between these points. They may lie in "
                "parts of the network that are not connected for this mode."
            )

        network_m = sum(edge.length_m for edge in result.edges)
        network_s = sum(
            travel_seconds(edge, transport_mode, traffic_level) for edge in result.edges
        )
        access_m = origin.distance_m + destination.distance_m
        access_s = access_m / _ACCESS_SPEED_MPS

        return RoutePlan(
            distance_km=round((network_m + access_m) / 1000.0, 3),
            time_min=round((network_s + access_s) / 60.0, 1),
            path=self._build_polyline(
                result.edges, (origin_lat, origin_lon), (dest_lat, dest_lon)
            ),
            instructions=build_instructions(result.edges, destination_name,
                                            self.graph, mode_bit),
            snap={
                "origin_m": round(origin.distance_m, 1),
                "destination_m": round(destination.distance_m, 1),
                "access_m": round(access_m, 1),
            },
            diagnostics={
                "algorithm": "Dijkstra" if algorithm == "dijkstra" else "A*",
                "nodes_settled": result.settled,
                "edges_in_route": len(result.edges),
                "graph_nodes": len(self.graph),
                "graph_edges": self.graph.edge_count,
            },
            hazards=hazard_map.crossed(result.edges, mode_bit),
        )

    def main_component(self, mode_bit: int) -> set:
        """The largest set of nodes joined together for one mode.

        Direction is ignored: a one-way street still connects the places along it.
        Anything outside this set is an island OSM left unconnected, and nothing on
        it can be routed to from the rest of campus.
        """
        both_ways: dict = {}
        for adjacency in self.graph.adj.values():
            for edge in adjacency:
                if not (edge.allowed & mode_bit):
                    continue
                both_ways.setdefault(edge.from_node, []).append(edge.to_node)
                both_ways.setdefault(edge.to_node, []).append(edge.from_node)

        seen: set = set()
        largest: set = set()
        for origin in both_ways:
            if origin in seen:
                continue
            component = {origin}
            queue = [origin]
            while queue:
                node = queue.pop()
                for neighbour in both_ways.get(node, ()):
                    if neighbour not in component:
                        component.add(neighbour)
                        queue.append(neighbour)
            seen |= component
            if len(component) > len(largest):
                largest = component
        return largest

    def unreachable(self, locations, transport_mode: str = "walk") -> list:
        """The places that sit off the main network, with the reason."""
        mode_bit = MODE_BITS[transport_mode]
        main = self.main_component(mode_bit)
        if not main:
            return []

        stranded = []
        for place in locations:
            try:
                candidates = self.index.nearest_edges(
                    float(place["lat"]), float(place["lon"]), mode_bit,
                    config.SNAP_TOLERANCE_M, limit=_SNAP_CANDIDATES)
            except (KeyError, TypeError, ValueError):
                stranded.append((place, "coordinates are unusable"))
                continue
            if not candidates:
                stranded.append((place, "too far from any path"))
            elif not any(c.edge.from_node in main or c.edge.to_node in main
                         for c in candidates):
                stranded.append((place, "on an island, disconnected from campus"))
        return stranded

    def nearest_facilities(
        self,
        lat: float,
        lon: float,
        candidates: Sequence[dict],
        transport_mode: str = "drive",
        traffic_level: str = "normal",
        limit: int = 3,
        hazards: Sequence = (),
    ) -> list:
        """Rank candidate facilities by travel time using a single graph sweep."""
        mode_bit = MODE_BITS[transport_mode]
        hazard_map = HazardMap(hazards, self.index)
        overlay = GraphOverlay(self.graph)

        origin = self._project("origin", lat, lon, mode_bit)
        source = self._attach_origin(overlay, origin, mode_bit)

        by_target: dict[int, tuple[dict, float]] = {}
        for facility in candidates:
            try:
                projection = self.index.nearest_edge(
                    float(facility["lat"]), float(facility["lon"]),
                    mode_bit, config.SNAP_TOLERANCE_M,
                )
            except (KeyError, TypeError, ValueError):
                continue
            if projection is None:
                continue
            target = self._attach_destination(overlay, projection, mode_bit)
            self._link_if_same_edge(overlay, origin, source, projection, target, mode_bit)
            by_target[target] = (facility, projection.distance_m)

        if not by_target:
            return []

        weight_fn = hazard_map.wrap(
            make_weight_fn(transport_mode, "fastest", traffic_level), mode_bit)
        results = dijkstra_to_many(overlay, source, by_target.keys(), weight_fn, mode_bit)

        ranked = []
        for target, result in results.items():
            if not result.found:
                continue
            facility, facility_snap = by_target[target]
            access_m = origin.distance_m + facility_snap
            network_m = sum(edge.length_m for edge in result.edges)
            network_s = sum(travel_seconds(edge, transport_mode, traffic_level)
                            for edge in result.edges)
            ranked.append({
                **facility,
                "time_min": round((network_s + access_m / _ACCESS_SPEED_MPS) / 60.0, 1),
                "distance_km": round((network_m + access_m) / 1000.0, 3),
                "hazards": hazard_map.crossed(result.edges, mode_bit),
            })

        ranked.sort(key=lambda entry: entry["time_min"])
        return ranked[:limit]

    def coverage(
        self,
        facilities: Sequence[dict],
        transport_mode: str = "drive",
        traffic_level: str = "normal",
        hazards: Sequence = (),
    ) -> dict:
        """Travel time from the nearest facility to every road, grouped into bands."""
        mode_bit = MODE_BITS[transport_mode]
        hazard_map = HazardMap(hazards, self.index)
        overlay = GraphOverlay(self.graph)
        sources = []

        for facility in facilities:
            try:
                projection = self.index.nearest_edge(
                    float(facility["lat"]), float(facility["lon"]),
                    mode_bit, config.SNAP_TOLERANCE_M)
            except (KeyError, TypeError, ValueError):
                continue
            if projection is None:
                continue
            node = self._attach_origin(overlay, projection, mode_bit)
            sources.append((node, projection.distance_m / _ACCESS_SPEED_MPS))

        if not sources:
            raise NoRouteError("None of those facilities could be placed on the network.")

        weight_fn = hazard_map.wrap(
            make_weight_fn(transport_mode, "fastest", traffic_level, avoid_restricted=False),
            mode_bit)
        cost = dijkstra_from_many(overlay, sources, weight_fn, mode_bit,
                                  _COVERAGE_MAX_SECONDS)

        edges = [*_COVERAGE_BANDS, float("inf")]
        lines = [[] for _ in edges]
        seen = set()
        unreachable = 0

        for adjacency in self.graph.adj.values():
            for edge in adjacency:
                if not (edge.allowed & mode_bit):
                    continue
                key = frozenset((edge.from_node, edge.to_node))
                if key in seen:
                    continue
                seen.add(key)

                start, end = cost.get(edge.from_node), cost.get(edge.to_node)
                geometry = [[round(lat, 5), round(lon, 5)] for lat, lon in edge.geometry]
                if start is None or end is None:
                    unreachable += 1
                    lines[-1].append(geometry)
                    continue

                worst = max(start, end)
                for index, limit in enumerate(edges):
                    if worst <= limit:
                        lines[index].append(geometry)
                        break

        return {
            "transport_mode": transport_mode,
            "traffic_level": traffic_level,
            "facility_count": len(sources),
            "unreachable_segments": unreachable,
            "bands": [
                {
                    "index": index,
                    "max_seconds": None if limit == float("inf") else limit,
                    "label": _band_label(index, edges),
                    "lines": lines[index],
                }
                for index, limit in enumerate(edges)
            ],
        }

    def _candidates(self, which: str, lat: float, lon: float, mode_bit: int) -> list:
        found = self.index.nearest_edges(
            lat, lon, mode_bit, config.SNAP_TOLERANCE_M, _SNAP_CANDIDATES)
        if not found:
            raise SnapError(which, self._diagnostic_distance(lat, lon, mode_bit))
        return found

    @staticmethod
    def _attempts(origins: list, destinations: list):
        """Candidate pairs, nearest combined snap first, capped to bound the work."""
        pairs = [(o, d) for o in origins for d in destinations]
        pairs.sort(key=lambda pair: pair[0].distance_m + pair[1].distance_m)
        return pairs[:_MAX_SNAP_ATTEMPTS]

    def _project(self, which: str, lat: float, lon: float, mode_bit: int) -> Projection:
        projection = self.index.nearest_edge(lat, lon, mode_bit, config.SNAP_TOLERANCE_M)
        if projection is None:
            raise SnapError(which, self._diagnostic_distance(lat, lon, mode_bit))
        return projection

    def _reverse_edge(self, edge, mode_bit: int):
        """The base-graph edge running back along the same road, if there is one."""
        for candidate in self.graph.neighbours(edge.to_node):
            if (candidate.to_node == edge.from_node
                    and candidate.allowed & mode_bit
                    and candidate.highway == edge.highway
                    and candidate.name == edge.name):
                return candidate
        return None

    def _attach_origin(self, overlay: GraphOverlay, projection: Projection,
                       mode_bit: int) -> int:
        edge = projection.edge
        if projection.along_m >= edge.length_m - _JUNCTION_SNAP_M:
            return edge.to_node
        if projection.along_m <= _JUNCTION_SNAP_M:
            return edge.from_node

        node = overlay.add_virtual_node(projection.lat, projection.lon)
        head, tail = split_geometry(edge, projection.lat, projection.lon, projection.along_m)

        overlay.add_edge(node, edge.to_node,
                         edge.length_m - projection.along_m, tail, edge)

        reverse = self._reverse_edge(edge, mode_bit)
        if reverse is not None:
            overlay.add_edge(node, edge.from_node,
                             projection.along_m, tuple(reversed(head)), reverse)
        return node

    def _attach_destination(self, overlay: GraphOverlay, projection: Projection,
                            mode_bit: int) -> int:
        edge = projection.edge
        if projection.along_m >= edge.length_m - _JUNCTION_SNAP_M:
            return edge.to_node
        if projection.along_m <= _JUNCTION_SNAP_M:
            return edge.from_node

        node = overlay.add_virtual_node(projection.lat, projection.lon)
        head, tail = split_geometry(edge, projection.lat, projection.lon, projection.along_m)

        overlay.add_edge(edge.from_node, node, projection.along_m, head, edge)

        reverse = self._reverse_edge(edge, mode_bit)
        if reverse is not None:
            overlay.add_edge(edge.to_node, node,
                             edge.length_m - projection.along_m,
                             tuple(reversed(tail)), reverse)
        return node

    def _link_if_same_edge(self, overlay: GraphOverlay, origin: Projection, source: int,
                           destination: Projection, target: int, mode_bit: int) -> None:
        """Join the two virtual nodes directly when both landed on the same road."""
        edge = origin.edge
        if destination.edge is edge:
            if destination.along_m >= origin.along_m:
                overlay.add_edge(source, target,
                                 destination.along_m - origin.along_m,
                                 slice_geometry(edge, origin, destination), edge)
                return
            reverse = self._reverse_edge(edge, mode_bit)
            if reverse is not None:
                overlay.add_edge(source, target,
                                 origin.along_m - destination.along_m,
                                 tuple(reversed(slice_geometry(edge, destination, origin))),
                                 reverse)
            return

        reverse = self._reverse_edge(edge, mode_bit)
        if reverse is not None and destination.edge is reverse:
            mirrored = edge.length_m - destination.along_m
            if mirrored >= origin.along_m:
                stand_in = Projection(edge, destination.lat, destination.lon,
                                      destination.distance_m, mirrored)
                overlay.add_edge(source, target, mirrored - origin.along_m,
                                 slice_geometry(edge, origin, stand_in), edge)

    def _diagnostic_distance(self, lat: float, lon: float, mode_bit: int):
        projection = self.index.nearest_edge(lat, lon, mode_bit, _DIAGNOSTIC_SNAP_LIMIT_M)
        return None if projection is None else projection.distance_m

    def _heuristic_scale(self, objective: str, mode_bit: int, transport_mode: str,
                         traffic_level: str) -> float:
        """Metres-to-cost-unit divisor for the A* heuristic.

        `max_speed_mps` is derived from unscaled base times, so when light traffic
        makes edges cheaper the divisor has to grow by the same factor. Only
        factors below 1 are applied, so the heuristic can never become less
        optimistic than the plain top speed.
        """
        if objective == "shortest":
            return 1.0
        observed = self.graph.max_speed_mps(mode_bit)
        if observed <= 0:
            observed = _FALLBACK_MAX_SPEED_MPS
        return observed / min(1.0, min_traffic_multiplier(transport_mode, traffic_level))

    @staticmethod
    def _build_polyline(edges: Sequence, origin: tuple, destination: tuple) -> list:
        path = [[origin[0], origin[1]]]
        for index, edge in enumerate(edges):
            vertices = edge.geometry if index == 0 else edge.geometry[1:]
            for lat, lon in vertices:
                if path[-1][0] != lat or path[-1][1] != lon:
                    path.append([lat, lon])
        final = [destination[0], destination[1]]
        if path[-1] != final:
            path.append(final)
        return path

def _band_label(index: int, edges: Sequence[float]) -> str:
    limit = edges[index]
    if limit == float("inf"):
        return f"Over {int(edges[index - 1] // 60)} min or no access"
    if index == 0:
        return f"Under {int(limit // 60)} min"
    return f"{int(edges[index - 1] // 60)}-{int(limit // 60)} min"
