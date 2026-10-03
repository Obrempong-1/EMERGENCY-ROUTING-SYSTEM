"""Supabase token verification and the campus trust tier it maps to."""

from __future__ import annotations

import unittest
from unittest import mock

import accounts
import api
import auth
import config
import db
import supabase_auth
from tests import support

TEST_DATABASE_URL = support.TEST_DATABASE_URL

PROJECT = "https://example.supabase.co"
KEY = "sb_publishable_test"

def _payload(email, user_id="11111111-1111-1111-1111-111111111111", confirmed=True):
    return {
        "id": user_id,
        "email": email,
        "email_confirmed_at": "2026-01-01T00:00:00Z" if confirmed else None,
    }

class FakeSupabase:
    """Stands in for the auth service so tests never touch the network."""

    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else {}
        self.error = error
        self.calls = 0

    def __call__(self, token):
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload

class SupabaseStub(unittest.TestCase):
    def setUp(self):
        self.saved = (config.SUPABASE_URL, config.SUPABASE_PUBLISHABLE_KEY,
                      supabase_auth._fetch_user)
        config.SUPABASE_URL = PROJECT
        config.SUPABASE_PUBLISHABLE_KEY = KEY
        supabase_auth.clear_cache()

    def tearDown(self):
        (config.SUPABASE_URL, config.SUPABASE_PUBLISHABLE_KEY,
         supabase_auth._fetch_user) = self.saved
        supabase_auth.clear_cache()

    def stub(self, payload=None, error=None):
        fake = FakeSupabase(payload, error)
        supabase_auth._fetch_user = fake
        return fake

class TestTokenVerification(SupabaseStub):
    def test_valid_token_returns_the_account(self):
        self.stub(_payload("kwame@st.knust.edu.gh"))
        user = supabase_auth.verify("good-token")
        self.assertEqual(user["email"], "kwame@st.knust.edu.gh")
        self.assertTrue(user["email_confirmed"])

    def test_unconfirmed_email_is_reported_as_such(self):
        self.stub(_payload("kwame@st.knust.edu.gh", confirmed=False))
        self.assertFalse(supabase_auth.verify("t")["email_confirmed"])

    def test_empty_token_is_rejected_without_a_call(self):
        fake = self.stub(_payload("a@b.com"))
        self.assertIsNone(supabase_auth.verify(""))
        self.assertEqual(fake.calls, 0)

    def test_absurdly_long_token_is_rejected_without_a_call(self):
        fake = self.stub(_payload("a@b.com"))
        self.assertIsNone(supabase_auth.verify("x" * (supabase_auth.MAX_TOKEN_LENGTH + 1)))
        self.assertEqual(fake.calls, 0)

    def test_rejected_token_returns_none(self):
        self.stub({})
        self.assertIsNone(supabase_auth.verify("bad-token"))

    def test_payload_without_an_email_is_refused(self):
        self.stub({"id": "abc"})
        self.assertIsNone(supabase_auth.verify("t"))

    def test_payload_without_an_id_is_refused(self):
        self.stub({"email": "a@b.com"})
        self.assertIsNone(supabase_auth.verify("t"))

    def test_unreachable_supabase_raises_rather_than_denying(self):
        self.stub(error=supabase_auth.VerificationUnavailable("down"))
        with self.assertRaises(supabase_auth.VerificationUnavailable):
            supabase_auth.verify("t")

    def test_result_is_cached(self):
        fake = self.stub(_payload("kwame@st.knust.edu.gh"))
        supabase_auth.verify("same-token")
        supabase_auth.verify("same-token")
        self.assertEqual(fake.calls, 1)

    def test_rejection_is_cached_too(self):
        fake = self.stub({})
        supabase_auth.verify("bad")
        supabase_auth.verify("bad")
        self.assertEqual(fake.calls, 1)

    def test_different_tokens_are_cached_separately(self):
        fake = self.stub(_payload("kwame@st.knust.edu.gh"))
        supabase_auth.verify("one")
        supabase_auth.verify("two")
        self.assertEqual(fake.calls, 2)

    def test_forget_drops_a_cached_token(self):
        fake = self.stub(_payload("kwame@st.knust.edu.gh"))
        supabase_auth.verify("tok")
        supabase_auth.forget("tok")
        supabase_auth.verify("tok")
        self.assertEqual(fake.calls, 2)

    def test_expired_cache_entry_is_refetched(self):
        fake = self.stub(_payload("kwame@st.knust.edu.gh"))
        original = config.TOKEN_CACHE_TTL_S
        config.TOKEN_CACHE_TTL_S = -1
        try:
            supabase_auth.verify("tok")
            supabase_auth.verify("tok")
        finally:
            config.TOKEN_CACHE_TTL_S = original
        self.assertEqual(fake.calls, 2)

    def test_missing_project_config_denies_without_a_call(self):
        fake = self.stub(_payload("a@b.com"))
        config.SUPABASE_URL = ""
        self.assertIsNone(supabase_auth.verify("t"))
        self.assertEqual(fake.calls, 0)

    def test_the_token_is_never_used_as_a_cache_key_in_clear_text(self):
        self.stub(_payload("kwame@st.knust.edu.gh"))
        supabase_auth.verify("super-secret-token")
        self.assertNotIn("super-secret-token", supabase_auth._cache)

class TestConfigGuards(unittest.TestCase):
    def setUp(self):
        self.saved = (config.DATABASE_URL, config.SUPABASE_URL,
                      config.SUPABASE_PUBLISHABLE_KEY)

    def tearDown(self):
        (config.DATABASE_URL, config.SUPABASE_URL,
         config.SUPABASE_PUBLISHABLE_KEY) = self.saved

    def test_no_database_means_auth_is_off_and_sound(self):
        config.DATABASE_URL = ""
        self.assertFalse(db.configured())
        self.assertEqual(config.auth_misconfigured(), "")

    def test_missing_project_url_is_refused(self):
        config.DATABASE_URL = "postgresql://localhost/x"
        config.SUPABASE_URL = ""
        config.SUPABASE_PUBLISHABLE_KEY = KEY
        self.assertIn("SUPABASE_URL", config.auth_misconfigured())

    def test_insecure_project_url_is_refused(self):
        config.DATABASE_URL = "postgresql://localhost/x"
        config.SUPABASE_URL = "http://example.supabase.co"
        config.SUPABASE_PUBLISHABLE_KEY = KEY
        self.assertIn("https", config.auth_misconfigured())

    def test_missing_key_is_refused(self):
        config.DATABASE_URL = "postgresql://localhost/x"
        config.SUPABASE_URL = PROJECT
        config.SUPABASE_PUBLISHABLE_KEY = ""
        self.assertIn("SUPABASE_PUBLISHABLE_KEY", config.auth_misconfigured())

    def test_sound_configuration_reports_no_problem(self):
        config.DATABASE_URL = "postgresql://localhost/x"
        config.SUPABASE_URL = PROJECT
        config.SUPABASE_PUBLISHABLE_KEY = KEY
        self.assertEqual(config.auth_misconfigured(), "")

    def test_no_database_means_no_student(self):
        config.DATABASE_URL = ""
        self.assertIsNone(auth.student_for_token("anything"))

class TestStudentLinking(support.SchemaFixture, SupabaseStub):
    schema = "auth_test"
    extra_config = {"SUPABASE_URL": PROJECT, "SUPABASE_PUBLISHABLE_KEY": KEY}

    def setUp(self):
        SupabaseStub.setUp(self)
        config.SUPABASE_URL = PROJECT
        config.SUPABASE_PUBLISHABLE_KEY = KEY
        self.truncate("students")

    def test_knust_account_is_created_fully_trusted(self):
        self.stub(_payload("kwame@st.knust.edu.gh"))
        student = auth.student_for_token("tok")
        self.assertTrue(student["knust_verified"])
        self.assertEqual(student["trust"], accounts.TRUST_KNUST)
        self.assertEqual(student["role"], "student")

    def test_community_account_is_created_at_the_lower_tier(self):
        self.stub(_payload("obrempong.kow@gmail.com"))
        student = auth.student_for_token("tok")
        self.assertFalse(student["knust_verified"])
        self.assertEqual(student["trust"], accounts.TRUST_OTHER)

    def test_lookalike_domain_cannot_pose_as_a_member(self):
        self.stub(_payload("x@knust.edu.gh.evil.com"))
        student = auth.student_for_token("tok")
        self.assertFalse(student["knust_verified"])
        self.assertEqual(student["trust"], accounts.TRUST_OTHER)

    def test_signing_in_twice_reuses_one_account(self):
        self.stub(_payload("kwame@st.knust.edu.gh"))
        first = auth.student_for_token("tok")
        supabase_auth.clear_cache()
        second = auth.student_for_token("tok")
        self.assertEqual(first["id"], second["id"])

    def test_email_is_normalised_before_linking(self):
        self.stub(_payload("  KWAME@St.Knust.Edu.Gh "))
        student = auth.student_for_token("tok")
        self.assertEqual(student["email"], "kwame@st.knust.edu.gh")
        self.assertTrue(student["knust_verified"])

    def test_auth_user_id_is_recorded(self):
        self.stub(_payload("kwame@st.knust.edu.gh", user_id="22222222-2222-2222-2222-222222222222"))
        auth.student_for_token("tok")
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT auth_user_id::text FROM students")
            self.assertEqual(cur.fetchone()[0], "22222222-2222-2222-2222-222222222222")

    def test_unconfirmed_email_is_refused(self):
        self.stub(_payload("kwame@st.knust.edu.gh", confirmed=False))
        with self.assertRaises(auth.AuthError) as caught:
            auth.student_for_token("tok")
        self.assertEqual(caught.exception.status, 403)

    def test_invalid_token_yields_no_student_and_no_row(self):
        self.stub({})
        self.assertIsNone(auth.student_for_token("bad"))
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM students")
            self.assertEqual(cur.fetchone()[0], 0)

    def test_unreachable_supabase_surfaces_as_503(self):
        self.stub(error=supabase_auth.VerificationUnavailable("down"))
        with self.assertRaises(auth.AuthError) as caught:
            auth.student_for_token("tok")
        self.assertEqual(caught.exception.status, 503)

    def test_an_existing_role_survives_a_later_sign_in(self):
        self.stub(_payload("guard@knust.edu.gh"))
        student = auth.student_for_token("tok")
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE students SET role='security' WHERE id=%s", (student["id"],))
            conn.commit()
        supabase_auth.clear_cache()
        self.assertEqual(auth.student_for_token("tok")["role"], "security")

    def test_decayed_trust_is_not_reset_by_signing_in_again(self):
        self.stub(_payload("kwame@st.knust.edu.gh"))
        student = auth.student_for_token("tok")
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE students SET trust=0.25 WHERE id=%s", (student["id"],))
            conn.commit()
        supabase_auth.clear_cache()
        self.assertEqual(auth.student_for_token("tok")["trust"], 0.25)

    def test_owner_email_signs_in_as_admin(self):
        with mock.patch.object(config, "ADMIN_EMAILS", frozenset({"owner@gmail.com"})):
            self.stub(_payload("Owner@Gmail.com"))
            self.assertEqual(auth.student_for_token("tok")["role"], "admin")

    def test_existing_account_is_promoted_once_listed_as_owner(self):
        self.stub(_payload("owner@gmail.com"))
        self.assertEqual(auth.student_for_token("tok")["role"], "student")
        supabase_auth.clear_cache()
        with mock.patch.object(config, "ADMIN_EMAILS", frozenset({"owner@gmail.com"})):
            self.assertEqual(auth.student_for_token("tok")["role"], "admin")

    def test_other_accounts_are_unaffected_by_owner_list(self):
        with mock.patch.object(config, "ADMIN_EMAILS", frozenset({"owner@gmail.com"})):
            self.stub(_payload("kwame@st.knust.edu.gh"))
            self.assertEqual(auth.student_for_token("tok")["role"], "student")

class TestAdminSetRole(support.SchemaFixture):
    """Role changes from the admin screen, including the owner lock."""

    schema = "admin_role_test"

    def setUp(self):
        self.truncate("students")
        self.admin = self._insert("boss@knust.edu.gh", "admin")
        self.editor = {"id": self.admin, "email": "boss@knust.edu.gh", "role": "admin"}
        patcher = mock.patch.object(api, "require_admin", return_value=self.editor)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _insert(self, email, role="student"):
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO students (email, role) VALUES (%s, %s) RETURNING id",
                            (email, role))
                student_id = cur.fetchone()[0]
            conn.commit()
        return student_id

    def _set(self, student_id, role):
        return api.admin_set_role(student_id, api.RoleRequest(role=role), None, None)

    def test_admin_can_grant_and_revoke_security(self):
        guard = self._insert("guard@knust.edu.gh")
        self.assertEqual(self._set(guard, "security")["role"], "security")
        self.assertEqual(self._set(guard, "student")["role"], "student")

    def test_owner_cannot_be_demoted(self):
        owner = self._insert("owner@gmail.com", "admin")
        with mock.patch.object(config, "ADMIN_EMAILS", frozenset({"owner@gmail.com"})):
            with self.assertRaises(api.HTTPException) as caught:
                self._set(owner, "student")
        self.assertEqual(caught.exception.status_code, 409)

    def test_unknown_account_is_404(self):
        with self.assertRaises(api.HTTPException) as caught:
            self._set(999_999, "security")
        self.assertEqual(caught.exception.status_code, 404)

    def test_admin_cannot_demote_themselves(self):
        with self.assertRaises(api.HTTPException) as caught:
            self._set(self.admin, "student")
        self.assertEqual(caught.exception.status_code, 409)

    def test_database_health_check_touches_the_database(self):
        self.assertEqual(api.health_db(api.Response()), {"database": "ok"})

if __name__ == "__main__":
    unittest.main()
