"""Per-request virtual nodes layered over the shared, read-only RouteGraph."""

from __future__ import annotations

from typing import Sequence

from .graph import Edge, RouteGraph

class _NodeView:
    """Membership over the base graph's nodes plus this request's virtual ones."""

    __slots__ = ("_base", "_extra")

    def __init__(self, base: dict, extra: dict) -> None:
        self._base = base
        self._extra = extra

    def __contains__(self, node_id) -> bool:
        return node_id in self._extra or node_id in self._base

class GraphOverlay:
    __slots__ = ("_base", "_adj", "_coords", "_next_id")

    def __init__(self, base: RouteGraph) -> None:
        self._base = base
        self._adj: dict[int, list[Edge]] = {}
        self._coords: dict[int, tuple[float, float]] = {}
        self._next_id = -1

    def add_virtual_node(self, lat: float, lon: float) -> int:
        node_id = self._next_id
        self._next_id -= 1
        self._coords[node_id] = (lat, lon)
        return node_id

    def add_edge(
        self,
        from_node: int,
        to_node: int,
        length_m: float,
        geometry: tuple,
        template: Edge,
    ) -> None:
        """Add a partial copy of `template`, with its costs scaled by length."""
        if length_m <= 0 or len(geometry) < 2:
            return
        share = length_m / template.length_m if template.length_m > 0 else 1.0
        self._adj.setdefault(from_node, []).append(Edge(
            from_node=from_node,
            to_node=to_node,
            length_m=length_m,
            highway=template.highway,
            name=template.name,
            allowed=template.allowed,
            base_seconds={bit: seconds * share
                          for bit, seconds in template.base_seconds.items()},
            geometry=geometry,
            restricted=template.restricted,
            roundabout=template.roundabout,
        ))

    def neighbours(self, node_id) -> Sequence[Edge]:
        extra = self._adj.get(node_id)
        if extra is None:
            return self._base.neighbours(node_id)
        if node_id < 0:
            return extra
        return [*self._base.neighbours(node_id), *extra]

    def coords(self, node_id) -> tuple[float, float]:
        virtual = self._coords.get(node_id)
        return virtual if virtual is not None else self._base.coords(node_id)

    @property
    def nodes(self) -> _NodeView:
        return _NodeView(self._base.nodes, self._coords)

    def max_speed_mps(self, mode_bit: int) -> float:
        return self._base.max_speed_mps(mode_bit)

