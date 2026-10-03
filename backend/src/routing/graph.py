"""Routing graph: nodes, directed edges, and an adjacency list."""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Container, Protocol, Sequence

EARTH_RADIUS_M = 6_371_008.8

_NO_EDGES: tuple = ()

class Graph(Protocol):

    @property
    def nodes(self) -> Container: ...

    def neighbours(self, node_id: int) -> Sequence[Edge]: ...

    def coords(self, node_id: int) -> tuple[float, float]: ...

    def max_speed_mps(self, mode_bit: int) -> float: ...

@dataclass(slots=True)
class Edge:
    from_node: int
    to_node: int
    length_m: float
    highway: str
    name: str
    allowed: int
    base_seconds: dict
    geometry: tuple
    restricted: int = 0
    roundabout: bool = False

class RouteGraph:
    __slots__ = ("nodes", "adj", "_edge_count", "_max_speed_mps")

    def __init__(self) -> None:
        self.nodes: dict[int, tuple[float, float]] = {}
        self.adj: dict[int, list[Edge]] = {}
        self._edge_count = 0
        self._max_speed_mps: dict[int, float] = {}

    def add_node(self, node_id: int, lat: float, lon: float) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = (lat, lon)
            self.adj[node_id] = []

    def add_edge(self, edge: Edge) -> None:
        if edge.from_node not in self.nodes or edge.to_node not in self.nodes:
            raise KeyError("both endpoints must be added before the edge")
        if edge.length_m <= 0:
            raise ValueError("edge length must be positive")
        if not edge.allowed:
            raise ValueError("edge must permit at least one travel mode")
        if len(edge.geometry) < 2:
            raise ValueError("edge geometry needs at least two vertices")

        self.adj[edge.from_node].append(edge)
        self._edge_count += 1

        for bit, seconds in edge.base_seconds.items():
            if not (edge.allowed & bit) or seconds <= 0:
                continue
            speed = edge.length_m / seconds
            if speed > self._max_speed_mps.get(bit, 0.0):
                self._max_speed_mps[bit] = speed

    def __len__(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return self._edge_count

    def neighbours(self, node_id: int) -> Sequence[Edge]:
        return self.adj.get(node_id, _NO_EDGES)

    def coords(self, node_id: int) -> tuple[float, float]:
        return self.nodes[node_id]

    def max_speed_mps(self, mode_bit: int) -> float:
        """Fastest observed speed for a mode; an upper bound for A* heuristics."""
        return self._max_speed_mps.get(mode_bit, 0.0)

    def mode_stats(self, mode_bits) -> dict:
        """Reachable node and edge counts per mode, in one pass over the adjacency."""
        nodes = {bit: set() for bit in mode_bits}
        edges = {bit: 0 for bit in mode_bits}
        for adjacency in self.adj.values():
            for edge in adjacency:
                for bit in mode_bits:
                    if edge.allowed & bit:
                        edges[bit] += 1
                        nodes[bit].add(edge.from_node)
                        nodes[bit].add(edge.to_node)
        return {bit: (len(nodes[bit]), edges[bit]) for bit in mode_bits}

def polyline_length_m(points) -> float:
    """Ground length of a (lat, lon) polyline."""
    return sum(haversine_m(lat1, lon1, lat2, lon2)
               for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]))

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = radians(lon2 - lon1)
    h = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(h))
