"""Tests for the routing service layer."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routing.graph import Edge, RouteGraph, haversine_m
from routing.weights import BIKE, DRIVE, WALK, base_traverse_seconds, drive_speed_kph
import config
from router import NoRouteError, RoutingService, SnapError

NODES = {
    1: (6.6740, -1.5730),
    2: (6.6740, -1.5712),
    3: (6.6740, -1.5694),
    4: (6.6727, -1.5712),
}

def _edge(graph: RouteGraph, tail: int, head: int, highway: str, name: str,
          allowed: int) -> None:
    lat1, lon1 = graph.coords(tail)
    lat2, lon2 = graph.coords(head)
    length = haversine_m(lat1, lon1, lat2, lon2)
    drive_kph = drive_speed_kph(highway, None)
    graph.add_edge(Edge(
        from_node=tail,
        to_node=head,
        length_m=length,
        highway=highway,
        name=name,
        allowed=allowed,
        base_seconds={
            DRIVE: base_traverse_seconds("drive", length, highway, drive_kph),
            BIKE: base_traverse_seconds("bike", length, highway, drive_kph),
            WALK: base_traverse_seconds("walk", length, highway, drive_kph),
        },
        geometry=((lat1, lon1), (lat2, lon2)),
    ))

def build_service() -> RoutingService:
    graph = RouteGraph()
    for node_id, (lat, lon) in NODES.items():
        graph.add_node(node_id, lat, lon)
    for tail, head in ((1, 2), (2, 1), (2, 3), (3, 2)):
        _edge(graph, tail, head, "residential", "Main Road", DRIVE | BIKE | WALK)
    for tail, head in ((2, 4), (4, 2)):
        _edge(graph, tail, head, "footway", "", WALK)
    return RoutingService(graph)

class TestPlan(unittest.TestCase):
    def setUp(self):
        self.service = build_service()

    def test_plan_returns_consistent_totals(self):
        plan = self.service.plan(6.6740, -1.5730, 6.6740, -1.5694)
        self.assertGreater(plan.distance_km, 0)
        self.assertGreater(plan.time_min, 0)
        self.assertEqual(plan.diagnostics["edges_in_route"], 2)
        self.assertEqual(plan.diagnostics["algorithm"], "A*")

    def test_access_legs_are_included_in_totals(self):
        on_node = self.service.plan(6.6740, -1.5730, 6.6740, -1.5694)
        offset = self.service.plan(6.6744, -1.5730, 6.6740, -1.5694)
        self.assertGreater(offset.snap["origin_m"], 0)
        self.assertGreater(offset.distance_km, on_node.distance_km)
        self.assertGreater(offset.time_min, on_node.time_min)

    def test_polyline_starts_and_ends_at_requested_coordinates(self):
        plan = self.service.plan(6.6744, -1.5731, 6.6741, -1.5693)
        self.assertEqual(plan.path[0], [6.6744, -1.5731])
        self.assertEqual(plan.path[-1], [6.6741, -1.5693])

    def test_polyline_has_no_duplicate_consecutive_points(self):
        plan = self.service.plan(6.6740, -1.5730, 6.6740, -1.5694)
        for first, second in zip(plan.path, plan.path[1:]):
            self.assertNotEqual(first, second)

    def test_instructions_end_with_arrival(self):
        plan = self.service.plan(
            6.6740, -1.5730, 6.6740, -1.5694, destination_name="Great Hall")
        self.assertEqual(plan.instructions[-1]["kind"], "arrive")
        self.assertIn("Great Hall", plan.instructions[-1]["text"])

    def test_dijkstra_and_astar_agree_at_every_traffic_level(self):
        for mode in ("drive", "bike", "walk"):
            for level in ("low", "normal", "heavy"):
                with self.subTest(mode=mode, traffic=level):
                    exact = self.service.plan(
                        6.6740, -1.5730, 6.6740, -1.5694,
                        transport_mode=mode, traffic_level=level, algorithm="dijkstra")
                    guided = self.service.plan(
                        6.6740, -1.5730, 6.6740, -1.5694,
                        transport_mode=mode, traffic_level=level, algorithm="astar")
                    self.assertAlmostEqual(guided.time_min, exact.time_min, places=6)
                    self.assertAlmostEqual(guided.distance_km, exact.distance_km, places=6)

    def test_low_traffic_widens_the_heuristic_scale(self):
        normal = self.service._heuristic_scale("fastest", DRIVE, "drive", "normal")
        low = self.service._heuristic_scale("fastest", DRIVE, "drive", "low")
        self.assertGreater(low, normal)

    def test_heuristic_scale_is_unchanged_for_heavy_traffic(self):
        normal = self.service._heuristic_scale("fastest", DRIVE, "drive", "normal")
        heavy = self.service._heuristic_scale("fastest", DRIVE, "drive", "heavy")
        self.assertEqual(heavy, normal)

    def test_dijkstra_and_astar_agree(self):
        args = (6.6740, -1.5730, 6.6740, -1.5694)
        exact = self.service.plan(*args, algorithm="dijkstra")
        guided = self.service.plan(*args, algorithm="astar")
        self.assertAlmostEqual(exact.distance_km, guided.distance_km, places=6)
        self.assertAlmostEqual(exact.time_min, guided.time_min, places=6)
        self.assertEqual(exact.diagnostics["algorithm"], "Dijkstra")

    def test_far_origin_is_refused_with_a_distance(self):
        with self.assertRaises(SnapError) as caught:
            self.service.plan(6.7100, -1.5300, 6.6740, -1.5694)
        self.assertEqual(caught.exception.which, "origin")
        self.assertIsNotNone(caught.exception.distance_m)
        self.assertGreater(caught.exception.distance_m, config.SNAP_TOLERANCE_M)

    def test_far_destination_is_refused(self):
        with self.assertRaises(SnapError) as caught:
            self.service.plan(6.6740, -1.5730, 6.7100, -1.5300)
        self.assertEqual(caught.exception.which, "destination")

    def test_driving_snaps_past_a_footpath_only_node_to_the_road(self):
        drive = self.service.plan(6.6740, -1.5730, 6.6727, -1.5712, transport_mode="drive")
        walk = self.service.plan(6.6740, -1.5730, 6.6727, -1.5712, transport_mode="walk")
        self.assertGreater(drive.snap["destination_m"], 100.0)
        self.assertLess(walk.snap["destination_m"], 1.0)

    def test_driving_never_traverses_a_footpath(self):
        plan = self.service.plan(6.6740, -1.5730, 6.6727, -1.5712, transport_mode="drive")
        self.assertTrue(all(step["road"] != "the footway" for step in plan.instructions))

    def test_footpath_only_destination_is_refused_when_no_road_is_near(self):
        graph = RouteGraph()
        graph.add_node(1, 6.6740, -1.5730)
        graph.add_node(2, 6.6740, -1.5712)
        graph.add_node(3, 6.6600, -1.5712)
        graph.add_node(4, 6.6601, -1.5712)
        for tail, head in ((1, 2), (2, 1)):
            _edge(graph, tail, head, "residential", "Main Road", DRIVE | WALK)
        for tail, head in ((3, 4), (4, 3)):
            _edge(graph, tail, head, "footway", "", WALK)

        service = RoutingService(graph)
        with self.assertRaises(SnapError):
            service.plan(6.6740, -1.5730, 6.6600, -1.5712, transport_mode="drive")

    def test_unreachable_component_raises_no_route(self):
        graph = RouteGraph()
        graph.add_node(1, 6.6740, -1.5730)
        graph.add_node(2, 6.6740, -1.5712)
        graph.add_node(3, 6.6300, -1.5694)
        graph.add_node(4, 6.6300, -1.5676)
        for tail, head in ((1, 2), (2, 1)):
            _edge(graph, tail, head, "residential", "A", DRIVE | WALK)
        for tail, head in ((3, 4), (4, 3)):
            _edge(graph, tail, head, "residential", "B", DRIVE | WALK)

        service = RoutingService(graph)
        with self.assertRaises(NoRouteError):
            service.plan(6.6740, -1.5730, 6.6300, -1.5694)

    def test_shortest_and_fastest_both_report_a_duration(self):
        for objective in ("fastest", "shortest"):
            plan = self.service.plan(
                6.6740, -1.5730, 6.6740, -1.5694, objective=objective)
            self.assertGreater(plan.time_min, 0, objective)

    def test_heavy_traffic_increases_the_driving_estimate(self):
        args = (6.6740, -1.5730, 6.6740, -1.5694)
        normal = self.service.plan(*args, traffic_level="normal")
        heavy = self.service.plan(*args, traffic_level="heavy")
        self.assertGreater(heavy.time_min, normal.time_min)

    def test_traffic_does_not_affect_walking(self):
        args = (6.6740, -1.5730, 6.6740, -1.5694)
        normal = self.service.plan(*args, transport_mode="walk", traffic_level="normal")
        heavy = self.service.plan(*args, transport_mode="walk", traffic_level="heavy")
        self.assertEqual(normal.time_min, heavy.time_min)

class TestNearestFacilities(unittest.TestCase):
    def setUp(self):
        self.service = build_service()
        self.candidates = [
            {"id": "far", "name": "Far Clinic", "lat": 6.6740, "lon": -1.5694},
            {"id": "near", "name": "Near Clinic", "lat": 6.6740, "lon": -1.5712},
        ]

    def test_results_are_sorted_by_travel_time(self):
        results = self.service.nearest_facilities(6.6740, -1.5730, self.candidates)
        self.assertEqual([r["id"] for r in results], ["near", "far"])
        self.assertLessEqual(results[0]["time_min"], results[1]["time_min"])

    def test_limit_is_respected(self):
        results = self.service.nearest_facilities(
            6.6740, -1.5730, self.candidates, limit=1)
        self.assertEqual(len(results), 1)

    def test_unsnappable_candidates_are_dropped(self):
        results = self.service.nearest_facilities(
            6.6740, -1.5730, [{"id": "x", "lat": 6.9, "lon": -1.2}])
        self.assertEqual(results, [])

    def test_malformed_candidates_are_ignored(self):
        results = self.service.nearest_facilities(
            6.6740, -1.5730,
            [{"id": "bad"}, {"id": "near", "lat": 6.6740, "lon": -1.5712}],
        )
        self.assertEqual([r["id"] for r in results], ["near"])

    def test_far_source_is_refused(self):
        with self.assertRaises(SnapError):
            self.service.nearest_facilities(6.7100, -1.5300, self.candidates)

class TestNearestOnTheSameRoad(unittest.TestCase):
    """A facility on the same one-way block as the caller must still be reachable."""

    def setUp(self):
        graph = RouteGraph()
        graph.add_node(10, 6.6740, -1.5730)
        graph.add_node(11, 6.6740, -1.5710)
        _edge(graph, 10, 11, "residential", "One Way Street", DRIVE | BIKE | WALK)
        self.service = RoutingService(graph)
        self.facility = {"id": "clinic", "name": "Clinic",
                         "lat": 6.6740, "lon": -1.5716}

    def test_facility_ahead_on_a_one_way_block_is_returned(self):
        results = self.service.nearest_facilities(
            6.6740, -1.5724, [self.facility], transport_mode="drive")
        self.assertEqual([entry["id"] for entry in results], ["clinic"])

    def test_the_reported_time_reflects_the_short_hop(self):
        results = self.service.nearest_facilities(
            6.6740, -1.5724, [self.facility], transport_mode="drive")
        self.assertLess(results[0]["distance_km"], 0.2)

    def test_plan_already_handles_the_same_case(self):
        plan = self.service.plan(6.6740, -1.5724, 6.6740, -1.5716,
                                 transport_mode="drive")
        self.assertLess(plan.distance_km, 0.2)

class TestCoverage(unittest.TestCase):
    def setUp(self):
        self.service = build_service()
        self.facility = {"id": "f1", "name": "Clinic", "lat": 6.6740, "lon": -1.5730}

    def test_bands_cover_every_usable_segment(self):
        result = self.service.coverage([self.facility])
        drawn = sum(len(band["lines"]) for band in result["bands"])
        usable = {frozenset((e.from_node, e.to_node))
                  for adjacency in self.service.graph.adj.values()
                  for e in adjacency if e.allowed & DRIVE}
        self.assertEqual(drawn + result["unreachable_segments"], len(usable))

    def test_the_facility_sits_in_the_fastest_band(self):
        result = self.service.coverage([self.facility])
        self.assertGreater(len(result["bands"][0]["lines"]), 0)

    def test_every_line_has_at_least_two_points(self):
        result = self.service.coverage([self.facility])
        for band in result["bands"]:
            for line in band["lines"]:
                self.assertGreaterEqual(len(line), 2)

    def test_footways_are_absent_when_driving(self):
        drive = self.service.coverage([self.facility], transport_mode="drive")
        walk = self.service.coverage([self.facility], transport_mode="walk")
        drive_lines = sum(len(b["lines"]) for b in drive["bands"])
        walk_lines = sum(len(b["lines"]) for b in walk["bands"])
        self.assertLess(drive_lines, walk_lines)

    def test_a_second_facility_never_slows_anything(self):
        one = self.service.coverage([self.facility])
        two = self.service.coverage([self.facility,
                                     {"id": "f2", "lat": 6.6740, "lon": -1.5694}])
        self.assertGreaterEqual(len(two["bands"][0]["lines"]),
                                len(one["bands"][0]["lines"]))

    def test_band_labels_are_ordered_and_open_ended(self):
        result = self.service.coverage([self.facility])
        self.assertEqual(result["bands"][0]["label"], "Under 2 min")
        self.assertIsNone(result["bands"][-1]["max_seconds"])

    def test_unplaceable_facilities_raise(self):
        with self.assertRaises(NoRouteError):
            self.service.coverage([{"id": "x", "lat": 6.9, "lon": -1.2}])

    def test_malformed_facilities_are_ignored(self):
        result = self.service.coverage([{"id": "bad"}, self.facility])
        self.assertEqual(result["facility_count"], 1)

    def test_coordinates_are_rounded(self):
        result = self.service.coverage([self.facility])
        for band in result["bands"]:
            for line in band["lines"]:
                for lat, lon in line:
                    self.assertLessEqual(len(str(lat).split(".")[-1]), 5)

if __name__ == "__main__":
    unittest.main(verbosity=2)
