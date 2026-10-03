"""Tests for the OpenStreetMap parsing layer."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from osm.geometry import local_scale, ring_centroid
from osm.parse import facilities, index_nodes, road_segments
from routing.builder import build_route_graph
from routing.graph import haversine_m, polyline_length_m
from routing.weights import BIKE, DRIVE, WALK

def node(node_id, lat, lon, **tags):
    element = {"type": "node", "id": node_id, "lat": lat, "lon": lon}
    if tags:
        element["tags"] = tags
    return element

def way(way_id, refs, **tags):
    return {"type": "way", "id": way_id, "nodes": refs, "tags": tags}

class TestGeometry(unittest.TestCase):
    def test_square_centroid_is_its_middle(self):
        ring = [(6.670, -1.570), (6.670, -1.568), (6.672, -1.568), (6.672, -1.570)]
        lat, lon = ring_centroid(ring)
        self.assertAlmostEqual(lat, 6.671, places=6)
        self.assertAlmostEqual(lon, -1.569, places=6)

    def test_closed_and_open_rings_agree(self):
        ring = [(6.670, -1.570), (6.670, -1.568), (6.672, -1.568), (6.672, -1.570)]
        self.assertEqual(ring_centroid(ring), ring_centroid(ring + [ring[0]]))

    def test_l_shape_centroid_is_area_weighted_not_vertex_mean(self):
        ring = [(0.0, 0.0), (0.0, 2.0), (1.0, 2.0), (1.0, 1.0), (2.0, 1.0), (2.0, 0.0)]
        lat, lon = ring_centroid(ring)
        vertex_lat = sum(p[0] for p in ring) / len(ring)
        self.assertNotAlmostEqual(lat, vertex_lat, places=3)
        self.assertTrue(0.0 < lat < 2.0 and 0.0 < lon < 2.0)

    def test_degenerate_ring_falls_back_to_vertex_mean(self):
        collinear = [(6.670, -1.570), (6.671, -1.570), (6.672, -1.570)]
        lat, lon = ring_centroid(collinear)
        self.assertAlmostEqual(lat, 6.671, places=6)
        self.assertAlmostEqual(lon, -1.570, places=6)

    def test_two_point_ring_is_the_midpoint(self):
        lat, lon = ring_centroid([(6.670, -1.570), (6.672, -1.570)])
        self.assertAlmostEqual(lat, 6.671, places=6)

    def test_empty_geometry_is_rejected(self):
        with self.assertRaises(ValueError):
            ring_centroid([])

    def test_longitude_metres_shrink_with_latitude(self):
        _lat_m, equator = local_scale(0.0)
        _lat_m2, knust = local_scale(6.6745)
        self.assertLess(knust, equator)

    def test_polyline_length_matches_summed_haversine(self):
        points = [(6.670, -1.570), (6.671, -1.570), (6.671, -1.568)]
        expected = (haversine_m(6.670, -1.570, 6.671, -1.570)
                    + haversine_m(6.671, -1.570, 6.671, -1.568))
        self.assertAlmostEqual(polyline_length_m(points), expected, places=9)

class TestNodeIndexing(unittest.TestCase):
    def test_nodes_are_indexed_by_id(self):
        nodes = index_nodes([node(1, 6.670, -1.570), node(2, 6.671, -1.571)])
        self.assertEqual(nodes[1], (6.670, -1.570))
        self.assertEqual(len(nodes), 2)

    def test_malformed_nodes_are_skipped(self):
        nodes = index_nodes([{"type": "node", "id": 1}, node(2, 6.671, -1.571)])
        self.assertEqual(list(nodes), [2])

class TestSegmentSplitting(unittest.TestCase):
    def setUp(self):
        self.nodes = [node(i, 6.670 + i * 0.001, -1.570) for i in range(1, 6)]

    def test_a_way_with_no_junction_becomes_one_segment(self):
        elements = self.nodes + [way(100, [1, 2, 3, 4, 5], highway="residential")]
        segments = road_segments(elements, index_nodes(elements))
        self.assertEqual(len(segments), 1)
        self.assertEqual((segments[0].start, segments[0].end), (1, 5))
        self.assertEqual(len(segments[0].geometry), 5)

    def test_a_shared_node_splits_the_way(self):
        """Intermediate vertices stay as geometry; shared nodes become junctions."""
        elements = self.nodes + [
            way(100, [1, 2, 3, 4, 5], highway="residential"),
            way(200, [3, 1], highway="residential"),
        ]
        segments = road_segments(elements, index_nodes(elements))
        spans = sorted((s.start, s.end) for s in segments)
        self.assertIn((1, 3), spans)
        self.assertIn((3, 5), spans)

    def test_intermediate_vertices_are_kept_as_geometry(self):
        elements = self.nodes + [way(100, [1, 2, 3, 4, 5], highway="residential")]
        segment = road_segments(elements, index_nodes(elements))[0]
        self.assertEqual(segment.geometry[1], (6.672, -1.570))

    def test_non_highway_ways_are_ignored(self):
        elements = self.nodes + [way(100, [1, 2, 3], building="yes")]
        self.assertEqual(road_segments(elements, index_nodes(elements)), [])

    def test_segments_with_missing_nodes_are_dropped(self):
        elements = [node(1, 6.670, -1.570)] + [way(100, [1, 999], highway="residential")]
        self.assertEqual(road_segments(elements, index_nodes(elements)), [])

class TestOneway(unittest.TestCase):
    def _segment(self, **tags):
        nodes = [node(1, 6.670, -1.570), node(2, 6.671, -1.570)]
        elements = nodes + [way(100, [1, 2], highway="residential", **tags)]
        return road_segments(elements, index_nodes(elements))[0]

    def test_default_is_two_way(self):
        segment = self._segment()
        self.assertTrue(segment.forward and segment.backward)

    def test_oneway_yes(self):
        segment = self._segment(oneway="yes")
        self.assertTrue(segment.forward)
        self.assertFalse(segment.backward)

    def test_oneway_minus_one_reverses(self):
        segment = self._segment(oneway="-1")
        self.assertFalse(segment.forward)
        self.assertTrue(segment.backward)

    def test_oneway_no_is_two_way(self):
        segment = self._segment(oneway="no")
        self.assertTrue(segment.forward and segment.backward)

    def test_roundabout_is_implicitly_oneway(self):
        segment = self._segment(junction="roundabout")
        self.assertTrue(segment.forward)
        self.assertFalse(segment.backward)

    def test_pedestrians_keep_contraflow_and_bikes_are_pushed(self):
        nodes = [node(1, 6.670, -1.570), node(2, 6.671, -1.570)]
        elements = nodes + [way(100, [1, 2], highway="residential", oneway="yes")]
        graph = build_route_graph(road_segments(elements, index_nodes(elements)))
        back = [e for e in graph.neighbours(2) if e.to_node == 1]
        self.assertEqual(len(back), 1)
        self.assertFalse(back[0].allowed & DRIVE)
        self.assertTrue(back[0].allowed & WALK)
        self.assertTrue(back[0].allowed & BIKE)
        self.assertEqual(back[0].base_seconds[BIKE], back[0].base_seconds[WALK])

    def test_oneway_blocks_vehicles_in_the_wrong_direction(self):
        nodes = [node(1, 6.670, -1.570), node(2, 6.671, -1.570)]
        elements = nodes + [way(100, [1, 2], highway="residential", oneway="yes")]
        graph = build_route_graph(road_segments(elements, index_nodes(elements)))
        forward = [e for e in graph.neighbours(1) if e.to_node == 2]
        self.assertTrue(forward[0].allowed & DRIVE)

class TestFacilities(unittest.TestCase):
    KEYS = ("amenity", "building")

    def test_named_node_becomes_a_facility(self):
        elements = [node(1, 6.670, -1.570, name="Clinic", amenity="clinic")]
        found = facilities(elements, index_nodes(elements), self.KEYS)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].osm_id, "node/1")
        self.assertEqual((found[0].lat, found[0].lon), (6.670, -1.570))

    def test_named_way_is_reduced_to_its_centroid(self):
        corners = [node(1, 6.670, -1.570), node(2, 6.670, -1.568),
                   node(3, 6.672, -1.568), node(4, 6.672, -1.570)]
        elements = corners + [way(100, [1, 2, 3, 4, 1], name="Hall", building="yes")]
        found = facilities(elements, index_nodes(elements), self.KEYS)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0].lat, 6.671, places=6)
        self.assertEqual(found[0].osm_id, "way/100")

    def test_unnamed_elements_are_ignored(self):
        elements = [node(1, 6.670, -1.570, amenity="clinic")]
        self.assertEqual(facilities(elements, index_nodes(elements), self.KEYS), [])

    def test_elements_without_a_wanted_key_are_ignored(self):
        elements = [node(1, 6.670, -1.570, name="Tree", natural="tree")]
        self.assertEqual(facilities(elements, index_nodes(elements), self.KEYS), [])

if __name__ == "__main__":
    unittest.main(verbosity=2)
