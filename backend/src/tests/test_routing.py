"""Correctness tests for the routing engine."""

from __future__ import annotations

import os
import random
import sys
import unittest
from itertools import permutations
from math import inf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routing.priority_queue import MinHeap
from routing.graph import RouteGraph, Edge, haversine_m
from routing.dijkstra import dijkstra, a_star, dijkstra_from_many, dijkstra_to_many
from routing.snapping import EdgeIndex, project_onto_edge
from routing.weights import min_traffic_multiplier
from routing.weights import DRIVE, WALK, BIKE, make_weight_fn, parse_maxspeed, permissions_for
from routing.instructions import bearing, build_instructions

def heap_is_valid(heap: MinHeap) -> bool:
    keys = heap._keys
    for i in range(1, len(keys)):
        if keys[(i - 1) // 2] > keys[i]:
            return False
    return all(heap._pos[item] == i for i, item in enumerate(heap._items))

class TestMinHeap(unittest.TestCase):
    def test_pops_in_sorted_order(self):
        random.seed(1)
        for _ in range(50):
            pairs = [(f"n{i}", random.uniform(0, 100)) for i in range(random.randint(1, 60))]
            heap = MinHeap()
            for item, key in pairs:
                heap.push(item, key)
                self.assertTrue(heap_is_valid(heap))
            popped = [heap.pop_min()[1] for _ in range(len(pairs))]
            self.assertEqual(popped, sorted(popped))

    def test_invariant_holds_through_decrease_key(self):
        random.seed(2)
        heap = MinHeap()
        for i in range(40):
            heap.push(i, random.uniform(50, 100))
        for _ in range(200):
            item = random.randrange(40)
            if item in heap:
                heap.decrease_key(item, heap.key_of(item) - random.uniform(0, 5))
                self.assertTrue(heap_is_valid(heap))

    def test_decrease_key_cannot_raise(self):
        heap = MinHeap()
        heap.push("a", 5.0)
        with self.assertRaises(ValueError):
            heap.decrease_key("a", 9.0)

    def test_duplicate_push_rejected(self):
        heap = MinHeap()
        heap.push("a", 1.0)
        with self.assertRaises(KeyError):
            heap.push("a", 2.0)

    def test_heap_never_exceeds_node_count(self):
        heap = MinHeap()
        for i in range(10):
            heap.push(i, 100.0)
        for _ in range(500):
            heap.push_or_decrease(random.randrange(10), random.uniform(0, 99))
        self.assertLessEqual(len(heap), 10)

    def test_empty_pop_raises(self):
        with self.assertRaises(IndexError):
            MinHeap().pop_min()

def random_graph(node_count: int, edge_count: int, seed: int) -> RouteGraph:
    rng = random.Random(seed)
    g = RouteGraph()
    for i in range(node_count):
        g.add_node(i, 6.67 + rng.uniform(-0.01, 0.01), -1.57 + rng.uniform(-0.01, 0.01))
    for _ in range(edge_count):
        u, v = rng.randrange(node_count), rng.randrange(node_count)
        if u == v:
            continue
        length = max(haversine_m(*g.coords(u), *g.coords(v)), 5.0)
        allowed = rng.choice([DRIVE | BIKE | WALK, WALK, DRIVE, BIKE | WALK])
        g.add_edge(Edge(
            from_node=u, to_node=v, length_m=length, highway="residential",
            name="", allowed=allowed,
            base_seconds={DRIVE: length / 7, BIKE: length / 4, WALK: length / 1.4},
            geometry=(g.coords(u), g.coords(v)),
        ))
    return g

def _any_edge(g: RouteGraph) -> Edge:
    for edges in g.adj.values():
        if edges:
            return edges[0]
    raise AssertionError("fixture produced no edges")

def brute_force_shortest(g: RouteGraph, source: int, target: int,
                         weight_fn, mode_bit: int) -> float:
    best = inf
    nodes = [n for n in g.nodes if n not in (source, target)]
    for size in range(len(nodes) + 1):
        for middle in permutations(nodes, size):
            chain = (source,) + middle + (target,)
            total = 0.0
            ok = True
            for a, b in zip(chain, chain[1:]):
                usable = [e for e in g.neighbours(a)
                          if e.to_node == b and e.allowed & mode_bit]
                if not usable:
                    ok = False
                    break
                total += min(weight_fn(e) for e in usable)
            if ok:
                best = min(best, total)
    return best

class TestDijkstraCorrectness(unittest.TestCase):
    def test_matches_brute_force_on_random_graphs(self):
        weight_fn = make_weight_fn("drive", "shortest", "normal")
        for seed in range(40):
            g = random_graph(6, 14, seed)
            for source in g.nodes:
                for target in g.nodes:
                    if source == target:
                        continue
                    expected = brute_force_shortest(g, source, target, weight_fn, DRIVE)
                    result = dijkstra(g, source, target, weight_fn, DRIVE)
                    if expected == inf:
                        self.assertFalse(result.found,
                                         f"seed {seed}: claimed a path that does not exist")
                    else:
                        self.assertTrue(result.found, f"seed {seed}: missed an existing path")
                        self.assertAlmostEqual(result.cost, expected, places=6,
                                               msg=f"seed {seed} {source}->{target}")

    def test_astar_matches_dijkstra(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        for seed in range(30):
            g = random_graph(12, 40, seed + 100)
            for source, target in ((0, 5), (3, 11), (7, 1)):
                d = dijkstra(g, source, target, weight_fn, DRIVE)
                a = a_star(g, source, target, weight_fn, DRIVE, g.max_speed_mps(DRIVE))
                self.assertEqual(d.found, a.found)
                if d.found:
                    self.assertAlmostEqual(d.cost, a.cost, places=6)

    def test_reported_cost_equals_sum_of_returned_edges(self):
        weight_fn = make_weight_fn("drive", "fastest", "heavy")
        for seed in range(30):
            g = random_graph(10, 35, seed + 200)
            result = dijkstra(g, 0, 9, weight_fn, DRIVE)
            if result.found:
                self.assertAlmostEqual(
                    result.cost, sum(weight_fn(e) for e in result.edges), places=6)

    def test_path_is_connected_and_endpoints_correct(self):
        weight_fn = make_weight_fn("walk", "shortest", "normal")
        for seed in range(30):
            g = random_graph(10, 35, seed + 300)
            r = dijkstra(g, 0, 9, weight_fn, WALK)
            if r.found:
                self.assertEqual(r.nodes[0], 0)
                self.assertEqual(r.nodes[-1], 9)
                self.assertEqual(len(r.edges), len(r.nodes) - 1)
                for node, edge in zip(r.nodes, r.edges):
                    self.assertEqual(edge.from_node, node)
                for edge, node in zip(r.edges, r.nodes[1:]):
                    self.assertEqual(edge.to_node, node)

    def test_mode_filter_is_never_violated(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        for seed in range(40):
            g = random_graph(12, 45, seed + 400)
            for target in g.nodes:
                r = dijkstra(g, 0, target, weight_fn, DRIVE)
                for edge in r.edges:
                    self.assertTrue(edge.allowed & DRIVE,
                                    "Dijkstra used an edge this mode may not use")

    def test_mode_can_make_a_route_impossible(self):
        g = RouteGraph()
        g.add_node(1, 6.670, -1.570)
        g.add_node(2, 6.671, -1.570)
        g.add_edge(Edge(1, 2, 100, "footway", "", WALK,
                        {DRIVE: 10, BIKE: 10, WALK: 72}, ((6.670, -1.570), (6.671, -1.570))))
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        self.assertFalse(dijkstra(g, 1, 2, weight_fn, DRIVE).found)
        self.assertTrue(dijkstra(g, 1, 2, make_weight_fn("walk", "fastest", "normal"), WALK).found)

    def test_dijkstra_to_many_matches_individual_searches(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        for seed in range(20):
            g = random_graph(12, 45, seed + 500)
            targets = {2, 5, 8, 11}
            batch = dijkstra_to_many(g, 0, targets, weight_fn, DRIVE)
            for target in targets:
                single = dijkstra(g, 0, target, weight_fn, DRIVE)
                self.assertEqual(batch[target].found, single.found)
                if single.found:
                    self.assertAlmostEqual(batch[target].cost, single.cost, places=6)

    def test_source_equals_target(self):
        g = random_graph(5, 10, 1)
        r = dijkstra(g, 0, 0, make_weight_fn("drive", "fastest", "normal"), DRIVE)
        self.assertTrue(r.found)
        self.assertEqual(r.cost, 0.0)
        self.assertEqual(r.edges, [])

    def test_unknown_node_is_not_found(self):
        g = random_graph(5, 10, 1)
        self.assertFalse(dijkstra(g, 0, 999, make_weight_fn("drive", "fastest", "normal"),
                                  DRIVE).found)

class TestMultiSourceDijkstra(unittest.TestCase):
    def test_matches_the_minimum_over_single_source_runs(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        for seed in range(25):
            g = random_graph(12, 40, seed + 900)
            sources = [0, 4, 9]
            multi = dijkstra_from_many(g, [(s, 0.0) for s in sources], weight_fn, DRIVE)
            for node in g.nodes:
                best = inf
                for source in sources:
                    result = dijkstra(g, source, node, weight_fn, DRIVE)
                    if result.found:
                        best = min(best, result.cost)
                if best == inf:
                    self.assertNotIn(node, multi)
                else:
                    self.assertAlmostEqual(multi[node], best, places=6)

    def test_initial_costs_are_honoured(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        g = random_graph(10, 30, 901)
        plain = dijkstra_from_many(g, [(0, 0.0)], weight_fn, DRIVE)
        offset = dijkstra_from_many(g, [(0, 25.0)], weight_fn, DRIVE)
        for node, cost in plain.items():
            self.assertAlmostEqual(offset[node], cost + 25.0, places=6)

    def test_nearer_source_wins(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        g = random_graph(10, 30, 902)
        one = dijkstra_from_many(g, [(0, 0.0)], weight_fn, DRIVE)
        both = dijkstra_from_many(g, [(0, 0.0), (5, 0.0)], weight_fn, DRIVE)
        for node, cost in one.items():
            self.assertLessEqual(both[node], cost + 1e-9)

    def test_empty_sources_returns_empty(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        g = random_graph(8, 20, 903)
        self.assertEqual(dijkstra_from_many(g, [], weight_fn, DRIVE), {})

    def test_unknown_source_ids_are_ignored(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        g = random_graph(8, 20, 904)
        self.assertEqual(dijkstra_from_many(g, [(9999, 0.0)], weight_fn, DRIVE), {})

    def test_duplicate_sources_do_not_raise(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        g = random_graph(8, 20, 905)
        result = dijkstra_from_many(g, [(0, 5.0), (0, 2.0)], weight_fn, DRIVE)
        self.assertAlmostEqual(result[0], 2.0, places=9)

    def test_max_cost_truncates_without_dropping_cheaper_nodes(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        g = random_graph(14, 45, 906)
        full = dijkstra_from_many(g, [(0, 0.0)], weight_fn, DRIVE)
        capped = dijkstra_from_many(g, [(0, 0.0)], weight_fn, DRIVE, max_cost=40.0)
        for node, cost in capped.items():
            self.assertLessEqual(cost, 40.0)
        for node, cost in full.items():
            if cost <= 40.0:
                self.assertIn(node, capped)

    def test_mode_filtering_is_respected(self):
        g = RouteGraph()
        g.add_node(1, 6.670, -1.570)
        g.add_node(2, 6.671, -1.570)
        g.add_edge(Edge(1, 2, 100, "footway", "", WALK,
                        {DRIVE: 10, BIKE: 10, WALK: 72},
                        ((6.670, -1.570), (6.671, -1.570))))
        drive = dijkstra_from_many(g, [(1, 0.0)],
                                   make_weight_fn("drive", "fastest", "normal"), DRIVE)
        walk = dijkstra_from_many(g, [(1, 0.0)],
                                  make_weight_fn("walk", "fastest", "normal"), WALK)
        self.assertNotIn(2, drive)
        self.assertIn(2, walk)

class TestWeights(unittest.TestCase):
    def test_weights_are_strictly_positive(self):
        g = random_graph(10, 30, 7)
        for mode in ("drive", "walk", "bike"):
            for objective in ("fastest", "shortest"):
                for traffic in ("low", "normal", "heavy"):
                    fn = make_weight_fn(mode, objective, traffic)
                    for edges in g.adj.values():
                        for edge in edges:
                            self.assertGreater(fn(edge), 0.0)

    def test_heavy_traffic_is_slower_than_normal_for_driving(self):
        edge = _any_edge(random_graph(5, 10, 3))
        normal = make_weight_fn("drive", "fastest", "normal")(edge)
        heavy = make_weight_fn("drive", "fastest", "heavy")(edge)
        low = make_weight_fn("drive", "fastest", "low")(edge)
        self.assertGreater(heavy, normal)
        self.assertLess(low, normal)

    def test_traffic_is_ignored_for_walking(self):
        edge = _any_edge(random_graph(5, 10, 3))
        self.assertEqual(make_weight_fn("walk", "fastest", "heavy")(edge),
                         make_weight_fn("walk", "fastest", "normal")(edge))

    def test_mph_is_converted_not_assumed_kph(self):
        self.assertAlmostEqual(parse_maxspeed("30 mph"), 48.28, places=1)
        self.assertEqual(parse_maxspeed("50"), 50.0)
        self.assertEqual(parse_maxspeed(["40", "60"]), 40.0)
        self.assertIsNone(parse_maxspeed("signals"))
        self.assertIsNone(parse_maxspeed(None))

class TestSnapping(unittest.TestCase):
    def setUp(self):
        self.g = RouteGraph()
        self.g.add_node(1, 6.6745, -1.5716)
        self.g.add_node(2, 6.6755, -1.5716)
        for tail, head in ((1, 2), (2, 1)):
            a, b = self.g.coords(tail), self.g.coords(head)
            self.g.add_edge(Edge(tail, head, 111, "residential", "", DRIVE | WALK | BIKE,
                                 {DRIVE: 16, BIKE: 27, WALK: 80}, (a, b)))
        self.index = EdgeIndex(self.g)

    def test_point_beside_a_road_snaps_onto_it(self):
        found = self.index.nearest_edge(6.6750, -1.5714, DRIVE, 250)
        self.assertIsNotNone(found)
        self.assertLess(found.distance_m, 30)

    def test_projection_beats_the_nearest_endpoint(self):
        """The midpoint of a road is closer than either of its junctions."""
        lat, lon = 6.6750, -1.57162
        found = self.index.nearest_edge(lat, lon, DRIVE, 250)
        to_endpoints = min(haversine_m(lat, lon, *self.g.coords(n)) for n in (1, 2))
        self.assertLess(found.distance_m, to_endpoints)

    def test_far_point_is_refused(self):
        self.assertIsNone(self.index.nearest_edge(6.70, -1.54, DRIVE, 250))

    def test_projection_lies_on_the_segment(self):
        edge = self.g.neighbours(1)[0]
        found = project_onto_edge(edge, 6.6750, -1.5700)
        self.assertGreaterEqual(found.along_m, 0.0)
        self.assertLessEqual(found.along_m, edge.length_m + 1e-6)
        self.assertGreaterEqual(found.lat, min(p[0] for p in edge.geometry) - 1e-9)
        self.assertLessEqual(found.lat, max(p[0] for p in edge.geometry) + 1e-9)

    def test_grid_search_agrees_with_brute_force(self):
        rng = random.Random(9)
        g = random_graph(200, 400, 11)
        index = EdgeIndex(g)
        for _ in range(120):
            lat = 6.67 + rng.uniform(-0.012, 0.012)
            lon = -1.57 + rng.uniform(-0.012, 0.012)
            found = index.nearest_edge(lat, lon, DRIVE, 5000)
            best = inf
            for edges in g.adj.values():
                for edge in edges:
                    if edge.allowed & DRIVE:
                        best = min(best, project_onto_edge(edge, lat, lon).distance_m)
            if found is None:
                self.assertGreater(best, 5000)
            else:
                self.assertAlmostEqual(found.distance_m, best, places=6)

    def test_snap_respects_mode(self):
        g = RouteGraph()
        g.add_node(1, 6.6745, -1.5716)
        g.add_node(2, 6.6751, -1.5716)
        g.add_node(3, 6.6750, -1.5700)
        g.add_node(4, 6.6751, -1.5700)
        g.add_edge(Edge(1, 2, 70, "footway", "", WALK,
                        {DRIVE: 1, BIKE: 1, WALK: 50}, (g.coords(1), g.coords(2))))
        g.add_edge(Edge(3, 4, 11, "residential", "", DRIVE | WALK,
                        {DRIVE: 2, BIKE: 3, WALK: 8}, (g.coords(3), g.coords(4))))
        index = EdgeIndex(g)
        walking = index.nearest_edge(6.67460, -1.5716, WALK, 250)
        driving = index.nearest_edge(6.67460, -1.5716, DRIVE, 250)
        self.assertEqual(walking.edge.highway, "footway")
        self.assertEqual(driving.edge.highway, "residential")

    def test_candidates_are_returned_in_distance_order(self):
        found = self.index.nearest_edges(6.6750, -1.5714, DRIVE, 250, limit=4)
        self.assertGreaterEqual(len(found), 1)
        self.assertEqual([p.distance_m for p in found],
                         sorted(p.distance_m for p in found))

class TestInstructions(unittest.TestCase):
    def test_bearing_cardinal_directions(self):
        self.assertAlmostEqual(bearing(0, 0, 1, 0), 0.0, places=3)
        self.assertAlmostEqual(bearing(0, 0, 0, 1), 90.0, places=3)
        self.assertAlmostEqual(bearing(1, 0, 0, 0), 180.0, places=3)
        self.assertAlmostEqual(bearing(0, 1, 0, 0), 270.0, places=3)

    def _edge(self, geometry, name, highway="residential", length=100.0):
        return Edge(0, 1, length, highway, name, DRIVE | WALK | BIKE,
                    {DRIVE: 14, BIKE: 24, WALK: 72}, geometry)

    def test_right_turn_is_detected(self):
        north = self._edge(((6.6700, -1.5700), (6.6710, -1.5700)), "First Street")
        east = self._edge(((6.6710, -1.5700), (6.6710, -1.5690)), "Second Street")
        steps = build_instructions([north, east], "Great Hall")
        kinds = [s["kind"] for s in steps]
        self.assertEqual(kinds[0], "depart")
        self.assertIn("turn-right", kinds)
        self.assertEqual(kinds[-1], "arrive")
        self.assertIn("Great Hall", steps[-1]["text"])

    def test_straight_same_road_merges_into_one_step(self):
        a = self._edge(((6.6700, -1.5700), (6.6710, -1.5700)), "Long Road", length=100)
        b = self._edge(((6.6710, -1.5700), (6.6720, -1.5700)), "Long Road", length=150)
        steps = build_instructions([a, b])
        self.assertEqual(len([s for s in steps if s["kind"] != "arrive"]), 1)
        self.assertEqual(steps[0]["distance_m"], 250)

    def test_unnamed_ways_do_not_merge_across_a_turn(self):
        north = self._edge(((6.6700, -1.5700), (6.6710, -1.5700)), "", "footway")
        east = self._edge(((6.6710, -1.5700), (6.6710, -1.5690)), "", "footway")
        steps = build_instructions([north, east])
        self.assertGreaterEqual(len([s for s in steps if s["kind"] != "arrive"]), 2)

    def test_empty_route_yields_no_instructions(self):
        self.assertEqual(build_instructions([]), [])

class TestGraphValidation(unittest.TestCase):
    def _graph(self):
        g = RouteGraph()
        g.add_node(1, 6.670, -1.570)
        g.add_node(2, 6.671, -1.570)
        return g

    def _edge(self, **overrides):
        defaults = dict(
            from_node=1, to_node=2, length_m=111.0, highway="residential", name="",
            allowed=DRIVE | BIKE | WALK,
            base_seconds={DRIVE: 16.0, BIKE: 27.0, WALK: 80.0},
            geometry=((6.670, -1.570), (6.671, -1.570)),
        )
        defaults.update(overrides)
        return Edge(**defaults)

    def test_rejects_unknown_endpoints(self):
        g = self._graph()
        with self.assertRaises(KeyError):
            g.add_edge(self._edge(to_node=99))

    def test_rejects_non_positive_length(self):
        g = self._graph()
        with self.assertRaises(ValueError):
            g.add_edge(self._edge(length_m=0.0))

    def test_rejects_edge_with_no_permitted_mode(self):
        g = self._graph()
        with self.assertRaises(ValueError):
            g.add_edge(self._edge(allowed=0))

    def test_rejects_degenerate_geometry(self):
        g = self._graph()
        with self.assertRaises(ValueError):
            g.add_edge(self._edge(geometry=((6.670, -1.570),)))

    def test_tracks_max_speed_per_mode(self):
        g = self._graph()
        g.add_edge(self._edge())
        self.assertAlmostEqual(g.max_speed_mps(DRIVE), 111.0 / 16.0, places=6)
        self.assertAlmostEqual(g.max_speed_mps(WALK), 111.0 / 80.0, places=6)

    def test_max_speed_ignores_modes_the_edge_forbids(self):
        g = self._graph()
        g.add_edge(self._edge(allowed=WALK))
        self.assertEqual(g.max_speed_mps(DRIVE), 0.0)
        self.assertGreater(g.max_speed_mps(WALK), 0.0)

    def test_neighbours_of_unknown_node_is_empty(self):
        self.assertEqual(len(self._graph().neighbours(12345)), 0)

class TestHeuristicScale(unittest.TestCase):
    def test_distance_objective_uses_metre_scale(self):
        weight_fn = make_weight_fn("drive", "shortest", "normal")
        for seed in range(25):
            g = random_graph(12, 40, seed + 700)
            exact = dijkstra(g, 0, 7, weight_fn, DRIVE)
            guided = a_star(g, 0, 7, weight_fn, DRIVE, 1.0)
            self.assertEqual(exact.found, guided.found)
            if exact.found:
                self.assertAlmostEqual(exact.cost, guided.cost, places=6)

    def test_graph_max_speed_keeps_time_heuristic_admissible(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        for seed in range(25):
            g = random_graph(12, 40, seed + 800)
            scale = g.max_speed_mps(DRIVE)
            exact = dijkstra(g, 0, 9, weight_fn, DRIVE)
            guided = a_star(g, 0, 9, weight_fn, DRIVE, scale)
            if exact.found:
                self.assertAlmostEqual(exact.cost, guided.cost, places=6)

    def test_non_positive_scale_falls_back_to_dijkstra(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        g = random_graph(10, 30, 901)
        exact = dijkstra(g, 0, 5, weight_fn, DRIVE)
        guided = a_star(g, 0, 5, weight_fn, DRIVE, 0.0)
        self.assertEqual(exact.found, guided.found)
        self.assertAlmostEqual(exact.cost, guided.cost, places=9)

class TestPermissions(unittest.TestCase):
    def test_unroutable_classes_permit_nothing(self):
        for highway in ("construction", "proposed", "razed", "elevator"):
            self.assertEqual(permissions_for(highway), 0, highway)

    def test_motorway_excludes_pedestrians(self):
        self.assertFalse(permissions_for("motorway") & WALK)
        self.assertTrue(permissions_for("motorway") & DRIVE)

    def test_footway_excludes_vehicles(self):
        self.assertEqual(permissions_for("footway"), WALK)

    def test_unknown_class_defaults_to_all_modes(self):
        allowed = permissions_for("some_new_osm_value")
        self.assertTrue(allowed & DRIVE and allowed & BIKE and allowed & WALK)

class TestMaxspeedParsing(unittest.TestCase):
    def test_semicolon_separated_values_take_the_first(self):
        self.assertEqual(parse_maxspeed("50;30"), 50.0)
        self.assertEqual(parse_maxspeed("40|60"), 40.0)
        self.assertEqual(parse_maxspeed("30, 50"), 30.0)

    def test_unit_conversion(self):
        self.assertAlmostEqual(parse_maxspeed("30 mph"), 48.2803, places=3)
        self.assertAlmostEqual(parse_maxspeed("20 knots"), 37.04, places=2)

    def test_unusable_values(self):
        for value in (None, True, 0, -5, "", "signals", "walk", "RU:urban", "none"):
            self.assertIsNone(parse_maxspeed(value), repr(value))

    def test_list_falls_through_to_first_parseable(self):
        self.assertEqual(parse_maxspeed(["signals", "60"]), 60.0)

if __name__ == "__main__":
    unittest.main(verbosity=2)

class TestTrafficBound(unittest.TestCase):
    """The A* heuristic needs to know how cheap an edge can possibly become."""

    def test_normal_traffic_scales_nothing(self):
        self.assertEqual(min_traffic_multiplier("drive", "normal"), 1.0)

    def test_low_traffic_can_make_an_edge_cheaper(self):
        self.assertLess(min_traffic_multiplier("drive", "low"), 1.0)

    def test_low_traffic_bound_matches_the_most_sensitive_road(self):
        self.assertAlmostEqual(min_traffic_multiplier("drive", "low"), 0.8, places=6)

    def test_heavy_traffic_never_makes_an_edge_cheaper(self):
        self.assertGreaterEqual(min_traffic_multiplier("drive", "heavy"), 1.0)

    def test_walking_and_cycling_ignore_traffic(self):
        for mode in ("walk", "bike"):
            for level in ("low", "normal", "heavy"):
                self.assertEqual(min_traffic_multiplier(mode, level), 1.0)

    def test_unknown_level_is_treated_as_neutral(self):
        self.assertEqual(min_traffic_multiplier("drive", "nonsense"), 1.0)

if __name__ == "__main__":
    unittest.main()

class TestModePermissions(unittest.TestCase):
    """Every mode's penalty table must only name roads that mode may use."""

    def test_bike_penalties_apply_only_to_roads_bikes_may_use(self):
        from routing.weights import BIKE, _BIKE_PENALTY, permissions_for
        for highway in _BIKE_PENALTY:
            self.assertTrue(permissions_for(highway) & BIKE,
                            f"bikes are penalised on {highway} but not permitted there")

    def test_walk_penalties_apply_only_to_roads_walkers_may_use(self):
        from routing.weights import WALK, _WALK_PENALTY, permissions_for
        for highway in _WALK_PENALTY:
            self.assertTrue(permissions_for(highway) & WALK,
                            f"walkers are penalised on {highway} but not permitted there")

    def test_cars_are_never_allowed_on_a_footpath(self):
        from routing.weights import DRIVE, permissions_for
        for highway in ("footway", "steps", "path", "pedestrian", "corridor"):
            self.assertFalse(permissions_for(highway) & DRIVE, highway)

    def test_walking_is_never_allowed_on_a_motorway(self):
        from routing.weights import WALK, permissions_for
        for highway in ("motorway", "motorway_link", "trunk", "trunk_link"):
            self.assertFalse(permissions_for(highway) & WALK, highway)

    def test_bikes_are_not_routed_up_steps(self):
        from routing.weights import BIKE, permissions_for
        self.assertFalse(permissions_for("steps") & BIKE)

class TestSpeedsAgainstReferences(unittest.TestCase):
    """Our speeds should agree with the reference routers and the research.

    OSRM foot.lua walking_speed = 5 km/h; bicycle.lua default_speed = 15 km/h
    with track 12 and path 13. Measured stair ascent is 0.48-0.97 m/s.
    """

    def test_walking_matches_the_reference_and_the_research(self):
        from routing.weights import WALK_SPEED_KPH
        self.assertEqual(WALK_SPEED_KPH, 5.0)

    def test_cycling_matches_the_reference(self):
        from routing.weights import BIKE_SPEED_KPH
        self.assertEqual(BIKE_SPEED_KPH, 15.0)

    def test_stair_speed_sits_inside_the_measured_range(self):
        from routing.weights import WALK_SPEED_KPH, _WALK_PENALTY
        kph = WALK_SPEED_KPH / _WALK_PENALTY["steps"]
        self.assertGreaterEqual(kph / 3.6, 0.48)
        self.assertLessEqual(kph / 3.6, 0.97)

    def test_bike_surface_speeds_match_osrm(self):
        from routing.weights import BIKE_SPEED_KPH, _BIKE_PENALTY
        self.assertAlmostEqual(BIKE_SPEED_KPH / _BIKE_PENALTY["track"], 12.0, delta=0.5)
        self.assertAlmostEqual(BIKE_SPEED_KPH / _BIKE_PENALTY["path"], 13.0, delta=0.5)

    def test_no_road_class_exceeds_the_ghana_motorway_limit(self):
        from routing.weights import _CLASS_SPEED_KPH
        for highway, kph in _CLASS_SPEED_KPH.items():
            self.assertLessEqual(kph, 100.0, highway)

    def test_campus_road_classes_stay_at_or_below_the_urban_limit(self):
        from routing.weights import _CLASS_SPEED_KPH
        for highway in ("residential", "service", "unclassified", "tertiary", "living_street"):
            self.assertLessEqual(_CLASS_SPEED_KPH[highway], 50.0, highway)
