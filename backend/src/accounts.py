"""Account email classification and the trust tier it determines."""

from __future__ import annotations

import re

KNUST_DOMAINS = ("knust.edu.gh", "st.knust.edu.gh")

ROLES = ("student", "security", "mapper", "admin")

REPORT = "report"
RESOLVE_INCIDENTS = "resolve_incidents"
ADD_PLACES = "add_places"
EDIT_PLACES = "edit_places"
MANAGE_ROLES = "manage_roles"

CAPABILITIES = {
    "student": frozenset({REPORT}),
    "security": frozenset({REPORT, RESOLVE_INCIDENTS}),
    "mapper": frozenset({REPORT, ADD_PLACES}),
    "admin": frozenset({
        REPORT, RESOLVE_INCIDENTS, ADD_PLACES, EDIT_PLACES, MANAGE_ROLES,
    }),
}

DENIED = {
    REPORT: "Sign in to do that.",
    RESOLVE_INCIDENTS: "That is for campus security only.",
    ADD_PLACES: "Adding a place needs the mapper role.",
    EDIT_PLACES: "Changing or removing a place needs the admin role.",
    MANAGE_ROLES: "That needs the admin role.",
}

PRIMARY_ORDER = ("admin", "security", "mapper", "student")

def _as_roles(value) -> tuple:
    if isinstance(value, str):
        return (value,)
    return tuple(value or ())

def normalise_roles(value) -> tuple:
    """Valid roles in a stable order. Everyone is at least a student."""
    held = {role for role in _as_roles(value) if role in CAPABILITIES}
    held.add("student")
    return tuple(role for role in ROLES if role in held)

def capabilities(value) -> frozenset:
    """Everything the held roles allow between them."""
    granted = set()
    for role in normalise_roles(value):
        granted |= CAPABILITIES[role]
    return frozenset(granted)

def can(value, capability: str) -> bool:
    return capability in capabilities(value)

def primary_role(value) -> str:
    """The strongest role held, for display and for the legacy role column."""
    held = normalise_roles(value)
    for role in PRIMARY_ORDER:
        if role in held:
            return role
    return "student"

def may_act_as(real_roles, wanted: str) -> bool:
    """Acting as another role may only ever reduce power, never raise it."""
    return wanted in CAPABILITIES and CAPABILITIES[wanted] <= capabilities(real_roles)

TRUST_KNUST = 1.0
TRUST_OTHER = 0.25

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def normalise_email(email: str) -> str:
    return str(email or "").strip().lower()

def valid_email(email: str) -> bool:
    address = normalise_email(email)
    return bool(address) and len(address) <= 254 and _EMAIL.match(address) is not None

def email_domain(email: str) -> str:
    address = normalise_email(email)
    _, _, domain = address.rpartition("@")
    return domain

def is_knust_email(email: str) -> bool:
    """True only for an exact KNUST domain match, never a lookalike or subdomain of one."""
    return email_domain(email) in KNUST_DOMAINS

def trust_for_email(email: str) -> float:
    """Starting trust: KNUST members count fully, everyone else a quarter."""
    return TRUST_KNUST if is_knust_email(email) else TRUST_OTHER
