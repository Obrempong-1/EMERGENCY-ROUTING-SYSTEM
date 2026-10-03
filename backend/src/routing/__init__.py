"""Routing engine: graph construction, priority queue, and shortest-path search."""

from __future__ import annotations

from .builder import build_route_graph
from .dijkstra import a_star, dijkstra, dijkstra_from_many, dijkstra_to_many
from .graph import RouteGraph
from .snapping import EdgeIndex
from .weights import MODE_BITS, make_weight_fn

__all__ = [
    "EdgeIndex",
    "MODE_BITS",
    "RouteGraph",
    "a_star",
    "build_route_graph",
    "dijkstra",
    "dijkstra_from_many",
    "dijkstra_to_many",
    "make_weight_fn",
]
