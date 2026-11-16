"""Anonymous identity (no login): HttpOnly cookie + X-Session-Token fallback + hashed IP for quota.

Design (documented in docs/ADR/0001-anonymous-identity.md):
- A random 256-bit token in an HttpOnly cookie (or X-Session-Token header when
  cross-origin quick tunnels / mobile ITP block third-party cookies) owns jobs.
  Losing the cookie/token means losing access to those jobs; there is no account
  to recover.
- Daily quota is keyed by a salted hash of the client IP (PRD US-07), so
  clearing cookies does not reset the daily allowance.
- The raw IP is never stored. Logs only contain the short hash.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass

from fastapi import Request, Response

from api import dal
from api.config import Settings
from api.timeutil import iso, utcnow

SESSION_HEADER = "X-Session-Token"


@dataclass(frozen=True)
class Identity:
    user_id: str
    ip_hash: str
    is_new: bool


def hash_ip(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf.strip()
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "0.0.0.0"


def resolve_identity(request: Request, response: Response, conn,
                     settings: Settings) -> Identity:
    """Return the caller's identity, creating an anonymous session if needed."""
    now = utcnow()
    ip_hash = hash_ip(client_ip(request, settings), settings.ip_hash_salt)
    raw = (
        request.cookies.get(settings.cookie_name)
        or request.headers.get("x-session-token", "").strip()
    )

    if raw:
        token_hash = hash_token(raw)
        session = dal.anon_session_get(conn, token_hash)
        if session is not None:
            dal.anon_session_touch(conn, token_hash, iso(now), ip_hash)
            response.headers[SESSION_HEADER] = raw
            return Identity(session["user_id"], ip_hash, is_new=False)

    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    user_id = str(uuid.uuid4())
    dal.create_user(
        conn,
        user_id=user_id,
        email=f"{user_id}@tanpa-login.invalid",
        dibuat_pada=iso(now),
    )
    dal.anon_session_create(
        conn,
        token_hash=token_hash,
        user_id=user_id,
        ip_hash=ip_hash,
        dibuat_pada=iso(now),
    )
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.cookie_max_age_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers[SESSION_HEADER] = token
    return Identity(user_id, ip_hash, is_new=True)
