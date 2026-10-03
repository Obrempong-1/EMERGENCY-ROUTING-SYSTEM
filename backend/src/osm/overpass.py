"""Overpass API client built on the standard library."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

USER_AGENT = "KNUST-Emergency-GIS/1.0 (academic project)"
TIMEOUT_S = 180
MAX_ATTEMPTS = 3
BACKOFF_S = 5.0

class OverpassError(RuntimeError):
    """The Overpass API could not be reached or returned something unusable."""

def query(ql: str, cache_path: str | None = None) -> dict:
    """Run an Overpass QL query, returning the decoded JSON."""
    if cache_path and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            logger.info("Overpass cache hit: %s (%d elements)",
                        cache_path, len(payload.get("elements", [])))
            return payload
        except (OSError, ValueError):
            logger.warning("Overpass cache at %s unreadable; refetching",
                           cache_path, exc_info=True)

    payload = _fetch(ql)

    if cache_path:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            logger.info("Cached Overpass response to %s", cache_path)
        except OSError:
            logger.warning("Could not write Overpass cache", exc_info=True)

    return payload

def _fetch(ql: str) -> dict:
    body = urllib.parse.urlencode({"data": ql}).encode("utf-8")
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        for endpoint in ENDPOINTS:
            request = urllib.request.Request(
                endpoint,
                data=body,
                headers={"User-Agent": USER_AGENT,
                         "Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                logger.info("Overpass request to %s (attempt %d)", endpoint, attempt)
                with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                elements = payload.get("elements")
                if elements is None:
                    raise OverpassError("response contained no 'elements'")
                logger.info("Overpass returned %d elements", len(elements))
                return payload
            except (urllib.error.URLError, TimeoutError, ValueError, OverpassError) as exc:
                last_error = exc
                logger.warning("Overpass attempt failed (%s): %s", endpoint, exc)

        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_S * attempt)

    raise OverpassError(f"all Overpass endpoints failed: {last_error}")

def roads_around(lat: float, lon: float, radius_m: int) -> str:
    """QL for every highway way in range, with the nodes needed to draw them."""
    return (
        f"[out:json][timeout:{TIMEOUT_S}];\n"
        f'way["highway"](around:{radius_m},{lat},{lon});\n'
        f"(._;>;);\n"
        f"out body;"
    )

def features_around(lat: float, lon: float, radius_m: int, keys: tuple) -> str:
    """QL for named points and areas carrying any of `keys`."""
    clauses = []
    for key in keys:
        clauses.append(f'  node["{key}"]["name"](around:{radius_m},{lat},{lon});')
        clauses.append(f'  way["{key}"]["name"](around:{radius_m},{lat},{lon});')
    joined = "\n".join(clauses)
    return (
        f"[out:json][timeout:{TIMEOUT_S}];\n"
        f"(\n{joined}\n);\n"
        f"(._;>;);\n"
        f"out body;"
    )


def campus_boundary(lat: float, lon: float, radius_m: int) -> str:
    """QL for the university outline around a point, with its nodes."""
    return (
        f"[out:json][timeout:{TIMEOUT_S}];\n"
        f"(\n"
        f'  way["amenity"="university"](around:{radius_m},{lat},{lon});\n'
        f'  relation["amenity"="university"](around:{radius_m},{lat},{lon});\n'
        f");\n"
        f"(._;>;);\n"
        f"out body;"
    )
