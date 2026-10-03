"""Road legality, direction, surface speeds, private roads and manoeuvres."""

from __future__ import annotations

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from osm.parse import index_nodes, road_segments
from router import RoutingService
from routing.builder import build_route_graph
from routing.dijkstra import a_star, dijkstra
from routing.graph import Edge, RouteGraph
from routing.instructions import build_instructions
from routing.weights import (
    BIKE,
    DRIVE,
    PRIVATE_PENALTY,
    WALK,
    access_for,
    base_traverse_seconds,
    make_weight_fn,
    travel_seconds,
)

def node(node_id, lat, lon):
    return {"type": "node", "id": node_id, "lat": lat, "lon": lon}

def way(way_id, refs, **tags):
    return {"type": "way", "id": way_id, "nodes": refs,
            "tags": {key.replace("__", ":"): value for key, value in tags.items()}}

def build(elements) -> RouteGraph:
    return build_route_graph(road_segments(elements, index_nodes(elements)))

def single(**tags) -> RouteGraph:
    """One 111 m way from node 1 to node 2, with the given tags."""
    tags.setdefault("highway", "residential")
    return build([node(1, 6.670, -1.570), node(2, 6.671, -1.570), way(100, [1, 2], **tags)])

def edge_between(graph: RouteGraph, tail: int, head: int):
    found = [e for e in graph.neighbours(tail) if e.to_node == head]
    return found[0] if found else None

def modes(graph: RouteGraph, tail: int, head: int) -> int:
    edge = edge_between(graph, tail, head)
    return edge.allowed if edge else 0

class TestAccessTags(unittest.TestCase):
    def test_road_class_alone_allows_everything_on_a_street(self):
        self.assertEqual(access_for({"highway": "residential"}), (DRIVE | BIKE | WALK, 0))

    def test_access_no_blocks_every_mode(self):
        self.assertEqual(access_for({"highway": "residential", "access": "no"})[0], 0)

    def test_foot_no_blocks_walking_only(self):
        allowed, _ = access_for({"highway": "residential", "foot": "no"})
        self.assertEqual(allowed, DRIVE | BIKE)

    def test_motor_vehicle_no_blocks_driving_only(self):
        allowed, _ = access_for({"highway": "residential", "motor_vehicle": "no"})
        self.assertEqual(allowed, BIKE | WALK)

    def test_vehicle_no_blocks_driving_and_cycling(self):
        allowed, _ = access_for({"highway": "residential", "vehicle": "no"})
        self.assertEqual(allowed, WALK)

    def test_bicycle_yes_opens_a_footway_to_bikes(self):
        allowed, _ = access_for({"highway": "footway", "bicycle": "yes"})
        self.assertEqual(allowed, BIKE | WALK)

    def test_the_most_specific_tag_wins(self):
        allowed, _ = access_for({"highway": "residential", "access": "no", "foot": "yes"})
        self.assertEqual(allowed, WALK)

    def test_private_keeps_the_road_but_marks_it_restricted(self):
        allowed, restricted = access_for({"highway": "service", "access": "private"})
        self.assertEqual(allowed, DRIVE | BIKE | WALK)
        self.assertEqual(restricted, DRIVE | BIKE | WALK)

    def test_private_for_cars_only_leaves_walkers_unrestricted(self):
        _, restricted = access_for({"highway": "service", "motor_vehicle": "private"})
        self.assertEqual(restricted, DRIVE)

    def test_specific_permission_lifts_a_general_private_restriction(self):
        allowed, restricted = access_for(
            {"highway": "service", "access": "private", "bicycle": "yes"})
        self.assertEqual(allowed, DRIVE | BIKE | WALK)
        self.assertEqual(restricted, DRIVE | WALK)

    def test_specific_restriction_narrows_a_general_permission(self):
        allowed, restricted = access_for(
            {"highway": "residential", "access": "yes", "motor_vehicle": "private"})
        self.assertEqual(allowed, DRIVE | BIKE | WALK)
        self.assertEqual(restricted, DRIVE)

    def test_motorcar_is_more_specific_than_motor_vehicle(self):
        allowed, _ = access_for(
            {"highway": "residential", "motor_vehicle": "no", "motorcar": "yes"})
        self.assertTrue(allowed & DRIVE)

    def test_bicycle_is_more_specific_than_vehicle(self):
        allowed, _ = access_for({"highway": "residential", "vehicle": "no", "bicycle": "yes"})
        self.assertEqual(allowed, BIKE | WALK)

    def test_vehicle_tags_never_touch_walkers(self):
        allowed, restricted = access_for(
            {"highway": "residential", "vehicle": "private", "motor_vehicle": "no"})
        self.assertTrue(allowed & WALK)
        self.assertFalse(restricted & WALK)
        self.assertEqual(restricted, BIKE)

    def test_unknown_value_leaves_the_general_rule_in_force(self):
        allowed, restricted = access_for(
            {"highway": "service", "access": "private", "bicycle": "permit"})
        self.assertTrue(restricted & BIKE)
        allowed, _ = access_for({"highway": "residential", "access": "no", "foot": "unknown"})
        self.assertEqual(allowed, 0)

    def test_designated_counts_as_permission(self):
        allowed, restricted = access_for(
            {"highway": "path", "access": "no", "foot": "designated"})
        self.assertEqual((allowed, restricted), (WALK, 0))

    def test_first_of_several_values_is_used(self):
        allowed, _ = access_for({"highway": "residential", "foot": "no;yes"})
        self.assertFalse(allowed & WALK)

    def test_unroutable_class_stays_closed_whatever_the_tags(self):
        self.assertEqual(access_for({"highway": "construction", "foot": "yes"}), (0, 0))

    def test_a_road_closed_to_all_is_left_out_of_the_graph(self):
        self.assertEqual(single(access="no").edge_count, 0)

class TestDirection(unittest.TestCase):
    def test_two_way_street_is_open_both_ways_to_everyone(self):
        graph = single()
        self.assertEqual(modes(graph, 1, 2), DRIVE | BIKE | WALK)
        self.assertEqual(modes(graph, 2, 1), DRIVE | BIKE | WALK)

    def test_oneway_blocks_wrong_way_driving_but_not_walking(self):
        graph = single(oneway="yes")
        self.assertTrue(modes(graph, 1, 2) & DRIVE)
        self.assertFalse(modes(graph, 2, 1) & DRIVE)
        self.assertTrue(modes(graph, 2, 1) & WALK)

    def test_wrong_way_bike_is_pushed_at_walking_speed(self):
        graph = single(oneway="yes")
        back = edge_between(graph, 2, 1)
        self.assertTrue(back.allowed & BIKE)
        self.assertEqual(back.base_seconds[BIKE], back.base_seconds[WALK])
        ahead = edge_between(graph, 1, 2)
        self.assertLess(ahead.base_seconds[BIKE], ahead.base_seconds[WALK])

    def test_oneway_bicycle_no_lets_bikes_ride_both_ways(self):
        graph = single(oneway="yes", oneway__bicycle="no")
        back = edge_between(graph, 2, 1)
        self.assertFalse(back.allowed & DRIVE)
        self.assertLess(back.base_seconds[BIKE], back.base_seconds[WALK])

    def test_opposite_cycleway_lets_bikes_ride_both_ways(self):
        back = edge_between(single(oneway="yes", cycleway="opposite_lane"), 2, 1)
        self.assertLess(back.base_seconds[BIKE], back.base_seconds[WALK])

    def test_every_opposite_cycleway_form_allows_contraflow_riding(self):
        variants = [{"cycleway": "opposite"}, {"cycleway": "opposite_lane"},
                    {"cycleway": "opposite_track"}, {"cycleway__left": "opposite"},
                    {"cycleway__right": "opposite"}, {"cycleway__both": "opposite_lane"}]
        for tags in variants:
            with self.subTest(**tags):
                back = edge_between(single(oneway="yes", **tags), 2, 1)
                self.assertFalse(back.allowed & DRIVE)
                self.assertLess(back.base_seconds[BIKE], back.base_seconds[WALK])

    def test_ordinary_cycleway_lane_does_not_allow_contraflow(self):
        back = edge_between(single(oneway="yes", cycleway="lane"), 2, 1)
        self.assertEqual(back.base_seconds[BIKE], back.base_seconds[WALK])

    def test_oneway_bicycle_yes_makes_a_two_way_street_one_way_for_bikes(self):
        back = edge_between(single(oneway__bicycle="yes"), 2, 1)
        self.assertTrue(back.allowed & DRIVE)
        self.assertEqual(back.base_seconds[BIKE], back.base_seconds[WALK])

    def test_oneway_minus_one_runs_against_the_drawing(self):
        graph = single(oneway="-1")
        self.assertFalse(modes(graph, 1, 2) & DRIVE)
        self.assertTrue(modes(graph, 2, 1) & DRIVE)

    def test_vehicle_backward_no_removes_the_reverse_for_vehicles(self):
        graph = single(vehicle__backward="no")
        self.assertTrue(modes(graph, 1, 2) & DRIVE)
        back = modes(graph, 2, 1)
        self.assertFalse(back & DRIVE)
        self.assertTrue(back & WALK)

    def test_oneway_foot_restricts_walkers(self):
        graph = single(highway="footway", oneway__foot="yes")
        self.assertTrue(modes(graph, 1, 2) & WALK)
        self.assertEqual(modes(graph, 2, 1), 0)

    def test_no_pushing_where_walking_is_not_allowed(self):
        graph = single(highway="trunk", oneway="yes")
        self.assertIsNone(edge_between(graph, 2, 1))

class TestSurface(unittest.TestCase):
    def _seconds(self, mode, highway="residential", **tags):
        return base_traverse_seconds(mode, 1000.0, highway, 25.0, tags)

    def test_unpaved_slows_cycling_more_than_walking(self):
        bike = self._seconds("bike", surface="dirt") / self._seconds("bike")
        walk = self._seconds("walk", surface="dirt") / self._seconds("walk")
        self.assertGreater(bike, walk)
        self.assertGreater(walk, 1.0)

    def test_unpaved_caps_driving_speed(self):
        fast = base_traverse_seconds("drive", 1000.0, "primary", 40.0, {"surface": "gravel"})
        self.assertAlmostEqual(1000.0 / fast * 3.6, 20.0, places=3)

    def test_paved_surface_changes_nothing(self):
        self.assertEqual(self._seconds("bike", surface="asphalt"), self._seconds("bike"))

    def test_rough_smoothness_slows_bikes_and_cars(self):
        self.assertGreater(self._seconds("bike", smoothness="bad"), self._seconds("bike"))
        self.assertGreater(self._seconds("drive", smoothness="very_bad"), self._seconds("drive"))

    def test_track_on_dirt_is_not_penalised_twice(self):
        track = self._seconds("bike", highway="track")
        track_on_dirt = self._seconds("bike", highway="track", surface="dirt")
        dirt_road = self._seconds("bike", surface="dirt")
        self.assertEqual(track_on_dirt, max(track, dirt_road))

    def test_directional_maxspeed_applies_to_its_direction_only(self):
        graph = single(maxspeed="50", maxspeed__backward="20")
        ahead, back = edge_between(graph, 1, 2), edge_between(graph, 2, 1)
        self.assertAlmostEqual(back.base_seconds[DRIVE] / ahead.base_seconds[DRIVE], 2.5)

def _square_with_private_shortcut():
    """Nodes 1 and 2 joined by a private road and by a longer public detour.

    Node 5 hangs off node 2 by a private road and nothing else.
    """
    return [
        node(1, 6.670, -1.570), node(2, 6.670, -1.568),
        node(3, 6.671, -1.570), node(4, 6.671, -1.568),
        node(5, 6.669, -1.568),
        way(10, [1, 2], highway="service", access="private"),
        way(11, [1, 3, 4, 2], highway="residential"),
        way(12, [2, 5], highway="service", access="private"),
    ]

class TestPrivateRoads(unittest.TestCase):
    def setUp(self):
        elements = _square_with_private_shortcut()
        self.service = RoutingService.from_segments(
            road_segments(elements, index_nodes(elements)))

    def test_private_edges_are_marked(self):
        flags = sorted(bool(e.restricted & DRIVE)
                       for e in self.service.graph.neighbours(1) if e.to_node == 2)
        self.assertEqual(flags, [False, True])

    def test_penalty_applies_only_to_restricted_modes(self):
        private = edge_between(self.service.graph, 1, 2)
        avoid = make_weight_fn("drive", "fastest", "normal")
        allow = make_weight_fn("drive", "fastest", "normal", avoid_restricted=False)
        self.assertAlmostEqual(avoid(private), allow(private) * PRIVATE_PENALTY)

    def test_route_takes_the_public_detour_over_a_private_shortcut(self):
        plan = self.service.plan(6.670, -1.570, 6.670, -1.568)
        self.assertGreater(plan.distance_km, 0.3)

    def test_private_road_is_used_when_it_is_the_only_way_in(self):
        plan = self.service.plan(6.670, -1.570, 6.669, -1.568)
        self.assertGreater(plan.distance_km, 0)

    def test_nearest_reports_real_travel_time_not_the_penalty(self):
        inside = {"id": "x", "name": "Compound clinic", "lat": 6.669, "lon": -1.568}
        ranked = self.service.nearest_facilities(6.670, -1.568, [inside])
        private = edge_between(self.service.graph, 2, 5)
        real_min = travel_seconds(private, "drive", "normal") / 60.0
        self.assertAlmostEqual(ranked[0]["time_min"], real_min, delta=0.15)

    def test_coverage_measures_true_time_through_private_roads(self):
        clinic = {"id": "c", "lat": 6.670, "lon": -1.570}
        result = self.service.coverage([clinic])
        self.assertEqual(result["unreachable_segments"], 0)
        self.assertGreater(len(result["bands"][0]["lines"]), 0)

class TestHeuristicStillExact(unittest.TestCase):
    """A* with private penalties and pushed bikes still matches Dijkstra."""

    def test_a_star_matches_dijkstra_on_random_tagged_networks(self):
        for seed in range(25):
            rng = random.Random(seed)
            elements = [node(i, 6.67 + rng.random() * 0.01, -1.57 + rng.random() * 0.01)
                        for i in range(1, 9)]
            for way_id in range(14):
                a, b = rng.sample(range(1, 9), 2)
                tags = {"highway": rng.choice(["residential", "service", "footway", "track"])}
                if rng.random() < 0.3:
                    tags["oneway"] = "yes"
                if rng.random() < 0.3:
                    tags["access"] = "private"
                if rng.random() < 0.3:
                    tags["surface"] = rng.choice(["dirt", "asphalt", "compacted"])
                elements.append(way(100 + way_id, [a, b], **tags))
            graph = build(elements)
            for mode, bit in (("drive", DRIVE), ("bike", BIKE), ("walk", WALK)):
                weight_fn = make_weight_fn(mode, "fastest", "normal")
                for source in graph.nodes:
                    for target in graph.nodes:
                        exact = dijkstra(graph, source, target, weight_fn, bit)
                        guided = a_star(graph, source, target, weight_fn, bit,
                                        graph.max_speed_mps(bit) or 25.0)
                        self.assertEqual(exact.found, guided.found)
                        if exact.found:
                            self.assertAlmostEqual(exact.cost, guided.cost, places=6)

def _edge(points, name="", highway="residential", roundabout=False, tail=0, head=1):
    from routing.graph import polyline_length_m
    return Edge(tail, head, polyline_length_m(points), highway, name, DRIVE | BIKE | WALK,
                {DRIVE: 10, BIKE: 20, WALK: 60}, tuple(points), roundabout=roundabout)

class TestManoeuvres(unittest.TestCase):
    def _roundabout_graph(self):
        """A ring 10-11-12-13 with a spoke out of each node; enter at 10."""
        graph = RouteGraph()
        ring = {10: (6.6700, -1.5700), 11: (6.6702, -1.5698),
                12: (6.6704, -1.5700), 13: (6.6702, -1.5702)}
        spokes = {20: (6.6695, -1.5700), 21: (6.6702, -1.5690),
                  22: (6.6710, -1.5700), 23: (6.6702, -1.5710)}
        for node_id, (lat, lon) in {**ring, **spokes}.items():
            graph.add_node(node_id, lat, lon)
        order = [10, 11, 12, 13, 10]
        ring_edges = []
        for tail, head in zip(order, order[1:]):
            edge = _edge([ring[tail], ring[head]], roundabout=True, tail=tail, head=head)
            graph.add_edge(edge)
            ring_edges.append(edge)
        spoke_edges = {}
        for hub, spoke in zip((10, 11, 12, 13), (20, 21, 22, 23)):
            out = _edge([ring[hub], spokes[spoke]], name=f"Road {spoke}", tail=hub, head=spoke)
            graph.add_edge(out)
            spoke_edges[hub] = out
        entry = _edge([spokes[20], ring[10]], name="Road 20", tail=20, head=10)
        return graph, entry, ring_edges, spoke_edges

    def test_roundabout_names_the_exit(self):
        graph, entry, ring, spokes = self._roundabout_graph()
        route = [entry, ring[0], ring[1], spokes[12]]
        steps = build_instructions(route, "Library", graph, DRIVE)
        roundabout = [s for s in steps if s["kind"] == "roundabout"]
        self.assertEqual(len(roundabout), 1)
        self.assertIn("take the 2nd exit onto Road 22", roundabout[0]["text"])

    def test_road_after_the_exit_joins_the_roundabout_step(self):
        graph, entry, ring, spokes = self._roundabout_graph()
        hub, spoke = spokes[12].geometry
        onward = _edge([spoke, (spoke[0] + 0.001, spoke[1])], "Road 22", tail=22, head=99)
        steps = build_instructions([entry, ring[0], ring[1], spokes[12], onward],
                                   None, graph, DRIVE)
        self.assertFalse(any(s["text"].startswith("Continue onto Road 22") for s in steps))
        roundabout = next(s for s in steps if s["kind"] == "roundabout")
        self.assertGreater(roundabout["distance_m"], spokes[12].length_m + 100)

    def test_two_roads_leaving_one_node_are_two_exits(self):
        graph, entry, ring, spokes = self._roundabout_graph()
        hub = ring[0].to_node
        lat, lon = graph.coords(hub)
        graph.add_node(30, lat + 0.0003, lon + 0.0008)
        graph.add_edge(_edge([(lat, lon), (lat + 0.0003, lon + 0.0008)], "Road 30",
                             tail=hub, head=30))
        steps = build_instructions([entry, ring[0], ring[1], spokes[12]], None, graph, DRIVE)
        roundabout = next(s for s in steps if s["kind"] == "roundabout")
        self.assertIn("3rd exit", roundabout["text"])

    def test_entry_only_road_is_not_counted_as_an_exit(self):
        graph, entry, ring, spokes = self._roundabout_graph()
        graph.adj[ring[0].to_node] = [e for e in graph.adj[ring[0].to_node]
                                      if e.roundabout]
        steps = build_instructions([entry, ring[0], ring[1], spokes[12]], None, graph, DRIVE)
        roundabout = next(s for s in steps if s["kind"] == "roundabout")
        self.assertIn("1st exit", roundabout["text"])

    def test_exits_closed_to_the_mode_are_not_counted(self):
        graph, entry, ring, spokes = self._roundabout_graph()
        spokes[11].allowed = WALK
        steps = build_instructions([entry, ring[0], ring[1], spokes[12]], None, graph, DRIVE)
        roundabout = next(s for s in steps if s["kind"] == "roundabout")
        self.assertIn("1st exit", roundabout["text"])

    def test_roundabout_without_a_graph_still_reads_sensibly(self):
        _, entry, ring, spokes = self._roundabout_graph()
        steps = build_instructions([entry, ring[0], spokes[11]])
        self.assertTrue(any("At the roundabout, exit onto Road 21" in s["text"] for s in steps))

    def test_short_unnamed_connector_is_absorbed_into_the_road(self):
        a = _edge([(6.6700, -1.5700), (6.6710, -1.5700)], "Long Road")
        link = _edge([(6.6710, -1.5700), (6.67103, -1.5700)], "", "service")
        b = _edge([(6.67103, -1.5700), (6.6720, -1.5700)], "Long Road")
        steps = [s for s in build_instructions([a, link, b]) if s["kind"] != "arrive"]
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["road"], "Long Road")

    def test_short_connector_at_a_turn_is_not_absorbed(self):
        a = _edge([(6.6700, -1.5700), (6.6710, -1.5700)], "Long Road")
        link = _edge([(6.6710, -1.5700), (6.6710, -1.56997)], "", "service")
        b = _edge([(6.6710, -1.56997), (6.6720, -1.56997)], "Long Road")
        steps = [s for s in build_instructions([a, link, b]) if s["kind"] != "arrive"]
        self.assertGreater(len(steps), 1)

    def test_short_connector_between_different_roads_is_not_absorbed(self):
        a = _edge([(6.6700, -1.5700), (6.6710, -1.5700)], "Long Road")
        link = _edge([(6.6710, -1.5700), (6.67103, -1.5700)], "", "service")
        b = _edge([(6.67103, -1.5700), (6.6720, -1.5700)], "Other Road")
        steps = [s for s in build_instructions([a, link, b]) if s["kind"] != "arrive"]
        self.assertEqual([s["road"] for s in steps], ["Long Road", "the service", "Other Road"])

    def test_long_unnamed_stretch_is_not_absorbed(self):
        a = _edge([(6.6700, -1.5700), (6.6710, -1.5700)], "Long Road")
        link = _edge([(6.6710, -1.5700), (6.6720, -1.5700)], "", "service")
        b = _edge([(6.6720, -1.5700), (6.6730, -1.5700)], "Long Road")
        steps = [s for s in build_instructions([a, link, b]) if s["kind"] != "arrive"]
        self.assertEqual(len(steps), 3)

    def test_same_named_road_changing_class_stays_one_step(self):
        a = _edge([(6.6700, -1.5700), (6.6710, -1.5700)], "Long Road", "tertiary")
        b = _edge([(6.6710, -1.5700), (6.6720, -1.5700)], "Long Road", "residential")
        steps = [s for s in build_instructions([a, b]) if s["kind"] != "arrive"]
        self.assertEqual(len(steps), 1)

    def test_two_unnamed_roads_at_a_turn_stay_separate(self):
        north = _edge([(6.6700, -1.5700), (6.6710, -1.5700)], "", "footway")
        east = _edge([(6.6710, -1.5700), (6.6710, -1.5690)], "", "footway")
        steps = [s for s in build_instructions([north, east]) if s["kind"] != "arrive"]
        self.assertEqual(len(steps), 2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
