"""OAuth provider flow for Kakao (primary) and Naver (config-ready).

Custom OAuth in FastAPI — endpoints verified against current Kakao/Naver docs:
  Kakao:  authorize kauth.kakao.com/oauth/authorize · token kauth.kakao.com/oauth/token
          · userinfo kapi.kakao.com/v2/user/me (supports PKCE)
  Naver:  authorize nid.naver.com/oauth2.0/authorize · token nid.naver.com/oauth2.0/token
          · userinfo openapi.naver.com/v1/nid/me (state only, no PKCE)

Each provider is env-gated: with no client id/redirect configured it reports as
disabled and login 404s, so the app runs fine before credentials exist.
"""

import base64
import hashlib
import logging
import os
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("parenting_roundtable.oauth")


def _parse_kakao(data: Dict[str, Any]) -> Dict[str, Optional[str]]:
    account = data.get("kakao_account") or {}
    profile = account.get("profile") or {}
    props = data.get("properties") or {}
    return {
        "provider_user_id": str(data.get("id")),
        "display_name": profile.get("nickname") or props.get("nickname"),
    }


def _parse_naver(data: Dict[str, Any]) -> Dict[str, Optional[str]]:
    r = data.get("response") or {}
    return {
        "provider_user_id": str(r.get("id")),
        "display_name": r.get("nickname") or r.get("name"),
    }


PROVIDERS: Dict[str, Dict[str, Any]] = {
    "kakao": {
        "authorize_url": "https://kauth.kakao.com/oauth/authorize",
        "token_url": "https://kauth.kakao.com/oauth/token",
        "userinfo_url": "https://kapi.kakao.com/v2/user/me",
        "client_id_env": "KAKAO_REST_API_KEY",
        "client_secret_env": "KAKAO_CLIENT_SECRET",
        "redirect_uri_env": "KAKAO_REDIRECT_URI",
        "pkce": True,
        "token_send": "data",       # form-encoded body
        "parse": _parse_kakao,
    },
    "naver": {
        "authorize_url": "https://nid.naver.com/oauth2.0/authorize",
        "token_url": "https://nid.naver.com/oauth2.0/token",
        "userinfo_url": "https://openapi.naver.com/v1/nid/me",
        "client_id_env": "NAVER_CLIENT_ID",
        "client_secret_env": "NAVER_CLIENT_SECRET",
        "redirect_uri_env": "NAVER_REDIRECT_URI",
        "pkce": False,
        "token_send": "params",     # query string
        "parse": _parse_naver,
    },
}


def provider_config(provider: str) -> Optional[Dict[str, Any]]:
    return PROVIDERS.get(provider)


def _client_id(cfg: Dict[str, Any]) -> Optional[str]:
    return os.getenv(cfg["client_id_env"])


def _redirect_uri(cfg: Dict[str, Any]) -> Optional[str]:
    return os.getenv(cfg["redirect_uri_env"])


def provider_enabled(provider: str) -> bool:
    cfg = provider_config(provider)
    return bool(cfg and _client_id(cfg) and _redirect_uri(cfg))


def make_pkce() -> Dict[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return {"verifier": verifier, "challenge": challenge}


def build_authorize_url(provider: str, state: str, code_challenge: Optional[str] = None) -> str:
    cfg = provider_config(provider)
    params = {
        "response_type": "code",
        "client_id": _client_id(cfg),
        "redirect_uri": _redirect_uri(cfg),
        "state": state,
    }
    if cfg["pkce"] and code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return f"{cfg['authorize_url']}?{urlencode(params)}"


async def exchange_code(
    provider: str, code: str, state: str, code_verifier: Optional[str] = None
) -> Optional[str]:
    """Exchange an authorization code for an access token. Returns the token or None."""
    cfg = provider_config(provider)
    payload = {
        "grant_type": "authorization_code",
        "client_id": _client_id(cfg),
        "redirect_uri": _redirect_uri(cfg),
        "code": code,
    }
    secret = os.getenv(cfg["client_secret_env"])
    if secret:
        payload["client_secret"] = secret
    if cfg["pkce"] and code_verifier:
        payload["code_verifier"] = code_verifier
    if provider == "naver":
        payload["state"] = state

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            kwargs = {cfg["token_send"]: payload}
            resp = await client.post(cfg["token_url"], **kwargs)
            resp.raise_for_status()
            return resp.json().get("access_token")
    except Exception as e:  # noqa: BLE001 - graceful degradation on any failure
        logger.warning("OAuth token exchange failed", extra={"provider": provider, "error": str(e)})
        return None


async def fetch_userinfo(provider: str, access_token: str) -> Optional[Dict[str, Optional[str]]]:
    """Fetch + normalise the provider's user info to {provider_user_id, display_name}."""
    cfg = provider_config(provider)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            parsed = cfg["parse"](resp.json())
    except Exception as e:  # noqa: BLE001
        logger.warning("OAuth userinfo fetch failed", extra={"provider": provider, "error": str(e)})
        return None
    if not parsed.get("provider_user_id") or parsed["provider_user_id"] == "None":
        return None
    return parsed
