"""Study-area configuration."""

from __future__ import annotations

import os
from math import cos, radians

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load_env_file(path: str) -> None:
    """Fill in unset variables from a local env file. Real environment always wins."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return

    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

for _name in (".env", ".env.local"):
    _load_env_file(os.path.join(_BACKEND_DIR, _name))

KNUST_CENTER_LAT = 6.6745
KNUST_CENTER_LON = -1.5716
SEARCH_RADIUS_METERS = 3500

SNAP_TOLERANCE_M = 250.0
PIN_SNAP_TOLERANCE_M = 80.0
PLACE_DUPLICATE_RADIUS_M = 30.0

CAMPUS_SECURITY_PHONE = os.getenv("CAMPUS_SECURITY_PHONE", "").strip()
CAMPUS_SECURITY_LABEL = os.getenv("CAMPUS_SECURITY_LABEL", "KNUST Security").strip()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DATABASE_CONNECT_TIMEOUT_S = float(os.getenv("DATABASE_CONNECT_TIMEOUT_S", "10"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
SUPABASE_TIMEOUT_S = float(os.getenv("SUPABASE_TIMEOUT_S", "10"))
TOKEN_CACHE_TTL_S = float(os.getenv("TOKEN_CACHE_TTL_S", "60"))

ADMIN_EMAILS = frozenset(
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
)

INCIDENT_REPORTS_PER_HOUR = int(os.getenv("INCIDENT_REPORTS_PER_HOUR", "3"))

def auth_misconfigured() -> str:
    """Why authentication must refuse to serve, or an empty string when it is sound."""
    if not DATABASE_URL:
        return ""
    if not SUPABASE_URL:
        return "SUPABASE_URL is not set, so access tokens cannot be verified."
    if not SUPABASE_URL.startswith("https://"):
        return f"SUPABASE_URL must be an https URL, not {SUPABASE_URL!r}."
    if not SUPABASE_PUBLISHABLE_KEY:
        return "SUPABASE_PUBLISHABLE_KEY is not set, so access tokens cannot be verified."
    return ""

_M_PER_DEG_LAT = 111_132.0

def service_bounds() -> dict:
    """Advertised service area, derived from the downloaded network extent."""
    reach_m = SEARCH_RADIUS_METERS + SNAP_TOLERANCE_M
    delta_lat = reach_m / _M_PER_DEG_LAT
    delta_lon = reach_m / max(_M_PER_DEG_LAT * cos(radians(KNUST_CENTER_LAT)), 1.0)
    return {
        "center": {"lat": KNUST_CENTER_LAT, "lon": KNUST_CENTER_LON},
        "radius_m": reach_m,
        "min_lat": KNUST_CENTER_LAT - delta_lat,
        "max_lat": KNUST_CENTER_LAT + delta_lat,
        "min_lon": KNUST_CENTER_LON - delta_lon,
        "max_lon": KNUST_CENTER_LON + delta_lon,
    }
