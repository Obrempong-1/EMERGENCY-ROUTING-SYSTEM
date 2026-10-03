"""Verification of Supabase access tokens against the project's auth service."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import urllib.error
import urllib.request

import config

logger = logging.getLogger(__name__)

MAX_TOKEN_LENGTH = 4096

_cache = {}
_cache_lock = threading.Lock()

class VerificationUnavailable(RuntimeError):
    """Raised when Supabase could not be reached to check a token."""

def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _cached(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, user = entry
        if expires_at < time.monotonic():
            _cache.pop(key, None)
            return None
        return user

def _remember(key: str, user: dict) -> None:
    with _cache_lock:
        if len(_cache) > 512:
            _cache.clear()
        _cache[key] = (time.monotonic() + config.TOKEN_CACHE_TTL_S, user)

def forget(token: str) -> None:
    with _cache_lock:
        _cache.pop(_fingerprint(token), None)

def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()

def _fetch_user(token: str) -> dict:
    request = urllib.request.Request(
        f"{config.SUPABASE_URL}/auth/v1/user",
        headers={
            "apikey": config.SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=config.SUPABASE_TIMEOUT_S) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {}
        raise VerificationUnavailable(f"Supabase returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VerificationUnavailable(f"Could not reach Supabase: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationUnavailable("Supabase returned a malformed response") from exc

def verify(token: str):
    """The Supabase user behind this access token, or None when it is not valid.

    Tokens are checked against Supabase rather than decoded locally, so a signing
    key never has to live here and a revoked session stops working within the
    cache window.
    """
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    if not config.SUPABASE_URL or not config.SUPABASE_PUBLISHABLE_KEY:
        return None

    key = _fingerprint(token)
    hit = _cached(key)
    if hit is not None:
        return hit or None

    payload = _fetch_user(token)
    user_id = payload.get("id")
    email = payload.get("email")

    if not user_id or not email:
        _remember(key, {})
        return None

    user = {
        "auth_user_id": user_id,
        "email": email,
        "email_confirmed": bool(payload.get("email_confirmed_at")
                                or payload.get("confirmed_at")),
    }
    _remember(key, user)
    return user
