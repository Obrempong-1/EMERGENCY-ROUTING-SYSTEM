"""Role capabilities and the downgrade-only view-as rule."""

from __future__ import annotations

import unittest

import accounts

class TestCapabilities(unittest.TestCase):
    def test_every_role_has_capabilities(self):
        for role in accounts.ROLES:
            self.assertIn(role, accounts.CAPABILITIES)

    def test_unknown_role_gets_the_weakest_set(self):
        self.assertEqual(accounts.capabilities("wizard"),
                         accounts.capabilities("student"))

    def test_admin_holds_every_capability(self):
        for role in accounts.ROLES:
            self.assertLessEqual(accounts.capabilities(role),
                                 accounts.capabilities("admin"))

    def test_only_mappers_and_admins_add_places(self):
        allowed = {r for r in accounts.ROLES if accounts.can(r, accounts.ADD_PLACES)}
        self.assertEqual(allowed, {"mapper", "admin"})

    def test_security_cannot_add_places(self):
        self.assertFalse(accounts.can("security", accounts.ADD_PLACES))

    def test_only_security_and_admins_resolve_incidents(self):
        allowed = {r for r in accounts.ROLES
                   if accounts.can(r, accounts.RESOLVE_INCIDENTS)}
        self.assertEqual(allowed, {"security", "admin"})

    def test_mappers_cannot_resolve_incidents(self):
        self.assertFalse(accounts.can("mapper", accounts.RESOLVE_INCIDENTS))

    def test_only_admins_edit_or_remove_places(self):
        for capability in (accounts.EDIT_PLACES, accounts.MANAGE_ROLES):
            allowed = {r for r in accounts.ROLES if accounts.can(r, capability)}
            self.assertEqual(allowed, {"admin"})

    def test_every_role_may_report(self):
        for role in accounts.ROLES:
            self.assertTrue(accounts.can(role, accounts.REPORT))

    def test_every_capability_has_a_refusal_message(self):
        for capability in accounts.CAPABILITIES["admin"]:
            self.assertIn(capability, accounts.DENIED)

class TestRoleCombinations(unittest.TestCase):
    def test_a_student_can_also_be_a_mapper(self):
        held = ["student", "mapper"]
        self.assertTrue(accounts.can(held, accounts.REPORT))
        self.assertTrue(accounts.can(held, accounts.ADD_PLACES))
        self.assertFalse(accounts.can(held, accounts.RESOLVE_INCIDENTS))

    def test_security_can_also_be_a_mapper(self):
        held = ["security", "mapper"]
        self.assertTrue(accounts.can(held, accounts.RESOLVE_INCIDENTS))
        self.assertTrue(accounts.can(held, accounts.ADD_PLACES))
        self.assertFalse(accounts.can(held, accounts.MANAGE_ROLES))

    def test_capabilities_are_the_union_of_what_is_held(self):
        self.assertEqual(
            accounts.capabilities(["security", "mapper"]),
            accounts.capabilities("security") | accounts.capabilities("mapper"))

    def test_everyone_is_at_least_a_student(self):
        self.assertIn("student", accounts.normalise_roles(["mapper"]))
        self.assertIn("student", accounts.normalise_roles([]))

    def test_unknown_roles_are_dropped(self):
        self.assertEqual(accounts.normalise_roles(["mapper", "wizard"]),
                         ("student", "mapper"))

    def test_a_bare_string_is_accepted_as_one_role(self):
        self.assertEqual(accounts.capabilities("admin"),
                         accounts.capabilities(["admin"]))

    def test_order_does_not_matter(self):
        self.assertEqual(accounts.normalise_roles(["mapper", "security"]),
                         accounts.normalise_roles(["security", "mapper"]))

    def test_primary_role_prefers_the_senior_one(self):
        self.assertEqual(accounts.primary_role(["student", "mapper"]), "mapper")
        self.assertEqual(accounts.primary_role(["security", "mapper"]), "security")
        self.assertEqual(accounts.primary_role(["admin", "mapper"]), "admin")
        self.assertEqual(accounts.primary_role([]), "student")

    def test_holding_both_allows_acting_as_either(self):
        held = ["security", "mapper"]
        self.assertTrue(accounts.may_act_as(held, "security"))
        self.assertTrue(accounts.may_act_as(held, "mapper"))
        self.assertTrue(accounts.may_act_as(held, "student"))
        self.assertFalse(accounts.may_act_as(held, "admin"))

class TestLegacyRoleColumn(unittest.TestCase):
    """A record whose role lives only in the column roles replaced."""

    def test_legacy_role_is_honoured_when_the_array_is_default(self):
        self.assertEqual(accounts.roles_from_record(["student"], "security"),
                         ("student", "security"))

    def test_legacy_role_is_honoured_when_the_array_is_missing(self):
        self.assertEqual(accounts.roles_from_record(None, "admin"),
                         ("student", "admin"))

    def test_the_array_wins_when_it_says_more(self):
        self.assertEqual(accounts.roles_from_record(["student", "mapper"], "student"),
                         ("student", "mapper"))

    def test_a_plain_student_stays_a_student(self):
        self.assertEqual(accounts.roles_from_record(["student"], "student"),
                         ("student",))

    def test_no_legacy_role_changes_nothing(self):
        self.assertEqual(accounts.roles_from_record(["student", "security"], ""),
                         ("student", "security"))

    def test_an_unknown_legacy_role_is_ignored(self):
        self.assertEqual(accounts.roles_from_record(["student"], "wizard"),
                         ("student",))


class TestMayActAs(unittest.TestCase):
    def test_admin_may_act_as_anything(self):
        for role in accounts.ROLES:
            self.assertTrue(accounts.may_act_as("admin", role))

    def test_security_may_step_down_to_student(self):
        self.assertTrue(accounts.may_act_as("security", "student"))

    def test_security_may_not_become_admin(self):
        self.assertFalse(accounts.may_act_as("security", "admin"))

    def test_sideways_moves_are_refused_when_only_one_is_held(self):
        self.assertFalse(accounts.may_act_as("security", "mapper"))
        self.assertFalse(accounts.may_act_as("mapper", "security"))

    def test_student_may_not_escalate(self):
        for role in ("security", "mapper", "admin"):
            self.assertFalse(accounts.may_act_as("student", role))

    def test_acting_as_your_own_role_is_allowed(self):
        for role in accounts.ROLES:
            self.assertTrue(accounts.may_act_as(role, role))

    def test_unknown_target_role_is_refused(self):
        self.assertFalse(accounts.may_act_as("admin", "superuser"))

    def test_no_role_can_ever_gain_a_capability(self):
        for real in accounts.ROLES:
            for wanted in accounts.ROLES:
                if accounts.may_act_as(real, wanted):
                    self.assertLessEqual(accounts.capabilities(wanted),
                                         accounts.capabilities(real))

if __name__ == "__main__":
    unittest.main()
