"""
security.py — Enterprise security utilities for the DB Tool.

Provides:
  - CredentialStore : Server-side session credential storage
                      (keeps raw DB passwords OUT of the session cookie).
                      Interface is Redis-ready; swap _store for a Redis client later.
  - error_response  : Standardised JSON error envelope.
  - ExportRateLimiter : Per-user rate limiter for expensive operations.
  - sanitize_identifier : Guard against SQL-injection in DB/table names.
"""

import threading
import re
import logging
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server-Side Credential Store
# ---------------------------------------------------------------------------
# Currently in-memory (thread-safe dict).
# To migrate to Redis later, replace _store operations with:
#   redis_client.setex(key, TTL_SECONDS, json.dumps(creds))
#   json.loads(redis_client.get(key))
# ---------------------------------------------------------------------------

_CRED_TTL_SECONDS = 24 * 3600   # Credentials expire with the session (24h)

class CredentialStore:
    """
    Stores DB credentials server-side, keyed by a session-scoped token.
    The session cookie only holds the token, never the password.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._store: dict = {}   # {token: {creds..., expires_at: datetime}}

    def put(self, token: str, creds: dict) -> None:
        """Save credentials, overwriting any previous entry for this token."""
        with self._lock:
            self._store[token] = {
                **creds,
                'expires_at': datetime.now() + timedelta(seconds=_CRED_TTL_SECONDS)
            }

    def get(self, token: str) -> dict | None:
        """Return credentials if the token exists and has not expired."""
        with self._lock:
            entry = self._store.get(token)
            if entry is None:
                return None
            if datetime.now() > entry['expires_at']:
                del self._store[token]
                return None
            return {k: v for k, v in entry.items() if k != 'expires_at'}

    def delete(self, token: str) -> None:
        """Remove credentials on logout."""
        with self._lock:
            self._store.pop(token, None)

    def purge_expired(self) -> int:
        """Remove all expired entries. Call periodically from cleanup task."""
        with self._lock:
            now = datetime.now()
            expired = [k for k, v in self._store.items() if now > v['expires_at']]
            for k in expired:
                del self._store[k]
            return len(expired)


CREDENTIAL_STORE = CredentialStore()


# ---------------------------------------------------------------------------
# Standardised Error Response
# ---------------------------------------------------------------------------

def error_response(status_code: int, message: str, detail: str = None) -> JSONResponse:
    """
    Return a uniform JSON error envelope:
      { "error": true, "message": "...", "detail": "..." }
    """
    body = {"error": True, "message": message}
    if detail:
        body["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


def ok_response(data: dict) -> dict:
    """Wrap a successful payload in a uniform envelope."""
    return {"error": False, **data}


# ---------------------------------------------------------------------------
# Export / Download Rate Limiter
# ---------------------------------------------------------------------------

class PerUserRateLimiter:
    """
    Sliding-window rate limiter keyed by username (not IP).
    Thread-safe via RLock.

    Default: max 10 export requests per 60 seconds per user.
    """

    def __init__(self, max_calls: int = 10, window_seconds: int = 60):
        self._lock = threading.RLock()
        self._calls: dict = {}   # {username: [timestamp, ...]}
        self.max_calls = max_calls
        self.window_seconds = window_seconds

    def is_allowed(self, username: str) -> bool:
        with self._lock:
            now = datetime.now().timestamp()
            if username not in self._calls:
                self._calls[username] = []

            # Evict old timestamps
            self._calls[username] = [
                t for t in self._calls[username]
                if now - t < self.window_seconds
            ]

            if len(self._calls[username]) >= self.max_calls:
                return False

            self._calls[username].append(now)
            return True

    def reset(self, username: str) -> None:
        with self._lock:
            self._calls.pop(username, None)


# One shared instance for export/download operations
export_limiter = PerUserRateLimiter(max_calls=10, window_seconds=60)


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------

# Valid MySQL identifier: letters, digits, underscores, hyphens, up to 64 chars.
_SAFE_IDENTIFIER_RE = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')


def sanitize_identifier(value: str, field_name: str = "identifier") -> str | None:
    """
    Validate a MySQL database or table name.
    Returns the value unchanged if safe, or None if it contains dangerous characters.

    Usage:
        db = sanitize_identifier(body.get('database'), 'database')
        if db is None:
            return error_response(400, "Invalid database name")
    """
    if not value or not isinstance(value, str):
        return None
    if _SAFE_IDENTIFIER_RE.match(value):
        return value
    logger.warning(f"Rejected potentially unsafe {field_name}: {repr(value)}")
    return None


def sanitize_host(value: str) -> str | None:
    """
    Validate a hostname or IP address.
    Allows: alphanumeric, dots, hyphens, underscores (hostnames + IPs).
    Max length 253 chars (DNS limit).
    """
    if not value or not isinstance(value, str):
        return None
    if len(value) > 253:
        return None
    if re.match(r'^[A-Za-z0-9.\-_]{1,253}$', value):
        return value
    logger.warning(f"Rejected potentially unsafe host: {repr(value)}")
    return None
