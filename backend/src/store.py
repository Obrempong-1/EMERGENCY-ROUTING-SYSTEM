"""Storage for curated places: a local file in development, PostgreSQL in production."""

from __future__ import annotations

import logging
from typing import Protocol

import db
import places

logger = logging.getLogger(__name__)

MAX_SLUG_ATTEMPTS = 5

_PLACE_COLUMNS = ("id", "name", "category", "type", "lat", "lon",
                  "phone", "opening_hours", "description")
_WRITE_COLUMNS = _PLACE_COLUMNS + ("created_by",)

class PlaceStore(Protocol):
    def load(self) -> dict:
        """Curated places in the shape places.merge consumes."""

    def add(self, place: dict) -> dict:
        """Persist a place, returning it as stored. The id may be reassigned."""

    def update(self, place_id: str, changes: dict) -> bool:
        """Apply changes to one place. False when there is no such place."""

    def remove(self, place_id: str) -> bool:
        """Delete one place. False when there is no such place."""

class FilePlaceStore:
    """Writes to the gitignored local overlay file."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict:
        try:
            return places.load_file(self.path)
        except (OSError, ValueError):
            logger.error("Local places file %s is unusable; ignoring it", self.path,
                         exc_info=True)
            return {}

    def add(self, place: dict) -> dict:
        places.append_place(self.path, place)
        return place

    def update(self, place_id: str, changes: dict) -> bool:
        return places.edit_place(self.path, place_id, changes)

    def remove(self, place_id: str) -> bool:
        return places.delete_place(self.path, place_id)

class PgPlaceStore:
    """Writes to the curated_places table, where the primary key settles id races."""

    def load(self) -> dict:
        columns = ", ".join(_PLACE_COLUMNS)
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {columns} FROM curated_places ORDER BY created_at")
                rows = cur.fetchall()

        entries = []
        for row in rows:
            entry = dict(zip(_PLACE_COLUMNS, row))
            entry["source"] = "curated"
            entries.append(entry)
        return {"version": 1, "places": entries, "overrides": [], "exclude": []}

    def add(self, place: dict) -> dict:
        from psycopg import errors

        stored = dict(place)
        columns = ", ".join(_WRITE_COLUMNS)
        placeholders = ", ".join(["%s"] * len(_WRITE_COLUMNS))
        statement = f"INSERT INTO curated_places ({columns}) VALUES ({placeholders})"

        with db.connection() as conn:
            for attempt in range(MAX_SLUG_ATTEMPTS):
                values = [stored.get(column) for column in _WRITE_COLUMNS]
                try:
                    with conn.cursor() as cur:
                        cur.execute(statement, values)
                    conn.commit()
                    return stored
                except errors.UniqueViolation:
                    conn.rollback()
                    stored["id"] = self._next_id(conn, stored["name"])
                    logger.warning("Place id collided; retrying as %s (attempt %d)",
                                   stored["id"], attempt + 2)

        raise RuntimeError(
            f"Could not allocate a unique id for {stored['name']!r} "
            f"after {MAX_SLUG_ATTEMPTS} attempts"
        )

    def update(self, place_id: str, changes: dict) -> bool:
        fields = [c for c in _PLACE_COLUMNS if c != "id" and c in changes]
        if not fields:
            return False
        assignments = ", ".join(f"{column} = %s" for column in fields)
        values = [changes[column] for column in fields]
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE curated_places SET {assignments} WHERE id = %s",
                            (*values, place_id))
                changed = cur.rowcount
            conn.commit()
        return changed > 0

    def remove(self, place_id: str) -> bool:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM curated_places WHERE id = %s", (place_id,))
                removed = cur.rowcount
            conn.commit()
        return removed > 0

    @staticmethod
    def _next_id(conn, name: str) -> str:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM curated_places")
            taken = {row[0] for row in cur.fetchall()}
        return places.slug_id(name, taken)

def make_place_store(file_path: str) -> PlaceStore:
    """PgPlaceStore when DATABASE_URL is set, otherwise the file-backed store."""
    if db.configured():
        logger.info("Curated places are stored in PostgreSQL")
        return PgPlaceStore()
    logger.info("Curated places are stored in %s", file_path)
    return FilePlaceStore(file_path)
