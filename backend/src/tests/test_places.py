"""Tests for the curated campus places layer."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import places

logging.getLogger('places').setLevel(logging.CRITICAL)

BOUNDS = {"min_lat": 6.65, "max_lat": 6.70, "min_lon": -1.60, "max_lon": -1.55}

def osm_place(place_id, name, category="facility", lat=6.674, lon=-1.571, type_="building"):
    return {"id": place_id, "name": name, "type": type_, "category": category,
            "lat": lat, "lon": lon, "phone": None, "opening_hours": None,
            "description": None}

class TestMerge(unittest.TestCase):
    def setUp(self):
        self.osm = [
            osm_place("way/1", "University Administration Building"),
            osm_place("way/2", "Security Office"),
            osm_place("way/3", "Security Room"),
            osm_place("node/4", "Ghana Police", "police", 6.688, -1.568),
        ]

    def test_no_curation_returns_the_osm_list(self):
        merged = places.merge(self.osm, {})
        self.assertEqual(len(merged), len(self.osm))
        self.assertEqual([m["id"] for m in merged], [o["id"] for o in self.osm])

    def test_override_by_osm_id_recategorises_in_place(self):
        merged = places.merge(self.osm, {"overrides": [
            {"match": {"osm_id": "way/1"}, "category": "administration"}]})
        self.assertEqual(len(merged), len(self.osm))
        target = next(m for m in merged if m["id"] == "way/1")
        self.assertEqual(target["category"], "administration")

    def test_override_does_not_mutate_the_input(self):
        places.merge(self.osm, {"overrides": [
            {"match": {"osm_id": "way/1"}, "category": "administration"}]})
        self.assertEqual(self.osm[0]["category"], "facility")

    def test_name_override_is_exact_not_substring(self):
        merged = places.merge(self.osm, {"overrides": [
            {"match": {"name": "Security Office"}, "category": "security"}]})
        by_id = {m["id"]: m for m in merged}
        self.assertEqual(by_id["way/2"]["category"], "security")
        self.assertEqual(by_id["way/3"]["category"], "facility")

    def test_unknown_match_is_ignored(self):
        merged = places.merge(self.osm, {"overrides": [
            {"match": {"osm_id": "way/999"}, "category": "security"}]})
        self.assertEqual(len(merged), len(self.osm))

    def test_exclude_removes_a_place(self):
        merged = places.merge(self.osm, {"exclude": [{"match": {"osm_id": "node/4"}}]})
        self.assertEqual(len(merged), len(self.osm) - 1)
        self.assertNotIn("node/4", [m["id"] for m in merged])

    def test_curated_place_is_appended(self):
        merged = places.merge(self.osm, {"places": [
            {"name": "J. Harper Building", "category": "student_services",
             "lat": 6.675, "lon": -1.572}]})
        self.assertEqual(len(merged), len(self.osm) + 1)
        added = merged[-1]
        self.assertEqual(added["id"], "curated/j-harper-building")
        self.assertEqual(added["category"], "student_services")

    def test_curated_id_collision_is_suffixed(self):
        merged = places.merge(self.osm, {"places": [
            {"name": "Annex", "category": "security", "lat": 6.675, "lon": -1.572},
            {"name": "Annex", "category": "security", "lat": 6.676, "lon": -1.573}]})
        ids = [m["id"] for m in merged if m["id"].startswith("curated/")]
        self.assertEqual(ids, ["curated/annex", "curated/annex-2"])

    def test_near_duplicate_of_an_osm_place_is_skipped(self):
        merged = places.merge(self.osm, {"places": [
            {"name": "Security Office", "category": "security",
             "lat": 6.674, "lon": -1.571}]})
        self.assertEqual(len(merged), len(self.osm))

    def test_same_name_far_away_is_kept(self):
        merged = places.merge(self.osm, {"places": [
            {"name": "Security Office", "category": "security",
             "lat": 6.690, "lon": -1.560}]})
        self.assertEqual(len(merged), len(self.osm) + 1)

    def test_malformed_places_are_skipped(self):
        merged = places.merge(self.osm, {"places": [
            {"name": "", "category": "security", "lat": 6.675, "lon": -1.572},
            {"name": "No Category", "lat": 6.675, "lon": -1.572},
            {"name": "Bad Coords", "category": "security", "lat": "x", "lon": None},
            {"name": "Infinite", "category": "security",
             "lat": float("inf"), "lon": -1.572}]})
        self.assertEqual(len(merged), len(self.osm))

    def test_local_overlay_applies_after_the_committed_file(self):
        merged = places.merge(
            self.osm,
            {"overrides": [{"match": {"osm_id": "way/1"}, "category": "administration"}]},
            {"overrides": [{"match": {"osm_id": "way/1"}, "category": "security"}]})
        self.assertEqual(next(m for m in merged if m["id"] == "way/1")["category"],
                         "security")

class TestValidation(unittest.TestCase):
    def valid(self, **overrides):
        payload = {"name": "J. Harper Building", "category": "student_services",
                   "lat": 6.675, "lon": -1.572}
        payload.update(overrides)
        return payload

    def test_a_good_payload_has_no_errors(self):
        self.assertEqual(places.validate_new_place(self.valid(), BOUNDS), [])

    def test_non_finite_coordinates_are_rejected(self):
        for value in (float("inf"), float("-inf"), float("nan")):
            self.assertTrue(places.validate_new_place(self.valid(lat=value), BOUNDS))

    def test_out_of_bounds_is_rejected(self):
        self.assertTrue(places.validate_new_place(self.valid(lat=5.60, lon=-0.18), BOUNDS))

    def test_empty_and_overlong_names_are_rejected(self):
        self.assertTrue(places.validate_new_place(self.valid(name="  "), BOUNDS))
        self.assertTrue(places.validate_new_place(
            self.valid(name="x" * (places.MAX_NAME_LENGTH + 1)), BOUNDS))

    def test_unknown_category_is_rejected(self):
        self.assertTrue(places.validate_new_place(self.valid(category="canteen"), BOUNDS))

    def test_booleans_are_not_coordinates(self):
        self.assertTrue(places.validate_new_place(self.valid(lat=True), BOUNDS))

class TestAtomicAppend(unittest.TestCase):
    def test_append_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "local.json")
            places.append_place(path, {"id": "curated/a", "name": "A"})
            payload = places.load_file(path)
            self.assertEqual(len(payload["places"]), 1)
            self.assertEqual(payload["places"][0]["id"], "curated/a")

    def test_missing_file_loads_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(places.load_file(os.path.join(directory, "nope.json")), {})

    def test_concurrent_appends_all_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "local.json")
            threads = [threading.Thread(target=places.append_place,
                                        args=(path, {"id": f"curated/{i}", "name": str(i)}))
                       for i in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(len(payload["places"]), 8)
            self.assertEqual({p["id"] for p in payload["places"]},
                             {f"curated/{i}" for i in range(8)})

class TestSlugId(unittest.TestCase):
    def test_slug_is_derived_from_the_name(self):
        self.assertEqual(places.slug_id("J. Harper Building", set()),
                         "curated/j-harper-building")

    def test_punctuation_only_name_still_yields_an_id(self):
        self.assertTrue(places.slug_id("!!!", set()).startswith("curated/"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
