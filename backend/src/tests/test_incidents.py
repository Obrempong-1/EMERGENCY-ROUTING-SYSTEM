"""Incident clustering, confidence scoring, expiry and the anti-prank safeguards."""

from __future__ import annotations

import unittest

import accounts
import config
import db
import incidents
from tests import support

TEST_DATABASE_URL = support.TEST_DATABASE_URL

CENTRE_LAT = 6.6745
CENTRE_LON = -1.5716
METRE_LAT = 1.0 / 111_132.0

class TestConfidenceMaths(unittest.TestCase):
    def test_no_evidence_means_no_confidence(self):
        self.assertEqual(incidents.confidence_from_evidence(0), 0.0)

    def test_confidence_rises_with_evidence(self):
        values = [incidents.confidence_from_evidence(e) for e in (0.5, 1, 2, 4)]
        self.assertEqual(values, sorted(values))

    def test_confidence_never_reaches_certainty(self):
        self.assertLess(incidents.confidence_from_evidence(1000), 1.0)

    def test_confidence_stays_in_range(self):
        for evidence in (0, 0.1, 1, 5, 50):
            value = incidents.confidence_from_evidence(evidence)
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_negative_evidence_is_clamped(self):
        self.assertEqual(incidents.confidence_from_evidence(-5), 0.0)

    def test_one_knust_report_is_already_likely(self):
        """A lone credible witness in an emergency must not read as unverified."""
        confidence = incidents.confidence_from_evidence(accounts.TRUST_KNUST)
        self.assertEqual(incidents.status_for(confidence), "likely")

    def test_one_knust_report_is_not_yet_confirmed(self):
        confidence = incidents.confidence_from_evidence(accounts.TRUST_KNUST)
        self.assertEqual(incidents.status_for(confidence), "likely")
        self.assertLess(confidence, incidents.CONFIRMED_AT)

    def test_a_lone_outsider_is_still_unverified(self):
        confidence = incidents.confidence_from_evidence(accounts.TRUST_OTHER)
        self.assertEqual(incidents.status_for(confidence), "unverified")

    def test_three_knust_reports_still_needed_to_confirm(self):
        two = incidents.confidence_from_evidence(2 * accounts.TRUST_KNUST)
        three = incidents.confidence_from_evidence(3 * accounts.TRUST_KNUST)
        self.assertEqual(incidents.status_for(two), "likely")
        self.assertEqual(incidents.status_for(three), "confirmed")

    def test_collusion_still_needs_many_outside_accounts(self):
        count = 0
        while incidents.confidence_from_evidence(count * accounts.TRUST_OTHER) \
                < incidents.CONFIRMED_AT:
            count += 1
            if count > 100:
                break
        self.assertGreaterEqual(count, 10)

    def test_two_knust_reports_reach_likely(self):
        confidence = incidents.confidence_from_evidence(2 * accounts.TRUST_KNUST)
        self.assertEqual(incidents.status_for(confidence), "likely")

    def test_outsider_needs_more_reports_than_a_member_for_likely(self):
        def reporters_needed(trust):
            count = 0
            while incidents.confidence_from_evidence(count * trust) < incidents.LIKELY_AT:
                count += 1
                if count > 100:
                    break
            return count

        self.assertGreater(reporters_needed(accounts.TRUST_OTHER),
                           reporters_needed(accounts.TRUST_KNUST))

    def test_status_bands(self):
        self.assertEqual(incidents.status_for(0.0), "unverified")
        self.assertEqual(incidents.status_for(0.34), "unverified")
        self.assertEqual(incidents.status_for(0.35), "likely")
        self.assertEqual(incidents.status_for(0.74), "likely")
        self.assertEqual(incidents.status_for(0.75), "confirmed")

    def test_override_wins_over_the_band(self):
        self.assertEqual(incidents.status_for(0.99, "false"), "false")
        self.assertEqual(incidents.status_for(0.0, "verified"), "verified")

    def test_every_kind_has_a_ttl_and_a_label(self):
        for kind in incidents.KINDS:
            self.assertIn(kind, incidents.KIND_TTL_HOURS)
            self.assertIn(kind, incidents.KIND_LABELS)

    def test_ttls_never_exceed_the_cap(self):
        for hours in incidents.KIND_TTL_HOURS.values():
            self.assertLessEqual(hours, incidents.TTL_CAP_HOURS)

    def test_suspicious_activity_expires_soonest(self):
        self.assertEqual(min(incidents.KIND_TTL_HOURS,
                             key=incidents.KIND_TTL_HOURS.get),
                         "suspicious_activity")

class TestReporting(support.SchemaFixture):
    schema = "incident_test"

    def setUp(self):
        self.truncate("incident_clusters", "incident_reports", "students")

    def _student(self, email, trust=None):
        if trust is None:
            trust = accounts.trust_for_email(email)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO students (email, trust, knust_verified)"
                    " VALUES (%s, %s, %s) RETURNING id",
                    (email, trust, accounts.is_knust_email(email)))
                student_id = cur.fetchone()[0]
            conn.commit()
        return {"id": student_id, "email": email, "trust": trust}

    def _knust(self, index):
        return self._student(f"student{index}@st.knust.edu.gh")

    def _trust_of(self, student_id):
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT trust FROM students WHERE id = %s", (student_id,))
            return float(cur.fetchone()[0])

    def _age_reports(self, minutes):
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE incident_reports"
                            " SET created_at = created_at - make_interval(mins => %s)",
                            (minutes,))
            conn.commit()

    def test_first_report_opens_a_cluster(self):
        result = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        self.assertFalse(result["corroborated"])
        self.assertTrue(result["counted"])
        self.assertEqual(result["reports"], 1)

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(incidents.IncidentError) as caught:
            incidents.report(self._knust(1), "alien_landing", CENTRE_LAT, CENTRE_LON)
        self.assertEqual(caught.exception.status, 422)

    def test_point_outside_the_service_area_is_rejected(self):
        with self.assertRaises(incidents.IncidentError) as caught:
            incidents.report(self._knust(1), "flooding", 0.0, 0.0)
        self.assertEqual(caught.exception.status, 422)

    def test_nearby_report_of_the_same_kind_corroborates(self):
        incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        second = incidents.report(self._knust(2), "flooding",
                                  CENTRE_LAT + 50 * METRE_LAT, CENTRE_LON)
        self.assertTrue(second["corroborated"])
        self.assertEqual(second["reports"], 2)
        self.assertEqual(len(incidents.live()), 1)

    def test_report_beyond_the_radius_opens_its_own_cluster(self):
        incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        second = incidents.report(self._knust(2), "flooding",
                                  CENTRE_LAT + 300 * METRE_LAT, CENTRE_LON)
        self.assertFalse(second["corroborated"])
        self.assertEqual(len(incidents.live()), 2)

    def test_different_kind_at_the_same_place_is_a_separate_cluster(self):
        incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        second = incidents.report(self._knust(2), "blocked_road", CENTRE_LAT, CENTRE_LON)
        self.assertFalse(second["corroborated"])
        self.assertEqual(len(incidents.live()), 2)

    def test_report_outside_the_time_window_opens_a_new_cluster(self):
        incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE incident_clusters"
                            " SET created_at = created_at - make_interval(mins => %s)",
                            (incidents.CLUSTER_WINDOW_MIN + 10,))
            conn.commit()
        second = incidents.report(self._knust(2), "flooding", CENTRE_LAT, CENTRE_LON)
        self.assertFalse(second["corroborated"])

    def test_same_student_reporting_twice_does_not_raise_confidence(self):
        student = self._knust(1)
        first = incidents.report(student, "flooding", CENTRE_LAT, CENTRE_LON)
        again = incidents.report(student, "flooding", CENTRE_LAT + 10 * METRE_LAT, CENTRE_LON)
        self.assertFalse(again["counted"])
        self.assertEqual(again["reports"], 1)
        self.assertAlmostEqual(again["confidence"], first["confidence"], places=2)

    def test_distinct_reporters_do_raise_confidence(self):
        first = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        second = incidents.report(self._knust(2), "flooding", CENTRE_LAT, CENTRE_LON)
        self.assertGreater(second["confidence"], first["confidence"])

    def test_three_knust_reporters_reach_confirmed(self):
        for index in range(3):
            result = incidents.report(self._knust(index), "flooding",
                                      CENTRE_LAT, CENTRE_LON)
        self.assertEqual(result["status"], "confirmed")

    def test_outsiders_cannot_confirm_as_fast_as_members(self):
        for index in range(3):
            outsider = self._student(f"outsider{index}@gmail.com")
            result = incidents.report(outsider, "flooding", CENTRE_LAT, CENTRE_LON)
        self.assertNotEqual(result["status"], "confirmed")

    def test_confidence_decays_as_reports_age(self):
        fresh = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        self._age_reports(180)
        aged = incidents.live()[0]
        self.assertLess(aged["confidence"], fresh["confidence"])

    def test_rate_limit_blocks_the_fourth_report_in_an_hour(self):
        student = self._knust(1)
        for index in range(config.INCIDENT_REPORTS_PER_HOUR):
            incidents.report(student, "flooding",
                             CENTRE_LAT + index * 200 * METRE_LAT, CENTRE_LON)
        with self.assertRaises(incidents.IncidentError) as caught:
            incidents.report(student, "flooding",
                             CENTRE_LAT - 400 * METRE_LAT, CENTRE_LON)
        self.assertEqual(caught.exception.status, 429)

    def test_expired_cluster_disappears_from_reads(self):
        incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE incident_clusters"
                            " SET expires_at = now() - interval '1 minute'")
            conn.commit()
        self.assertEqual(incidents.live(), [])

    def test_resolved_cluster_disappears_from_reads(self):
        result = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.resolve(result["id"])
        self.assertEqual(incidents.live(), [])

    def test_resolving_twice_is_refused(self):
        result = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.resolve(result["id"])
        with self.assertRaises(incidents.IncidentError) as caught:
            incidents.resolve(result["id"])
        self.assertEqual(caught.exception.status, 404)

    def test_ttl_matches_the_kind(self):
        flood = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        blocked = incidents.report(self._knust(2), "blocked_road",
                                   CENTRE_LAT + 600 * METRE_LAT, CENTRE_LON)
        self.assertLess(flood["expires_at"], blocked["expires_at"])

    def test_corroboration_extends_expiry(self):
        first = incidents.report(self._knust(1), "suspicious_activity",
                                 CENTRE_LAT, CENTRE_LON)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE incident_clusters"
                            " SET expires_at = now() + interval '5 minutes'")
            conn.commit()
        second = incidents.report(self._knust(2), "suspicious_activity",
                                  CENTRE_LAT, CENTRE_LON)
        self.assertGreater(second["expires_at"], first["expires_at"])

    def test_expiry_never_exceeds_the_cap(self):
        student_index = 0
        result = incidents.report(self._knust(student_index), "blocked_road",
                                  CENTRE_LAT, CENTRE_LON)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE incident_clusters"
                            " SET created_at = now() - make_interval(hours => %s),"
                            "     expires_at = now() + interval '1 minute'",
                            (incidents.TTL_CAP_HOURS - 1,))
            conn.commit()
        for student_index in range(1, 3):
            result = incidents.report(self._knust(student_index), "blocked_road",
                                      CENTRE_LAT, CENTRE_LON)
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT expires_at <= created_at + make_interval(hours => %s)"
                        " FROM incident_clusters WHERE id = %s",
                        (incidents.TTL_CAP_HOURS, result["id"]))
            self.assertTrue(cur.fetchone()[0])

    def test_marking_false_hides_the_incident(self):
        result = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.set_override(result["id"], "false")
        self.assertEqual(incidents.live(), [])

    def test_marking_false_decays_reporter_trust(self):
        student = self._knust(1)
        before = self._trust_of(student["id"])
        result = incidents.report(student, "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.set_override(result["id"], "false")
        after = self._trust_of(student["id"])
        self.assertAlmostEqual(after, before * incidents.FALSE_REPORT_TRUST_FACTOR, places=4)

    def test_trust_decay_weakens_future_reports(self):
        student = self._knust(1)
        first = incidents.report(student, "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.set_override(first["id"], "false")
        later = incidents.report(student, "blocked_road",
                                 CENTRE_LAT + 600 * METRE_LAT, CENTRE_LON)
        self.assertLess(later["confidence"], first["confidence"])

    def test_trust_never_decays_to_zero(self):
        student = self._knust(1)
        for _ in range(12):
            result = incidents.report(student, "flooding", CENTRE_LAT, CENTRE_LON)
            incidents.set_override(result["id"], "false")
            with db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM incident_reports")
                    cur.execute("DELETE FROM incident_clusters")
                conn.commit()
        self.assertGreater(self._trust_of(student["id"]), 0)

    def test_repeating_a_false_override_does_not_decay_trust_twice(self):
        student = self._knust(1)
        before = self._trust_of(student["id"])
        result = incidents.report(student, "flooding", CENTRE_LAT, CENTRE_LON)

        incidents.set_override(result["id"], "false")
        once = self._trust_of(student["id"])
        incidents.set_override(result["id"], "false")
        twice = self._trust_of(student["id"])

        self.assertAlmostEqual(once, before * incidents.FALSE_REPORT_TRUST_FACTOR, places=4)
        self.assertAlmostEqual(twice, once, places=6)

    def test_repeating_an_override_reports_no_further_decay(self):
        result = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        first = incidents.set_override(result["id"], "false")
        second = incidents.set_override(result["id"], "false")
        self.assertEqual(first["reporters_decayed"], 1)
        self.assertEqual(second["reporters_decayed"], 0)

    def test_changing_a_verdict_from_verified_to_false_decays_once(self):
        student = self._knust(1)
        before = self._trust_of(student["id"])
        result = incidents.report(student, "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.set_override(result["id"], "verified")
        self.assertEqual(self._trust_of(student["id"]), before)
        incidents.set_override(result["id"], "false")
        self.assertAlmostEqual(self._trust_of(student["id"]),
                               before * incidents.FALSE_REPORT_TRUST_FACTOR, places=4)

    def test_verified_override_keeps_the_incident_visible(self):
        result = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.set_override(result["id"], "verified")
        live = incidents.live()
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["status"], "verified")

    def test_verified_override_does_not_decay_trust(self):
        student = self._knust(1)
        before = self._trust_of(student["id"])
        result = incidents.report(student, "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.set_override(result["id"], "verified")
        self.assertEqual(self._trust_of(student["id"]), before)

    def test_unknown_override_is_rejected(self):
        result = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        with self.assertRaises(incidents.IncidentError) as caught:
            incidents.set_override(result["id"], "probably")
        self.assertEqual(caught.exception.status, 422)

    def test_override_on_a_missing_incident_is_a_404(self):
        with self.assertRaises(incidents.IncidentError) as caught:
            incidents.set_override(999_999, "verified")
        self.assertEqual(caught.exception.status, 404)

    def test_false_cluster_does_not_absorb_later_reports(self):
        first = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        incidents.set_override(first["id"], "false")
        second = incidents.report(self._knust(2), "flooding", CENTRE_LAT, CENTRE_LON)
        self.assertFalse(second["corroborated"])
        self.assertNotEqual(second["id"], first["id"])

    def test_live_payload_shape(self):
        incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON, "ankle deep")
        entry = incidents.live()[0]
        for field in ("id", "kind", "label", "lat", "lon", "confidence", "status",
                      "reports", "created_at", "expires_at", "expires_in_minutes"):
            self.assertIn(field, entry)

    def test_expiry_countdown_is_server_computed(self):
        result = incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        expected = incidents.KIND_TTL_HOURS["flooding"] * 60
        self.assertGreater(result["expires_in_minutes"], expected - 5)
        self.assertLessEqual(result["expires_in_minutes"], expected)

    def test_expiry_countdown_never_goes_negative(self):
        incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE incident_clusters"
                            " SET expires_at = now() - interval '2 hours'")
            conn.commit()
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT expires_at FROM incident_clusters LIMIT 1")
            self.assertEqual(incidents.minutes_until(cur.fetchone()[0]), 0)

    def test_note_is_truncated_rather_than_rejected(self):
        incidents.report(self._knust(1), "flooding", CENTRE_LAT, CENTRE_LON,
                         "x" * (incidents.MAX_NOTE_LENGTH + 50))
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT length(note) FROM incident_reports")
            self.assertEqual(cur.fetchone()[0], incidents.MAX_NOTE_LENGTH)

if __name__ == "__main__":
    unittest.main()
