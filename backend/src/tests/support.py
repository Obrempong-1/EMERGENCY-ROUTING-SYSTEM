"""Shared fixture for tests that need a real PostgreSQL schema."""

from __future__ import annotations

import os
import unittest
from urllib.parse import quote, urlsplit

import config
import db

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()
ALLOW_REMOTE = os.getenv("TEST_DATABASE_ALLOW_REMOTE") == "1"

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "")

def is_local(url: str) -> bool:
    return (urlsplit(url).hostname or "") in LOCAL_HOSTS

class SchemaFixture(unittest.TestCase):
    """Creates a throwaway schema, applies schema.sql, and drops it afterwards.

    These tests CREATE and DROP schemas, so pointing them at a shared or hosted
    database would litter or damage it. A remote host is refused unless
    TEST_DATABASE_ALLOW_REMOTE=1 says so deliberately.
    """

    schema = ""
    extra_config: dict = {}

    @classmethod
    def setUpClass(cls):
        if not TEST_DATABASE_URL:
            raise unittest.SkipTest("TEST_DATABASE_URL is not set")
        if not cls.schema:
            raise AssertionError(f"{cls.__name__} must set a schema name")
        if not is_local(TEST_DATABASE_URL) and not ALLOW_REMOTE:
            raise unittest.SkipTest(
                f"TEST_DATABASE_URL points at {urlsplit(TEST_DATABASE_URL).hostname}, "
                "which is not local. These tests create and drop schemas. "
                "Set TEST_DATABASE_ALLOW_REMOTE=1 only if that is what you want."
            )

        cls._saved = {name: getattr(config, name)
                      for name in ("DATABASE_URL", *cls.extra_config)}

        separator = "&" if "?" in TEST_DATABASE_URL else "?"
        option = quote(f"-c search_path={cls.schema}")
        config.DATABASE_URL = f"{TEST_DATABASE_URL}{separator}options={option}"
        for name, value in cls.extra_config.items():
            setattr(config, name, value)

        db.close()
        cls._reset_schema()
        db.apply_schema()

    @classmethod
    def tearDownClass(cls):
        try:
            with db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"DROP SCHEMA IF EXISTS {cls.schema} CASCADE")
                conn.commit()
        finally:
            db.close()
            for name, value in cls._saved.items():
                setattr(config, name, value)
            db.close()

    @classmethod
    def _reset_schema(cls):
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {cls.schema} CASCADE")
                cur.execute(f"CREATE SCHEMA {cls.schema}")
            conn.commit()

    def truncate(self, *tables):
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE {', '.join(tables)} CASCADE")
            conn.commit()
