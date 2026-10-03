"""Email classification and trust tiers, including lookalike-domain rejection."""

from __future__ import annotations

import unittest

import accounts

class TestKnustDetection(unittest.TestCase):
    def test_student_domain_is_knust(self):
        self.assertTrue(accounts.is_knust_email("kwame@st.knust.edu.gh"))

    def test_staff_domain_is_knust(self):
        self.assertTrue(accounts.is_knust_email("lecturer@knust.edu.gh"))

    def test_case_and_padding_are_ignored(self):
        self.assertTrue(accounts.is_knust_email("  Kwame@ST.KNUST.EDU.GH "))

    def test_unrelated_domain_is_not_knust(self):
        self.assertFalse(accounts.is_knust_email("someone@gmail.com"))

    def test_suffix_lookalike_is_rejected(self):
        self.assertFalse(accounts.is_knust_email("a@knust.edu.gh.evil.com"))

    def test_prefix_lookalike_is_rejected(self):
        self.assertFalse(accounts.is_knust_email("a@notknust.edu.gh"))

    def test_other_subdomain_is_rejected(self):
        self.assertFalse(accounts.is_knust_email("a@mail.knust.edu.gh"))

    def test_domain_in_local_part_is_rejected(self):
        self.assertFalse(accounts.is_knust_email("knust.edu.gh@gmail.com"))

    def test_second_at_sign_does_not_confuse_the_domain(self):
        self.assertFalse(accounts.is_knust_email("a@gmail.com@knust.edu.gh.evil.com"))

class TestTrustTiers(unittest.TestCase):
    def test_knust_member_starts_fully_trusted(self):
        self.assertEqual(accounts.trust_for_email("kwame@st.knust.edu.gh"),
                         accounts.TRUST_KNUST)

    def test_outsider_starts_at_the_lower_tier(self):
        self.assertEqual(accounts.trust_for_email("someone@gmail.com"),
                         accounts.TRUST_OTHER)

    def test_outsider_needs_more_corroboration_than_a_member(self):
        ratio = accounts.TRUST_KNUST / accounts.TRUST_OTHER
        self.assertGreaterEqual(ratio, 4)

    def test_trust_stays_within_the_schema_bounds(self):
        for value in (accounts.TRUST_KNUST, accounts.TRUST_OTHER):
            self.assertGreater(value, 0)
            self.assertLessEqual(value, 1)

class TestEmailValidation(unittest.TestCase):
    def test_plain_address_is_valid(self):
        self.assertTrue(accounts.valid_email("kwame@st.knust.edu.gh"))

    def test_blank_is_invalid(self):
        self.assertFalse(accounts.valid_email("   "))

    def test_none_is_invalid(self):
        self.assertFalse(accounts.valid_email(None))

    def test_missing_domain_dot_is_invalid(self):
        self.assertFalse(accounts.valid_email("kwame@localhost"))

    def test_whitespace_inside_is_invalid(self):
        self.assertFalse(accounts.valid_email("kwame mensah@knust.edu.gh"))

    def test_overlong_address_is_invalid(self):
        self.assertFalse(accounts.valid_email("a" * 250 + "@knust.edu.gh"))

    def test_normalisation_lowercases_and_trims(self):
        self.assertEqual(accounts.normalise_email("  A@B.COM "), "a@b.com")

if __name__ == "__main__":
    unittest.main()
