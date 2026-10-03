"""Curated campus places layered over the OpenStreetMap data."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import tempfile
import threading
from typing import Optional

from routing.graph import haversine_m

logger = logging.getLogger(__name__)

CATEGORY_NAMES = (
    "medical",
    "police",
    "fire_station",
    "security",
    "administration",
    "student_services",
)

CATEGORY_LABELS = {
    "medical": "Medical",
    "police": "Police",
    "fire_station": "Fire service",
    "security": "Campus security",
    "administration": "Administration",
    "student_services": "Student services",
}

SUBTYPES = {
    "medical": (
        {"key": "pharmacy", "label": "Pharmacy",
         "types": ("pharmacy", "chemist")},
        {"key": "hospital", "label": "Hospital or clinic",
         "types": ("hospital", "clinic", "doctors", "health_post", "dentist")},
    ),
}

def subtype_types(category: str, key: str):
    """The OSM types behind a subtype, or None when the key is not one."""
    for option in SUBTYPES.get(category, ()):
        if option["key"] == key:
            return set(option["types"])
    return None

MAX_NAME_LENGTH = 120
DUPLICATE_RADIUS_M = 30.0
OVERRIDABLE_FIELDS = ("category", "type", "name", "phone", "opening_hours", "description")

_WRITE_LOCK = threading.Lock()
_WHITESPACE = re.compile(r"\s+")
_NON_SLUG = re.compile(r"[^a-z0-9]+")

def load_file(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object at the top level")
    return payload

def normalise_name(name: str) -> str:
    return _WHITESPACE.sub(" ", str(name).strip().lower())

def slug_id(name: str, taken) -> str:
    base = _NON_SLUG.sub("-", normalise_name(name)).strip("-") or "place"
    candidate = f"curated/{base}"
    if candidate not in taken:
        return candidate
    index = 2
    while f"{candidate}-{index}" in taken:
        index += 1
    return f"{candidate}-{index}"

def merge(osm_locations: list, *curated_files: dict) -> list:
    locations = [dict(entry) for entry in osm_locations]
    by_id = {entry["id"]: entry for entry in locations if entry.get("id")}
    by_name = {}
    for entry in locations:
        by_name.setdefault(normalise_name(entry.get("name", "")), []).append(entry)

    removed = set()

    for curated in curated_files:
        if not curated:
            continue
        for override in _entries(curated, "overrides"):
            _apply_override(override, by_id, by_name)
        for excluded in _entries(curated, "exclude"):
            removed.update(id(entry) for entry in _matches(excluded.get("match"), by_id, by_name))

    if removed:
        locations = [entry for entry in locations if id(entry) not in removed]

    taken = {entry["id"] for entry in locations if entry.get("id")}
    existing = [(normalise_name(e.get("name", "")), e.get("lat"), e.get("lon"))
                for e in locations]

    for curated in curated_files:
        if not curated:
            continue
        for place in _entries(curated, "places"):
            built = _build_place(place, taken)
            if built is None:
                continue
            if _is_duplicate(built, existing):
                logger.warning("Curated place %r duplicates a nearby OSM place; skipped",
                               built["name"])
                continue
            locations.append(built)
            taken.add(built["id"])
            existing.append((normalise_name(built["name"]), built["lat"], built["lon"]))

    return locations

def validate_new_place(payload: dict, bounds: dict) -> list:
    errors = []

    name = str(payload.get("name") or "").strip()
    if not name:
        errors.append("name is required")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"name must be at most {MAX_NAME_LENGTH} characters")

    category = payload.get("category")
    if category not in CATEGORY_NAMES:
        errors.append(f"category must be one of {', '.join(CATEGORY_NAMES)}")

    lat, lon = payload.get("lat"), payload.get("lon")
    for label, value in (("lat", lat), ("lon", lon)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{label} must be a number")
        elif not math.isfinite(float(value)):
            errors.append(f"{label} must be a finite number")

    if not errors and bounds:
        if not (bounds["min_lat"] <= float(lat) <= bounds["max_lat"]
                and bounds["min_lon"] <= float(lon) <= bounds["max_lon"]):
            errors.append("coordinates fall outside the mapped service area")

    return errors

def append_place(path: str, place: dict) -> None:
    with _WRITE_LOCK:
        payload = load_file(path) if os.path.exists(path) else {}
        payload.setdefault("version", 1)
        payload.setdefault("places", [])
        payload.setdefault("overrides", [])
        payload.setdefault("exclude", [])
        payload["places"].append(place)
        _atomic_write(path, payload)

def edit_place(path: str, place_id: str, changes: dict) -> bool:
    """Apply changes to one place in the local overlay file."""
    with _WRITE_LOCK:
        payload = load_file(path) if os.path.exists(path) else {}
        entries = payload.get("places")
        if not isinstance(entries, list):
            return False
        for entry in entries:
            if entry.get("id") != place_id:
                continue
            for field in OVERRIDABLE_FIELDS + ("lat", "lon"):
                if field in changes:
                    entry[field] = changes[field]
            _atomic_write(path, payload)
            return True
    return False

def delete_place(path: str, place_id: str) -> bool:
    """Remove one place from the local overlay file."""
    with _WRITE_LOCK:
        payload = load_file(path) if os.path.exists(path) else {}
        entries = payload.get("places")
        if not isinstance(entries, list):
            return False
        remaining = [e for e in entries if e.get("id") != place_id]
        if len(remaining) == len(entries):
            return False
        payload["places"] = remaining
        _atomic_write(path, payload)
        return True

def _atomic_write(path: str, payload: dict) -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory,
                                         delete=False, suffix=".tmp")
    try:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, path)
    except BaseException:
        handle.close()
        if os.path.exists(handle.name):
            os.unlink(handle.name)
        raise

def _entries(curated: dict, key: str) -> list:
    value = curated.get(key)
    return value if isinstance(value, list) else []

def _matches(match, by_id: dict, by_name: dict) -> list:
    if not isinstance(match, dict):
        return []
    osm_id = match.get("osm_id")
    if osm_id:
        entry = by_id.get(osm_id)
        return [entry] if entry else []
    name = match.get("name")
    if name:
        return list(by_name.get(normalise_name(name), ()))
    return []

def _apply_override(override: dict, by_id: dict, by_name: dict) -> None:
    targets = _matches(override.get("match"), by_id, by_name)
    if not targets:
        logger.warning("Curated override matched nothing: %s", override.get("match"))
        return
    for target in targets:
        for field in OVERRIDABLE_FIELDS:
            if field in override:
                target[field] = override[field]

def _build_place(place: dict, taken: set) -> Optional[dict]:
    name = str(place.get("name") or "").strip()
    lat, lon = place.get("lat"), place.get("lon")
    category = place.get("category")

    if not name or category not in CATEGORY_NAMES:
        logger.warning("Curated place skipped (name/category): %r", place)
        return None
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        logger.warning("Curated place %r skipped: coordinates are not numbers", name)
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        logger.warning("Curated place %r skipped: coordinates are not finite", name)
        return None

    place_id = place.get("id") or slug_id(name, taken)
    if place_id in taken:
        place_id = slug_id(name, taken)

    return {
        "id": place_id,
        "name": name,
        "type": str(place.get("type") or category),
        "category": category,
        "lat": lat,
        "lon": lon,
        "phone": _clean(place.get("phone")),
        "opening_hours": _clean(place.get("opening_hours")),
        "description": _clean(place.get("description")),
    }

def _is_duplicate(place: dict, existing: list) -> bool:
    target = normalise_name(place["name"])
    for name, lat, lon in existing:
        if name != target or lat is None or lon is None:
            continue
        if haversine_m(place["lat"], place["lon"], lat, lon) <= DUPLICATE_RADIUS_M:
            return True
    return False

def _clean(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
