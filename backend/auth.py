"""Anonymous/device session identity (Phase 1a).

Per the consensus "A′" approach, every visitor gets a REAL, enforced session identity
from the first request — not a stubbed shared tenant. This makes ``user_id`` a genuine
isolation key immediately, and when the parent later signs in with Kakao (Phase 2) that
provider identity links to this same ``user_id`` (merge-in-place), so anonymous history
is preserved rather than lost.

The session is a signed cookie (stdlib HMAC — no extra dependency). It is NOT
authentication of a real person; Phase 2 layers OAuth + the full security surface
(state/PKCE, CSRF, refresh rotation) on top.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from typing import Any, Dict, Optional

from fastapi import Request, Response

from .config import IS_PRODUCTION

logger = logging.getLogger("parenting_roundtable.auth")

# The old insecure default. Treated as "unset" so a forgotten override fails closed.
_DEV_PLACEHOLDER_SECRET = "dev-insecure-secret-change-me"
_MIN_SECRET_LEN = 32


def _load_session_secret(raw: Optional[str], is_production: bool) -> str:
    """Resolve the HMAC signing secret, failing fast on an insecure production value.

    Pure + parameterised so it is directly unit-testable (test_auth.py).
    - Valid (set, not the placeholder, >=32 chars) -> use it.
    - Invalid in production -> SystemExit (refuse to forge-able-session our way into prod).
    - Invalid in dev -> ephemeral per-process secret + warning, so local dev / CI without
      the env var still runs (sessions just don't survive a restart, which is fine in dev).
    """
    if raw and raw != _DEV_PLACEHOLDER_SECRET and len(raw) >= _MIN_SECRET_LEN:
        return raw
    if is_production:
        raise SystemExit(
            "SESSION_SECRET must be set to a random value of at least "
            f"{_MIN_SECRET_LEN} characters in production "
            '(generate: python -c "import secrets;print(secrets.token_urlsafe(32))")'
        )
    logger.warning(
        "SESSION_SECRET is unset/insecure; using an ephemeral per-process secret "
        "(dev only — sessions will not survive a restart)."
    )
    return secrets.token_urlsafe(48)


SESSION_SECRET = _load_session_secret(os.getenv("SESSION_SECRET"), IS_PRODUCTION)
COOKIE_NAME = "pr_uid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


def cookie_security_kwargs() -> Dict[str, Any]:
    """Cookie security flags for the current environment.

    Production runs cross-site (Vercel frontend <-> PaaS backend), so the session cookie
    must be SameSite=None to be sent on credentialed fetches — which browsers only accept
    together with Secure. Dev stays SameSite=Lax without Secure for http://localhost.
    """
    if IS_PRODUCTION:
        return {"httponly": True, "secure": True, "samesite": "none"}
    return {"httponly": True, "secure": False, "samesite": "lax"}


def cookie_clear_kwargs() -> Dict[str, Any]:
    flags = cookie_security_kwargs()
    return {"secure": flags["secure"], "samesite": flags["samesite"]}


def _sign(user_id: str) -> str:
    sig = hmac.new(SESSION_SECRET.encode(), user_id.encode(), hashlib.sha256).hexdigest()
    return f"{user_id}.{sig}"


def _verify(token: Optional[str]) -> Optional[str]:
    if not token or "." not in token:
        return None
    user_id, _, sig = token.rpartition(".")
    expected = hmac.new(SESSION_SECRET.encode(), user_id.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected):
        return user_id
    return None


def set_session_cookie(response: Response, user_id: str) -> None:
    """Issue/replace the session cookie for ``user_id`` (used by anon mint + OAuth login)."""
    response.set_cookie(
        COOKIE_NAME,
        _sign(user_id),
        max_age=COOKIE_MAX_AGE,
        **cookie_security_kwargs(),
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, **cookie_clear_kwargs())


def sign_payload(payload: Dict[str, Any]) -> str:
    """Sign an arbitrary JSON payload (e.g. the short-lived OAuth state cookie)."""
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(SESSION_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_payload(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token or "." not in token:
        return None
    raw, _, sig = token.rpartition(".")
    expected = hmac.new(SESSION_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
    except (ValueError, json.JSONDecodeError):
        return None


def get_current_user(request: Request, response: Response) -> str:
    """FastAPI dependency: return the caller's user_id, minting an anonymous one if needed.

    A new anonymous identity is issued as an HttpOnly, SameSite=Lax signed cookie so the
    same browser keeps a stable, isolated ``user_id`` across requests.
    """
    user_id = _verify(request.cookies.get(COOKIE_NAME))
    if user_id is None:
        user_id = "anon" + uuid.uuid4().hex
        set_session_cookie(response, user_id)
    return user_id
