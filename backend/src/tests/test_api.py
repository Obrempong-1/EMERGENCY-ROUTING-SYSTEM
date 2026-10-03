"""Endpoint-level tests for the HTTP layer."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
except ImportError:
    HTTPException = None
    TestClient = None

import accounts
import api
import config

def build_client():
    import api
    return TestClient(api.app), api

@unittest.skipIf(TestClient is None, "fastapi TestClient unavailable")
class TestUnreadyService(unittest.TestCase):
    def setUp(self):
        self.client, self.api = build_client()
        self.api.state.reset()

    def test_health_reports_503_when_the_graph_never_loaded(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ready"])

    def test_root_is_always_available(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_bounds_needs_no_graph(self):
        body = self.client.get("/bounds").json()
        self.assertIn("min_lat", body)
        self.assertLess(body["min_lat"], body["max_lat"])

    def test_routing_endpoints_refuse_until_ready(self):
        self.assertEqual(self.client.get("/locations").status_code, 503)
        self.assertEqual(self.client.get("/categories").status_code, 503)
        self.assertEqual(self.client.post("/route", json={
            "origin_lat": 6.68, "origin_lon": -1.573,
            "dest_lat": 6.686, "dest_lon": -1.574}).status_code, 503)

@unittest.skipIf(TestClient is None, "fastapi TestClient unavailable")
class TestPublicConfig(unittest.TestCase):
    def setUp(self):
        self.client, self.api = build_client()

    def test_national_numbers_are_always_present(self):
        contacts = self.client.get("/config/public").json()["emergency_contacts"]
        numbers = [c["number"] for c in contacts]
        for expected in ("112", "191", "192", "193"):
            self.assertIn(expected, numbers)

    def test_campus_line_is_omitted_when_unset(self):
        original = config.CAMPUS_SECURITY_PHONE
        config.CAMPUS_SECURITY_PHONE = ""
        try:
            contacts = self.client.get("/config/public").json()["emergency_contacts"]
            self.assertNotIn("campus_security", [c["id"] for c in contacts])
        finally:
            config.CAMPUS_SECURITY_PHONE = original

    def test_campus_line_appears_when_configured(self):
        original = config.CAMPUS_SECURITY_PHONE
        config.CAMPUS_SECURITY_PHONE = "+233300000000"
        try:
            contacts = self.client.get("/config/public").json()["emergency_contacts"]
            campus = [c for c in contacts if c["id"] == "campus_security"]
            self.assertEqual(len(campus), 1)
            self.assertEqual(campus[0]["number"], "+233300000000")
        finally:
            config.CAMPUS_SECURITY_PHONE = original

@unittest.skipIf(TestClient is None, "fastapi TestClient unavailable")
class TestNonFiniteCoordinates(unittest.TestCase):
    """NaN and Infinity are valid to Python's JSON reader but not to JSON itself.

    Pydantic rejects them, but its error detail echoes the offending value, which
    then cannot be serialised into the 422 response. Without a handler that turns
    into an unauthenticated 500 on a public endpoint.
    """

    def setUp(self):
        self.client, self.api = build_client()

    def _route(self, literal):
        return self.client.post(
            "/route",
            content=('{"origin_lat":%s,"origin_lon":-1.57,'
                     '"dest_lat":6.68,"dest_lon":-1.56}' % literal),
            headers={"Content-Type": "application/json"},
        )

    def test_nan_is_a_client_error_not_a_server_error(self):
        self.assertEqual(self._route("NaN").status_code, 422)

    def test_infinity_is_a_client_error_not_a_server_error(self):
        self.assertEqual(self._route("Infinity").status_code, 422)

    def test_negative_infinity_is_a_client_error(self):
        self.assertEqual(self._route("-Infinity").status_code, 422)

    def test_the_error_body_is_serialisable_and_readable(self):
        body = self._route("NaN").json()
        self.assertIn("detail", body)
        self.assertIsInstance(body["detail"], str)

    def test_an_ordinary_out_of_range_value_still_reports_422(self):
        self.assertEqual(self._route("999").status_code, 422)

@unittest.skipIf(TestClient is None, "fastapi TestClient unavailable")
class TestActingRole(unittest.TestCase):
    """Acting as another role may only reduce access, never raise it."""

    def setUp(self):
        self.client, self.api = build_client()
        self.saved = api.auth.student_for_token

    def tearDown(self):
        api.auth.student_for_token = self.saved

    def _signed_in_as(self, role):
        api.auth.student_for_token = lambda token: (
            {"id": 1, "email": "a@b.com", "trust": 1.0,
             "knust_verified": True, "role": role} if token else None)

    def _me(self, acting=None):
        headers = {"Authorization": "Bearer t"}
        if acting:
            headers["X-Acting-Role"] = acting
        return self.client.get("/auth/me", headers=headers)

    def test_admin_can_act_as_student(self):
        self._signed_in_as("admin")
        body = self._me("student").json()["student"]
        self.assertEqual(body["role"], "student")
        self.assertEqual(body["real_role"], "admin")

    def test_admin_can_act_as_security(self):
        self._signed_in_as("admin")
        self.assertEqual(self._me("security").json()["student"]["role"], "security")

    def test_student_cannot_act_as_security(self):
        self._signed_in_as("student")
        self.assertEqual(self._me("security").status_code, 403)

    def test_student_cannot_act_as_admin(self):
        self._signed_in_as("student")
        self.assertEqual(self._me("admin").status_code, 403)

    def test_security_cannot_act_as_admin(self):
        self._signed_in_as("security")
        self.assertEqual(self._me("admin").status_code, 403)

    def test_unknown_role_is_refused(self):
        self._signed_in_as("admin")
        self.assertEqual(self._me("wizard").status_code, 422)

    def test_no_header_leaves_the_real_role(self):
        self._signed_in_as("admin")
        body = self._me().json()["student"]
        self.assertEqual(body["role"], "admin")
        self.assertNotIn("real_role", body)

    def test_an_admin_acting_as_student_loses_admin_endpoints(self):
        self._signed_in_as("admin")
        response = self.client.get("/admin/students", headers={
            "Authorization": "Bearer t", "X-Acting-Role": "student"})
        self.assertEqual(response.status_code, 403)

@unittest.skipIf(TestClient is None, "fastapi TestClient unavailable")
class TestAuthEndpoints(unittest.TestCase):
    """With no database no account can exist, so /auth/me answers "nobody"."""

    def setUp(self):
        self.client, self.api = build_client()

    def test_me_reports_nobody_rather_than_failing(self):
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["student"])

    def test_me_ignores_a_bearer_token_it_cannot_verify(self):
        response = self.client.get("/auth/me",
                                   headers={"Authorization": "Bearer nonsense"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["student"])

    def test_forget_accepts_a_token_and_returns_no_content(self):
        response = self.client.post("/auth/forget",
                                    headers={"Authorization": "Bearer nonsense"})
        self.assertEqual(response.status_code, 204)

    def test_forget_without_a_token_is_still_fine(self):
        self.assertEqual(self.client.post("/auth/forget").status_code, 204)

@unittest.skipIf(TestClient is None, "fastapi TestClient unavailable")
class TestPlaceEditingAuthorisation(unittest.TestCase):
    """Adding a place needs the mapper role, and is attributable to an account."""

    def setUp(self):
        self.client, self.api = build_client()
        self.saved = api.require_place_author
        self.payload = {"name": "Test", "category": "security",
                        "lat": 6.68050, "lon": -1.57330}

    def tearDown(self):
        api.require_place_author = self.saved

    def _as(self, student):
        def stub(authorization, acting_role=None):
            if student is None:
                raise HTTPException(status_code=401, detail="Sign in to do that.")
            if not accounts.can(student["role"], accounts.ADD_PLACES):
                raise HTTPException(status_code=403,
                                    detail=accounts.DENIED[accounts.ADD_PLACES])
            return student
        api.require_place_author = stub

    def test_anonymous_request_is_refused(self):
        self._as(None)
        self.assertEqual(self.client.post("/places", json=self.payload).status_code, 401)

    def test_ordinary_student_is_refused(self):
        self._as({"id": 1, "role": "student"})
        response = self.client.post("/places", json=self.payload)
        self.assertEqual(response.status_code, 403)
        self.assertIn("mapper", response.json()["detail"])

    def test_campus_security_is_refused(self):
        """Answering incidents is not the same job as maintaining the map."""
        self._as({"id": 1, "role": "security"})
        response = self.client.post("/places", json=self.payload)
        self.assertEqual(response.status_code, 403)

    def test_no_shared_token_is_consulted_any_more(self):
        self.assertFalse(hasattr(config, "PLACE_EDIT_TOKEN"))
        self.assertFalse(hasattr(config, "PLACE_EDITING_ENABLED"))
        self.assertFalse(hasattr(config, "place_editing_misconfigured"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
