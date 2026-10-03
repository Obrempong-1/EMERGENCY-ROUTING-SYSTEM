"""OpenStreetMap acquisition: road network and named facilities."""

from __future__ import annotations

import logging
import os

import config
import osm
import places
import store

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
ROADS_CACHE = os.path.join(CACHE_DIR, "roads.json")
FACILITIES_CACHE = os.path.join(CACHE_DIR, "facilities.json")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CURATED_PLACES_PATH = os.path.join(DATA_DIR, "campus_places.json")
LOCAL_PLACES_PATH = os.path.join(DATA_DIR, "campus_places.local.json")

CATEGORY_NAMES = places.CATEGORY_NAMES

_PLACE_STORE = None

EMERGENCY_CATEGORIES = {
    "chemist": "medical",
    "hospital": "medical",
    "clinic": "medical",
    "doctors": "medical",
    "dentist": "medical",
    "pharmacy": "medical",
    "health_post": "medical",
    "police": "police",
    "fire_station": "fire_station",
}

FACILITY_KEYS = ("amenity", "shop", "office", "leisure", "tourism", "building")
_TYPE_KEYS = ("amenity", "shop", "office", "leisure", "tourism")
_FACILITY_RADIUS_M = config.SEARCH_RADIUS_METERS + 500

def load_segments() -> list:
    """Road segments around campus, from the Overpass cache when available."""
    payload = osm.query(
        osm.roads_around(config.KNUST_CENTER_LAT, config.KNUST_CENTER_LON,
                         config.SEARCH_RADIUS_METERS),
        cache_path=ROADS_CACHE,
    )
    elements = payload["elements"]
    return osm.road_segments(elements, osm.index_nodes(elements))

def load_osm_locations() -> list:
    """Named OSM facilities as JSON-serialisable dicts with stable ids."""
    try:
        payload = osm.query(
            osm.features_around(config.KNUST_CENTER_LAT, config.KNUST_CENTER_LON,
                                _FACILITY_RADIUS_M, FACILITY_KEYS),
            cache_path=FACILITIES_CACHE,
        )
    except osm.OverpassError:
        logger.error("Could not fetch facilities from Overpass", exc_info=True)
        return []

    elements = payload["elements"]
    placed = osm.facilities(elements, osm.index_nodes(elements), FACILITY_KEYS)

    locations = []
    for facility in placed:
        facility_type = osm.tag_value(facility.tags, _TYPE_KEYS, "building")
        locations.append({
            "id": facility.osm_id,
            "name": facility.name,
            "type": facility_type,
            "category": EMERGENCY_CATEGORIES.get(facility_type, "facility"),
            "lat": facility.lat,
            "lon": facility.lon,
            "phone": osm.clean_tag(facility.tags, "phone")
                     or osm.clean_tag(facility.tags, "contact:phone"),
            "opening_hours": osm.clean_tag(facility.tags, "opening_hours"),
            "description": osm.clean_tag(facility.tags, "description"),
        })

    emergency = sum(1 for loc in locations if loc["category"] != "facility")
    logger.info("Loaded %d facilities (%d emergency-classified)",
                len(locations), emergency)
    return locations

def load_curated() -> tuple:
    """The committed curated file, then the writable overlay from the place store."""
    try:
        committed = places.load_file(CURATED_PLACES_PATH)
    except (OSError, ValueError):
        logger.error("Curated places file %s is unusable; ignoring it", CURATED_PLACES_PATH,
                     exc_info=True)
        committed = {}

    try:
        overlay = place_store().load()
    except Exception:
        logger.error("Could not read curated places from the store; ignoring them",
                     exc_info=True)
        overlay = {}

    return committed, overlay

def place_store():
    """The process-wide place store, created on first use."""
    global _PLACE_STORE
    if _PLACE_STORE is None:
        _PLACE_STORE = store.make_place_store(LOCAL_PLACES_PATH)
    return _PLACE_STORE

def get_locations(osm_locations=None) -> list:
    """OSM facilities with the curated campus layer applied."""
    if osm_locations is None:
        osm_locations = load_osm_locations()
    merged = places.merge(osm_locations, *load_curated())
    emergency = sum(1 for entry in merged if entry["category"] != "facility")
    logger.info("Locations ready: %d total, %d emergency-classified",
                len(merged), emergency)
    return merged
