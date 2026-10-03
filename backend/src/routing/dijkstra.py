"""Dijkstra and A* shortest-path search over a RouteGraph."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Callable, Iterable

from .graph import Edge, Graph, haversine_m
from .priority_queue import MinHeap

@dataclass
class SearchResult:
    found: bool
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    cost: float = inf
    settled: int = 0

def _not_found(settled: int = 0) -> SearchResult:
    return SearchResult(found=False, settled=settled)

def dijkstra(
    graph: Graph,
    source,
    target,
    weight_fn: Callable,
    mode_bit: int,
) -> SearchResult:
    """Shortest path from `source` to `target` using edges permitted for `mode_bit`."""
    if source not in graph.nodes or target not in graph.nodes:
        return _not_found()
    if source == target:
        return SearchResult(found=True, nodes=[source], cost=0.0)

    dist: dict = {source: 0.0}
    parent: dict = {}
    settled: set = set()
    pops = 0

    frontier = MinHeap()
    frontier.push(source, 0.0)

    while frontier:
        node, cost = frontier.pop_min()
        pops += 1

        if node == target:
            nodes, edges = _reconstruct(parent, source, target)
            return SearchResult(True, nodes, edges, cost, pops)

        settled.add(node)

        for edge in graph.neighbours(node):
            if not (edge.allowed & mode_bit):
                continue
            neighbour = edge.to_node
            if neighbour in settled:
                continue
            candidate = cost + weight_fn(edge)
            if candidate < dist.get(neighbour, inf):
                dist[neighbour] = candidate
                parent[neighbour] = (node, edge)
                frontier.push_or_decrease(neighbour, candidate)

    return _not_found(pops)

def a_star(
    graph: Graph,
    source,
    target,
    weight_fn: Callable,
    mode_bit: int,
    heuristic_scale: float,
) -> SearchResult:
    """Dijkstra guided by straight-line distance to the target."""
    if source not in graph.nodes or target not in graph.nodes:
        return _not_found()
    if source == target:
        return SearchResult(found=True, nodes=[source], cost=0.0)
    if heuristic_scale <= 0:
        return dijkstra(graph, source, target, weight_fn, mode_bit)

    target_lat, target_lon = graph.coords(target)

    def heuristic(node) -> float:
        lat, lon = graph.coords(node)
        return haversine_m(lat, lon, target_lat, target_lon) / heuristic_scale

    best: dict = {source: 0.0}
    parent: dict = {}
    settled: set = set()
    pops = 0

    frontier = MinHeap()
    frontier.push(source, heuristic(source))

    while frontier:
        node, _priority = frontier.pop_min()
        pops += 1

        if node == target:
            nodes, edges = _reconstruct(parent, source, target)
            return SearchResult(True, nodes, edges, best[target], pops)

        settled.add(node)
        cost = best[node]

        for edge in graph.neighbours(node):
            if not (edge.allowed & mode_bit):
                continue
            neighbour = edge.to_node
            if neighbour in settled:
                continue
            candidate = cost + weight_fn(edge)
            if candidate < best.get(neighbour, inf):
                best[neighbour] = candidate
                parent[neighbour] = (node, edge)
                frontier.push_or_decrease(neighbour, candidate + heuristic(neighbour))

    return _not_found(pops)

def dijkstra_to_many(
    graph: Graph,
    source,
    targets: Iterable,
    weight_fn: Callable,
    mode_bit: int,
) -> dict:
    results: dict = {}
    if source not in graph.nodes:
        return results

    remaining = {t for t in targets if t in graph.nodes}
    if not remaining:
        return results

    dist: dict = {source: 0.0}
    parent: dict = {}
    settled: set = set()
    pops = 0

    frontier = MinHeap()
    frontier.push(source, 0.0)

    while frontier and remaining:
        node, cost = frontier.pop_min()
        pops += 1
        settled.add(node)

        if node in remaining:
            remaining.discard(node)
            if node == source:
                results[node] = SearchResult(found=True, nodes=[source], cost=0.0, settled=pops)
            else:
                nodes, edges = _reconstruct(parent, source, node)
                results[node] = SearchResult(True, nodes, edges, cost, pops)

        for edge in graph.neighbours(node):
            if not (edge.allowed & mode_bit):
                continue
            neighbour = edge.to_node
            if neighbour in settled:
                continue
            candidate = cost + weight_fn(edge)
            if candidate < dist.get(neighbour, inf):
                dist[neighbour] = candidate
                parent[neighbour] = (node, edge)
                frontier.push_or_decrease(neighbour, candidate)

    for unreached in remaining:
        results[unreached] = _not_found(pops)
    return results

def dijkstra_from_many(
    graph: Graph,
    sources,
    weight_fn: Callable,
    mode_bit: int,
    max_cost: float = inf,
) -> dict:
    """Cost from the nearest of many sources to every reachable node."""
    dist: dict = {}
    frontier = MinHeap()

    for node, initial in sources:
        if node not in graph.nodes or initial > max_cost:
            continue
        if initial < dist.get(node, inf):
            dist[node] = initial
            frontier.push_or_decrease(node, initial)

    if not frontier:
        return {}

    settled: dict = {}

    while frontier:
        node, cost = frontier.pop_min()
        settled[node] = cost

        for edge in graph.neighbours(node):
            if not (edge.allowed & mode_bit):
                continue
            neighbour = edge.to_node
            if neighbour in settled:
                continue
            candidate = cost + weight_fn(edge)
            if candidate > max_cost:
                continue
            if candidate < dist.get(neighbour, inf):
                dist[neighbour] = candidate
                frontier.push_or_decrease(neighbour, candidate)

    return settled

def _reconstruct(parent: dict, source, target) -> tuple[list, list]:
    nodes = [target]
    edges: list[Edge] = []
    cursor = target
    while cursor != source:
        previous, edge = parent[cursor]
        edges.append(edge)
        nodes.append(previous)
        cursor = previous
    nodes.reverse()
    edges.reverse()
    return nodes, edges
