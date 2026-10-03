"""Student-reported hazards, corroborated into a confidence score that expires on its own."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

import config
import db
from routing.graph import haversine_m

logger = logging.getLogger(__name__)

KIND_TTL_HOURS = {
    "suspicious_activity": 2,
    "accident": 3,
    "flooding": 6,
    "blocked_road": 12,
}

KIND_LABELS = {
    "suspicious_activity": "Suspicious activity",
    "accident": "Accident",
    "flooding": "Flooding",
    "blocked_road": "Blocked road",
}

KINDS = tuple(KIND_TTL_HOURS)

CLUSTER_RADIUS_M = 120.0
CLUSTER_WINDOW_MIN = 90
TTL_CAP_HOURS = 24

DECAY_HALF_LIFE_MIN = 60.0
EVIDENCE_SCALE = 0.48
MAX_CONFIDENCE = 0.999

LIKELY_AT = 0.35
CONFIRMED_AT = 0.75

FALSE_REPORT_TRUST_FACTOR = 0.5
MAX_NOTE_LENGTH = 280

_M_PER_DEG_LAT = 111_132.0

class IncidentError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail

def minutes_until(moment) -> int:
    """Whole minutes left, computed server-side so device clock skew cannot distort it."""
    remaining = (moment - datetime.now(timezone.utc)).total_seconds() / 60.0
    return max(0, int(remaining))

def _require_db() -> None:
    if not db.configured():
        raise IncidentError(503, "Incident reporting requires a database.")

def confidence_from_evidence(evidence: float) -> float:
    """Diminishing returns: more independent weight raises confidence but never reaches 1."""
    raw = 1.0 - math.exp(-EVIDENCE_SCALE * max(evidence, 0.0))
    return min(raw, MAX_CONFIDENCE)

def status_for(confidence: float, override=None) -> str:
    if override:
        return override
    if confidence >= CONFIRMED_AT:
        return "confirmed"
    if confidence >= LIKELY_AT:
        return "likely"
    return "unverified"

_COLUMNS = """
SELECT c.id, c.kind, c.lat, c.lon, c.override, c.created_at, c.expires_at,
       count(r.id),
       coalesce(sum(s.trust * exp(-(extract(epoch from (now() - r.created_at)) / 60.0)
                                  / %(half_life)s)), 0)
FROM incident_clusters c
LEFT JOIN incident_reports r ON r.cluster_id = c.id
LEFT JOIN students s ON s.id = r.student_id
"""

_LIVE_SELECT = _COLUMNS + """
WHERE c.resolved_at IS NULL
  AND c.expires_at > now()
  AND coalesce(c.override, '') <> 'false'
GROUP BY c.id
HAVING count(r.id) > 0
ORDER BY c.created_at DESC
"""

_ALL_SELECT = _COLUMNS.replace(
    "\nFROM incident_clusters c", ",\n       c.resolved_at\nFROM incident_clusters c"
) + """
GROUP BY c.id
ORDER BY c.created_at DESC
"""

_ONE_SELECT = _COLUMNS + """
WHERE c.id = %(cluster_id)s
GROUP BY c.id
"""

def _build(row) -> dict:
    """The single place an incident payload is shaped, for both reads and writes."""
    (cluster_id, kind, lat, lon, override, created_at, expires_at,
     report_count, evidence) = row
    confidence = confidence_from_evidence(float(evidence))
    return {
        "id": cluster_id,
        "kind": kind,
        "label": KIND_LABELS.get(kind, kind),
        "lat": lat,
        "lon": lon,
        "confidence": round(confidence, 3),
        "status": status_for(confidence, override),
        "reports": int(report_count),
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "expires_in_minutes": minutes_until(expires_at),
    }

def live() -> list:
    """Every unresolved, unexpired cluster. Expiry is applied here, not by a worker."""
    if not db.configured():
        return []
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_LIVE_SELECT, {"half_life": DECAY_HALF_LIFE_MIN})
            rows = cur.fetchall()
        conn.commit()
    return [_build(row) for row in rows]

def all_clusters() -> list:
    """Every cluster ever opened, newest first, whatever its state."""
    if not db.configured():
        return []
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_ALL_SELECT, {"half_life": DECAY_HALF_LIFE_MIN})
            rows = cur.fetchall()
        conn.commit()
    return [{**_build(row[:9]), "live": _is_live(row)} for row in rows]

def _is_live(row) -> bool:
    """The same conditions the live listing filters on, read off a row."""
    override = row[4] or ""
    expires_at, report_count, resolved_at = row[6], int(row[7]), row[9]
    return (resolved_at is None
            and report_count > 0
            and override != "false"
            and minutes_until(expires_at) > 0)

def _check_rate_limit(cur, student_id: int) -> None:
    cur.execute(
        "SELECT count(*) FROM incident_reports"
        " WHERE student_id = %s AND created_at > now() - interval '1 hour'",
        (student_id,))
    if cur.fetchone()[0] >= config.INCIDENT_REPORTS_PER_HOUR:
        raise IncidentError(429, "You have reported too many incidents in the last hour.")

def _find_cluster(cur, kind: str, lat: float, lon: float):
    """The nearest live cluster of this kind within the radius and time window."""
    lat_span = CLUSTER_RADIUS_M / _M_PER_DEG_LAT
    lon_span = CLUSTER_RADIUS_M / max(_M_PER_DEG_LAT * math.cos(math.radians(lat)), 1.0)
    cur.execute(
        "SELECT id, lat, lon FROM incident_clusters"
        " WHERE kind = %s AND resolved_at IS NULL AND expires_at > now()"
        "   AND coalesce(override, '') <> 'false'"
        "   AND created_at > now() - make_interval(mins => %s)"
        "   AND lat BETWEEN %s AND %s AND lon BETWEEN %s AND %s",
        (kind, CLUSTER_WINDOW_MIN, lat - lat_span, lat + lat_span,
         lon - lon_span, lon + lon_span))

    nearest, best = None, CLUSTER_RADIUS_M
    for cluster_id, cluster_lat, cluster_lon in cur.fetchall():
        distance = haversine_m(lat, lon, cluster_lat, cluster_lon)
        if distance <= best:
            nearest, best = cluster_id, distance
    return nearest

def _snapshot(cur, cluster_id: int) -> dict:
    """One cluster as it stands now. Confidence is always derived, never stored."""
    cur.execute(_ONE_SELECT, {"half_life": DECAY_HALF_LIFE_MIN, "cluster_id": cluster_id})
    row = cur.fetchone()
    if row is None:
        raise IncidentError(404, "No such incident.")
    return _build(row)

def _extend(cur, cluster_id: int, kind: str) -> None:
    """Corroboration keeps a cluster alive, but never past the hard cap from creation."""
    cur.execute(
        "UPDATE incident_clusters"
        " SET expires_at = least(now() + make_interval(hours => %s),"
        "                        created_at + make_interval(hours => %s))"
        " WHERE id = %s AND expires_at < now() + make_interval(hours => %s)",
        (KIND_TTL_HOURS[kind], TTL_CAP_HOURS, cluster_id, KIND_TTL_HOURS[kind]))

def report(student: dict, kind: str, lat: float, lon: float, note=None) -> dict:
    """Attach a report to a nearby live cluster of the same kind, or open a new one."""
    _require_db()

    if kind not in KIND_TTL_HOURS:
        raise IncidentError(422, f"kind must be one of {', '.join(KINDS)}")
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise IncidentError(422, "Coordinates must be finite numbers.")

    bounds = config.service_bounds()
    if not (bounds["min_lat"] <= lat <= bounds["max_lat"]
            and bounds["min_lon"] <= lon <= bounds["max_lon"]):
        raise IncidentError(422, "That point is outside the mapped service area.")

    text = (note or "").strip()[:MAX_NOTE_LENGTH] or None

    with db.connection() as conn:
        with conn.cursor() as cur:
            _check_rate_limit(cur, student["id"])

            cluster_id = _find_cluster(cur, kind, lat, lon)
            corroborated = cluster_id is not None

            if not corroborated:
                cur.execute(
                    "INSERT INTO incident_clusters (kind, lat, lon, expires_at)"
                    " VALUES (%s, %s, %s, now() + make_interval(hours => %s)) RETURNING id",
                    (kind, lat, lon, KIND_TTL_HOURS[kind]))
                cluster_id = cur.fetchone()[0]

            cur.execute(
                "INSERT INTO incident_reports (cluster_id, student_id, lat, lon, note)"
                " VALUES (%s, %s, %s, %s, %s)"
                " ON CONFLICT (cluster_id, student_id) DO NOTHING RETURNING id",
                (cluster_id, student["id"], lat, lon, text))
            inserted = cur.fetchone() is not None

            if corroborated and inserted:
                _extend(cur, cluster_id, kind)

            snapshot = _snapshot(cur, cluster_id)
        conn.commit()

    if not inserted:
        logger.info("Student %s already reported cluster %s; confidence unchanged",
                    student["id"], cluster_id)

    return {**snapshot, "counted": inserted, "corroborated": corroborated}

def set_override(cluster_id: int, override: str) -> dict:
    """Security's verdict. Marking a cluster false permanently weakens its reporters.

    Idempotent: repeating a verdict changes nothing, so a replayed request cannot
    decay trust twice. The row is locked, so two concurrent verdicts cannot either.
    """
    _require_db()
    if override not in ("verified", "false"):
        raise IncidentError(422, "override must be 'verified' or 'false'")

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT override FROM incident_clusters WHERE id = %s FOR UPDATE",
                        (cluster_id,))
            row = cur.fetchone()
            if row is None:
                raise IncidentError(404, "No such incident.")

            decayed = 0
            if row[0] != override:
                cur.execute(
                    "UPDATE incident_clusters SET override = %s,"
                    " resolved_at = CASE WHEN %s = 'false' THEN now() ELSE resolved_at END"
                    " WHERE id = %s", (override, override, cluster_id))
                if override == "false":
                    cur.execute(
                        "UPDATE students SET trust = greatest(trust * %s, 0.01)"
                        " WHERE id IN (SELECT student_id FROM incident_reports"
                        "              WHERE cluster_id = %s)",
                        (FALSE_REPORT_TRUST_FACTOR, cluster_id))
                    decayed = cur.rowcount

            snapshot = _snapshot(cur, cluster_id)
        conn.commit()

    logger.info("Incident %s marked %s (%d reporter trust scores decayed)",
                cluster_id, override, decayed)
    return {"id": cluster_id, "override": override, "reporters_decayed": decayed,
            "status": snapshot["status"]}

def resolve(cluster_id: int) -> None:
    _require_db()
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE incident_clusters SET resolved_at = now()"
                " WHERE id = %s AND resolved_at IS NULL RETURNING id", (cluster_id,))
            if cur.fetchone() is None:
                raise IncidentError(404, "No such live incident.")
        conn.commit()
