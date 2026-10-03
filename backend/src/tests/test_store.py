"""Place storage: the file overlay and the PostgreSQL store."""

from __future__ import annotations

import os
import tempfile
import threading
import unittest

import accounts
import config
import db
import places
import store
from tests import support

TEST_DATABASE_URL = support.TEST_DATABASE_URL

def _place(place_id, name="Pharmacy Annex", lat=6.6745, lon=-1.5716):
    return {
        "id": place_id,
        "name": name,
        "category": "medical",
        "type": "pharmacy",
        "lat": lat,
        "lon": lon,
        "phone": None,
        "opening_hours": None,
        "description": None,
        "source": "curated",
    }

class TestFilePlaceStore(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "local.json")
        self.store = store.FilePlaceStore(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_missing_file_loads_as_empty(self):
        self.assertEqual(self.store.load(), {})

    def test_added_place_round_trips(self):
        self.store.add(_place("curated/pharmacy-annex"))
        loaded = self.store.load()
        self.assertEqual([entry["id"] for entry in loaded["places"]],
                         ["curated/pharmacy-annex"])

    def test_corrupt_file_is_ignored_rather_than_crashing(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(self.store.load(), {})

    def test_load_output_feeds_merge(self):
        self.store.add(_place("curated/pharmacy-annex"))
        merged = places.merge([], {}, self.store.load())
        self.assertEqual([entry["id"] for entry in merged], ["curated/pharmacy-annex"])

    def test_file_store_selected_without_database_url(self):
        original = config.DATABASE_URL
        config.DATABASE_URL = ""
        try:
            self.assertIsInstance(store.make_place_store(self.path), store.FilePlaceStore)
        finally:
            config.DATABASE_URL = original

class TestPgPlaceStore(support.SchemaFixture):
    """Writes go to the curated_places table, where the primary key settles id races."""

    schema = "place_store_test"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.store = store.PgPlaceStore()

    def setUp(self):
        self.truncate("curated_places", "students")

    def test_empty_table_loads_in_merge_shape(self):
        loaded = self.store.load()
        self.assertEqual(loaded["places"], [])
        self.assertEqual(loaded["overrides"], [])
        self.assertEqual(loaded["exclude"], [])

    def test_added_place_round_trips(self):
        self.store.add(_place("curated/pharmacy-annex"))
        loaded = self.store.load()
        self.assertEqual(len(loaded["places"]), 1)
        entry = loaded["places"][0]
        self.assertEqual(entry["id"], "curated/pharmacy-annex")
        self.assertEqual(entry["category"], "medical")
        self.assertAlmostEqual(entry["lat"], 6.6745)

    def test_load_output_feeds_merge(self):
        self.store.add(_place("curated/pharmacy-annex"))
        merged = places.merge([], {}, self.store.load())
        self.assertEqual([entry["id"] for entry in merged], ["curated/pharmacy-annex"])

    def test_colliding_id_is_reassigned(self):
        first = self.store.add(_place("curated/pharmacy-annex"))
        second = self.store.add(_place("curated/pharmacy-annex"))
        self.assertEqual(first["id"], "curated/pharmacy-annex")
        self.assertNotEqual(second["id"], first["id"])
        self.assertEqual(len(self.store.load()["places"]), 2)

    def test_concurrent_writers_all_get_distinct_ids(self):
        ids, errors = [], []

        def write():
            try:
                ids.append(self.store.add(_place("curated/pharmacy-annex"))["id"])
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(set(ids)), 4)

    def test_schema_is_safe_to_reapply(self):
        self.store.add(_place("curated/pharmacy-annex"))
        db.apply_schema()
        ids = [entry["id"] for entry in self.store.load()["places"]]
        self.assertEqual(ids, ["curated/pharmacy-annex"])

    def test_postgres_store_selected_when_url_is_set(self):
        self.assertIsInstance(store.make_place_store("unused.json"), store.PgPlaceStore)

    def _register(self, email):
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO students (email, trust, knust_verified)"
                    " VALUES (%s, %s, %s) RETURNING trust, knust_verified",
                    (email, accounts.trust_for_email(email), accounts.is_knust_email(email)))
                row = cur.fetchone()
            conn.commit()
        return row

    def test_any_email_may_register(self):
        trust, verified = self._register("outsider@gmail.com")
        self.assertEqual(trust, accounts.TRUST_OTHER)
        self.assertFalse(verified)

    def test_knust_member_registers_fully_trusted(self):
        trust, verified = self._register("kwame@st.knust.edu.gh")
        self.assertEqual(trust, accounts.TRUST_KNUST)
        self.assertTrue(verified)

    def test_lookalike_domain_cannot_pose_as_a_knust_member(self):
        trust, verified = self._register("x@knust.edu.gh.evil.com")
        self.assertEqual(trust, accounts.TRUST_OTHER)
        self.assertFalse(verified)

    def test_default_trust_is_the_lower_tier(self):
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO students (email) VALUES ('bare@gmail.com')"
                            " RETURNING trust, knust_verified")
                trust, verified = cur.fetchone()
            conn.commit()
        self.assertEqual(trust, accounts.TRUST_OTHER)
        self.assertFalse(verified)

if __name__ == "__main__":
    unittest.main()
