"""Linking a verified Supabase account to its campus trust tier."""

from __future__ import annotations

import logging

import accounts
import config
import db
import supabase_auth

logger = logging.getLogger(__name__)

class AuthError(Exception):
    """A sign-in failure that maps to an HTTP status."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail

def _student_from_row(row) -> dict:
    roles = accounts.roles_from_record(row[5] if len(row) > 5 else None, row[4])
    return {
        "id": row[0],
        "email": row[1],
        "trust": float(row[2]),
        "knust_verified": bool(row[3]),
        "roles": list(roles),
        "role": accounts.primary_role(roles),
    }

def _link(user: dict) -> dict:
    """Find or create the student record for a verified Supabase account."""
    email = accounts.normalise_email(user["email"])
    verified = accounts.is_knust_email(email)
    owner = email in config.ADMIN_EMAILS

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO students"
                " (email, trust, knust_verified, auth_user_id, role, roles)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (email) DO UPDATE"
                "   SET knust_verified = EXCLUDED.knust_verified,"
                "       auth_user_id = COALESCE(students.auth_user_id, EXCLUDED.auth_user_id),"
                "       role = CASE WHEN %s THEN 'admin' ELSE students.role END,"
                "       roles = CASE WHEN %s"
                "         THEN (SELECT ARRAY(SELECT DISTINCT unnest(students.roles || 'admin'::text)))"
                "         ELSE students.roles END"
                " RETURNING id, email, trust, knust_verified, role, roles",
                (email, accounts.trust_for_email(email), verified, user["auth_user_id"],
                 "admin" if owner else "student",
                 ["admin"] if owner else ["student"], owner, owner))
            student = _student_from_row(cur.fetchone())
        conn.commit()

    return student

def student_for_token(token: str):
    """The signed-in student, or None when the token is absent, invalid or expired."""
    if not token or not db.configured() or config.auth_misconfigured():
        return None

    try:
        user = supabase_auth.verify(token)
    except supabase_auth.VerificationUnavailable:
        logger.error("Could not verify an access token with Supabase", exc_info=True)
        raise AuthError(503, "Could not check your sign-in just now. Try again shortly.")

    if user is None:
        return None
    if not user["email_confirmed"]:
        raise AuthError(403, "Confirm your email address before continuing.")

    return _link(user)
