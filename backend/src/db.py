"""PostgreSQL connection pooling and the schema."""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlsplit

import config

logger = logging.getLogger(__name__)

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

_TRANSACTION_POOLER_PORT = 6543

_pool = None
_pool_lock = threading.Lock()

class DatabaseUnavailable(RuntimeError):
    """Raised when the database is configured but cannot be reached."""

def configured() -> bool:
    return bool(config.DATABASE_URL)

def _connection_kwargs(url: str) -> dict:
    kwargs = {}
    if urlsplit(url).port == _TRANSACTION_POOLER_PORT:
        kwargs["prepare_threshold"] = None
        logger.warning(
            "DATABASE_URL points at port %d (transaction pooler); disabling prepared "
            "statements, which pgbouncer in transaction mode does not support",
            _TRANSACTION_POOLER_PORT,
        )
    return kwargs

def pool():
    """The process-wide pool, created once. Safe for concurrent first callers."""
    global _pool
    if _pool is not None:
        return _pool
    if not configured():
        raise DatabaseUnavailable("DATABASE_URL is not set")

    try:
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        raise DatabaseUnavailable(
            "DATABASE_URL is set but psycopg is not installed; "
            "install it with pip install -r requirements.txt"
        ) from exc

    with _pool_lock:
        if _pool is not None:
            return _pool
        created = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=4,
            kwargs=_connection_kwargs(config.DATABASE_URL),
            open=False,
        )
        created.open(wait=True, timeout=config.DATABASE_CONNECT_TIMEOUT_S)
        _pool = created
        logger.info("Database pool ready (min 1, max 4)")
    return _pool

def close() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None

@contextmanager
def connection() -> Iterator:
    with pool().connection() as conn:
        yield conn

def apply_schema() -> None:
    """Create any missing tables and indexes. Safe to run on every start."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
        sql = handle.read()
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
