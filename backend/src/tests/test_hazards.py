"""Reported incidents as routing hazards."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from osm.parse import index_nodes, road_segments
from router import RoutingService
from routing.dijkstra import a_star, dijkstra
from routing.hazards import HazardMap, hazards_from_incidents
from routing.weights import BIKE, DRIVE, WALK, make_weight_fn

def node(node_id, lat, lon):
    return {"type": "node", "id": node_id, "lat": lat, "lon": lon}

def way(way_id, refs, **tags):
    return {"type": "way", "id": way_id, "nodes": refs, "tags": tags}

def incident(kind="blocked_road", status="confirmed", lat=6.670, lon=-1.569, cluster_id=1):
    return {"id": cluster_id, "kind": kind, "label": kind.replace("_", " ").capitalize(),
            "status": status, "lat": lat, "lon": lon}

def square() -> RoutingService:
    """Corners 1 and 2 joined directly (221 m) and by a detour through 3 and 4 (443 m).

    Every corner is a junction, and node 5 is a cul-de-sac reached only from 2.
    """
    elements = [
        node(1, 6.670, -1.570), node(2, 6.670, -1.568),
        node(3, 6.671, -1.570), node(4, 6.671, -1.568), node(5, 6.669, -1.568),
        way(10, [1, 2], highway="residential", name="Direct Road"),
        way(11, [1, 3], highway="residential", name="West Road"),
        way(12, [3, 4], highway="residential", name="North Road"),
        way(13, [4, 2], highway="residential", name="East Road"),
        way(14, [2, 5], highway="residential", name="Dead End"),
    ]
    return RoutingService.from_segments(road_segments(elements, index_nodes(elements)))

class TestWhichIncidentsCount(unittest.TestCase):
    def test_unverified_reports_change_nothing(self):
        self.assertEqual(hazards_from_incidents([incident(status="unverified")]), ())

    def test_likely_and_confirmed_both_count(self):
        found = hazards_from_incidents([incident(status="likely", cluster_id=1),
                                        incident(status="confirmed", cluster_id=2)])
        self.assertEqual([h.status for h in found], ["likely", "confirmed"])

    def test_security_verified_counts_as_confirmed(self):
        (hazard,) = hazards_from_incidents([incident(status="verified")])
        self.assertEqual(hazard.status, "confirmed")
        self.assertEqual(hazard.factor(DRIVE), 50.0)

    def test_reports_marked_false_are_ignored(self):
        self.assertEqual(hazards_from_incidents([incident(status="false")]), ())

    def test_unknown_kind_and_bad_coordinates_are_ignored(self):
        self.assertEqual(hazards_from_incidents([incident(kind="meteor")]), ())
        broken = incident()
        broken["lat"] = "north"
        self.assertEqual(hazards_from_incidents([broken]), ())

    def test_blocked_road_mostly_affects_vehicles(self):
        (hazard,) = hazards_from_incidents([incident()])
        self.assertGreater(hazard.factor(DRIVE), hazard.factor(WALK))
        self.assertEqual(hazard.factor(BIKE), hazard.factor(DRIVE))

    def test_suspicious_activity_does_not_slow_cars(self):
        (hazard,) = hazards_from_incidents([incident(kind="suspicious_activity")])
        self.assertEqual(hazard.factor(DRIVE), 1.0)
        self.assertGreater(hazard.factor(WALK), 1.0)

class TestHazardMap(unittest.TestCase):
    def setUp(self):
        self.service = square()
        self.direct = next(e for e in self.service.graph.neighbours(1) if e.to_node == 2)
        self.detour = next(e for e in self.service.graph.neighbours(1) if e.to_node == 3)

    def test_only_roads_near_the_incident_are_affected(self):
        hazards = HazardMap(hazards_from_incidents([incident()]))
        self.assertEqual(hazards.factor(self.direct, DRIVE), 50.0)
        self.assertEqual(hazards.factor(self.detour, DRIVE), 1.0)

    def test_without_hazards_the_cost_function_is_untouched(self):
        weight_fn = make_weight_fn("drive", "fastest", "normal")
        self.assertIs(HazardMap(()).wrap(weight_fn, DRIVE), weight_fn)

    def test_overlapping_hazards_use_the_strongest_not_the_product(self):
        hazards = HazardMap(hazards_from_incidents([
            incident(kind="blocked_road", cluster_id=1),
            incident(kind="flooding", cluster_id=2)]))
        self.assertEqual(hazards.factor(self.direct, DRIVE), 50.0)

class TestRoadHazardsStayOnTheirRoad(unittest.TestCase):
    """A blockage beside a junction must not close the roads across from it."""

    def setUp(self):
        elements = [
            node(1, 6.670, -1.570), node(2, 6.670, -1.568),
            node(6, 6.67027, -1.570), node(7, 6.67027, -1.568),
            way(10, [1, 2], highway="residential", name="Blocked Road"),
            way(20, [6, 7], highway="residential", name="Parallel Road"),
        ]
        self.service = RoutingService.from_segments(road_segments(elements, index_nodes(elements)))
        self.blocked = next(e for e in self.service.graph.neighbours(1) if e.to_node == 2)
        self.parallel = next(e for e in self.service.graph.neighbours(6) if e.to_node == 7)

    def test_blockage_touches_only_the_road_it_was_reported_on(self):
        hazards = HazardMap(hazards_from_incidents([incident(lat=6.67002)]), self.service.index)
        self.assertGreater(hazards.factor(self.blocked, DRIVE), 1.0)
        self.assertEqual(hazards.factor(self.parallel, DRIVE), 1.0)

    def test_flooding_covers_the_whole_area(self):
        hazards = HazardMap(hazards_from_incidents([incident(kind="flooding", lat=6.67002)]),
                            self.service.index)
        self.assertGreater(hazards.factor(self.parallel, DRIVE), 1.0)

    def test_blockage_far_from_any_road_affects_nothing(self):
        hazards = HazardMap(hazards_from_incidents([incident(lat=6.6750)]), self.service.index)
        self.assertEqual(hazards.factor(self.blocked, DRIVE), 1.0)

class TestRoutingAroundHazards(unittest.TestCase):
    def setUp(self):
        self.service = square()

    def test_clear_road_is_taken_when_nothing_is_reported(self):
        plan = self.service.plan(6.670, -1.570, 6.670, -1.568)
        self.assertLess(plan.distance_km, 0.25)
        self.assertEqual(plan.hazards, [])

    def test_confirmed_blockage_sends_the_car_around(self):
        plan = self.service.plan(6.670, -1.570, 6.670, -1.568,
                                 hazards=hazards_from_incidents([incident()]))
        self.assertGreater(plan.distance_km, 0.4)
        self.assertEqual(plan.hazards, [])

    def test_unverified_report_does_not_reroute(self):
        plan = self.service.plan(6.670, -1.570, 6.670, -1.568,
                                 hazards=hazards_from_incidents([incident(status="unverified")]))
        self.assertLess(plan.distance_km, 0.25)

    def test_likely_blockage_reroutes_cars_but_not_walkers(self):
        likely = hazards_from_incidents([incident(status="likely")])
        car = self.service.plan(6.670, -1.570, 6.670, -1.568, hazards=likely)
        walk = self.service.plan(6.670, -1.570, 6.670, -1.568, transport_mode="walk",
                                 hazards=likely)
        self.assertGreater(car.distance_km, 0.4)
        self.assertLess(walk.distance_km, 0.25)
        self.assertEqual([h["kind"] for h in walk.hazards], ["blocked_road"])

    def test_hazard_on_the_only_way_still_gives_a_route_with_a_warning(self):
        blocked = hazards_from_incidents([incident(lat=6.6695, lon=-1.568)])
        plan = self.service.plan(6.670, -1.570, 6.669, -1.568, hazards=blocked)
        self.assertGreater(plan.distance_km, 0)
        self.assertEqual([h["id"] for h in plan.hazards], [1])

    def test_reported_time_stays_the_real_travel_time(self):
        clear = self.service.plan(6.670, -1.570, 6.669, -1.568)
        blocked = self.service.plan(6.670, -1.570, 6.669, -1.568,
                                    hazards=hazards_from_incidents([incident(lat=6.6695,
                                                                             lon=-1.568)]))
        self.assertEqual(clear.time_min, blocked.time_min)

    def test_nearest_ranking_respects_a_blockage(self):
        near = {"id": "near", "name": "Near clinic", "lat": 6.670, "lon": -1.568}
        far = {"id": "far", "name": "Far clinic", "lat": 6.671, "lon": -1.5705}
        clear = self.service.nearest_facilities(6.670, -1.570, [near, far])
        self.assertEqual(clear[0]["id"], "near")
        blocked = self.service.nearest_facilities(
            6.670, -1.570, [near, far], hazards=hazards_from_incidents([incident()]))
        self.assertEqual(blocked[0]["id"], "far")

    def test_coverage_shows_the_area_behind_a_blockage_as_slower(self):
        clinic = {"id": "c", "lat": 6.670, "lon": -1.570}

        def slowness(result):
            return sum(band["index"] * len(band["lines"]) for band in result["bands"])

        clear = self.service.coverage([clinic], transport_mode="walk")
        blocked = self.service.coverage([clinic], transport_mode="walk",
                                        hazards=hazards_from_incidents([incident()]))
        self.assertGreater(slowness(blocked), slowness(clear))

    def test_a_star_still_matches_dijkstra_with_hazards(self):
        graph = self.service.graph
        hazards = HazardMap(hazards_from_incidents([incident()]))
        for mode, bit in (("drive", DRIVE), ("walk", WALK)):
            weight_fn = hazards.wrap(make_weight_fn(mode, "fastest", "normal"), bit)
            for source in graph.nodes:
                for target in graph.nodes:
                    exact = dijkstra(graph, source, target, weight_fn, bit)
                    guided = a_star(graph, source, target, weight_fn, bit,
                                    graph.max_speed_mps(bit))
                    self.assertAlmostEqual(exact.cost, guided.cost, places=6)

class TestApiHazardCache(unittest.TestCase):
    def setUp(self):
        import api
        self.api = api
        api.forget_hazards()
        self.addCleanup(api.forget_hazards)

    def test_incidents_are_read_once_then_cached(self):
        with mock.patch.object(self.api.incidents, "live", return_value=[incident()]) as live:
            first = self.api.current_hazards()
            second = self.api.current_hazards()
        self.assertEqual(live.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)

    def test_forgetting_forces_a_reload(self):
        with mock.patch.object(self.api.incidents, "live", return_value=[]) as live:
            self.api.current_hazards()
            self.api.forget_hazards()
            self.api.current_hazards()
        self.assertEqual(live.call_count, 2)

    def test_database_failure_keeps_the_last_known_hazards(self):
        with mock.patch.object(self.api.incidents, "live", return_value=[incident()]):
            known = self.api.current_hazards()
        self.api.forget_hazards()
        with mock.patch.object(self.api.incidents, "live", side_effect=RuntimeError("down")):
            self.assertEqual(self.api.current_hazards(), known)

class TestLoneReportDoesNotReroute(unittest.TestCase):
    """A single witness is shown as "likely" but must not divert traffic."""

    def test_one_report_is_ignored_by_routing(self):
        lone = {**incident(status="likely"), "reports": 1}
        self.assertEqual(hazards_from_incidents([lone]), ())

    def test_two_reports_are_respected(self):
        pair = {**incident(status="likely"), "reports": 2}
        self.assertEqual(len(hazards_from_incidents([pair])), 1)

    def test_security_verdict_counts_even_from_one_witness(self):
        lone = {**incident(status="verified"), "reports": 1}
        (hazard,) = hazards_from_incidents([lone])
        self.assertEqual(hazard.status, "confirmed")

    def test_confirmed_is_never_filtered_on_count(self):
        lone = {**incident(status="confirmed"), "reports": 1}
        self.assertEqual(len(hazards_from_incidents([lone])), 1)

    def test_a_missing_count_is_treated_as_corroborated(self):
        self.assertEqual(len(hazards_from_incidents([incident(status="likely")])), 1)

    def test_an_unusable_count_is_treated_as_corroborated(self):
        odd = {**incident(status="likely"), "reports": None}
        self.assertEqual(len(hazards_from_incidents([odd])), 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
