"""
WorkOS AuthKit authentication module for Eternal Copilot.

Phase 1 Implementation:
- JWT token verification using JWKS (local validation, no API call per request)
- Email domain validation (only @eternal.ag allowed)
- Token caching with 45-second TTL
- JWKS caching to avoid fetching keys on every request
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from cachetools import TTLCache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import (
    EMPLOYEE_EMAIL_DOMAIN,
    TOKEN_CACHE_TTL,
    WORKOS_API_KEY,
    WORKOS_CLIENT_ID,
)

logger = logging.getLogger(__name__)

# Security scheme for Bearer token auth
security = HTTPBearer(auto_error=False)

# Token cache with 45-second TTL (thread-safe)
_token_cache: TTLCache = TTLCache(maxsize=1000, ttl=TOKEN_CACHE_TTL)
_token_cache_lock = asyncio.Lock()

# JWKS cache (refresh every 1 hour)
_jwks_cache: dict = {}
_jwks_cache_lock = asyncio.Lock()
JWKS_CACHE_TTL = 3600  # 1 hour

# WorkOS client singleton
_workos_client = None


def get_workos_client():
    """Get or create WorkOS client singleton."""
    global _workos_client
    if _workos_client is None:
        if not WORKOS_API_KEY or not WORKOS_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="WorkOS not configured. Set WORKOS_API_KEY and WORKOS_CLIENT_ID.",
            )
        import workos
        _workos_client = workos.WorkOSClient(
            api_key=WORKOS_API_KEY,
            client_id=WORKOS_CLIENT_ID,
        )
    return _workos_client


async def get_jwks() -> dict:
    """
    Fetch and cache the JWKS (JSON Web Key Set) from WorkOS.
    Used for verifying JWT signatures locally.

    Note: Lock is held for the entire fetch-and-cache sequence to prevent
    multiple concurrent fetches when the cache expires.
    """
    import time

    async with _jwks_cache_lock:
        # Check if we have a cached JWKS that's still valid
        if _jwks_cache.get("keys") and _jwks_cache.get("expires_at", 0) > time.time():
            return _jwks_cache["keys"]

        # Fetch fresh JWKS from WorkOS (inside lock to prevent concurrent fetches)
        try:
            workos = get_workos_client()
            jwks_url = workos.user_management.get_jwks_url()

            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                jwks = response.json()

            # Cache the JWKS
            _jwks_cache["keys"] = jwks
            _jwks_cache["expires_at"] = time.time() + JWKS_CACHE_TTL
            logger.info("JWKS fetched and cached successfully")

            return jwks

        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {str(e)}")
            # If we have cached keys (even expired), use them as fallback
            if _jwks_cache.get("keys"):
                logger.warning("Using expired JWKS as fallback")
                return _jwks_cache["keys"]
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch authentication keys",
            )


@dataclass
class AuthenticatedUser:
    """Authenticated user information from WorkOS."""

    id: str  # WorkOS user ID
    email: str
    name: str
    profile_picture_url: Optional[str] = None

    def get_display_name(self) -> str:
        """Get display name for UI."""
        return self.name or self.email.split("@")[0]


def validate_email_domain(email: str) -> None:
    """
    Validate that email belongs to an allowed domain.

    Phase 1: Only @eternal.ag emails are allowed.

    Raises:
        HTTPException: 403 if email domain is not allowed.
    """
    # Skip validation if EMPLOYEE_EMAIL_DOMAIN is empty or set to "*"
    if not EMPLOYEE_EMAIL_DOMAIN or EMPLOYEE_EMAIL_DOMAIN == "*":
        logger.debug("Email domain validation disabled (EMPLOYEE_EMAIL_DOMAIN is empty or '*')")
        return

    if not email:
        logger.warning("Email address is empty - access denied")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address is required for authentication.",
        )

    email_domain = email.split("@")[-1].lower()
    allowed_domain = EMPLOYEE_EMAIL_DOMAIN.lower()

    if email_domain != allowed_domain:
        logger.warning(f"Access denied for email: {email} (domain: {email_domain}, allowed: {allowed_domain})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Only @{EMPLOYEE_EMAIL_DOMAIN} email addresses are allowed.",
        )


async def verify_workos_token(token: str) -> dict:
    """
    Verify WorkOS access token (JWT) and return user info.

    Uses local JWT validation with JWKS (no API call per request).
    Uses 45-second TTL cache to avoid re-validating the same token.
    """
    # Check cache first
    async with _token_cache_lock:
        if token in _token_cache:
            logger.debug("Token cache hit")
            return _token_cache[token]

    # Token not in cache, validate JWT locally
    try:
        # Get JWKS for signature verification
        jwks = await get_jwks()

        # Decode and verify the JWT
        # WorkOS access tokens are JWTs signed with RS256
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=WORKOS_CLIENT_ID,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
            }
        )

        # Extract user info from JWT claims
        # WorkOS access tokens may not include email - only sub (user ID)
        logger.debug(f"JWT payload claims: {list(payload.keys())}")

        user_id = payload.get("sub")

        # Validate we have required fields
        if not user_id:
            raise ValueError("Token missing user ID (sub claim)")

        # If email is not in the token, fetch user info from WorkOS API
        email = payload.get("email", "")
        first_name = payload.get("first_name", "")
        last_name = payload.get("last_name", "")
        profile_picture_url = payload.get("profile_picture_url")

        if not email:
            logger.debug(f"Email not in JWT, fetching from WorkOS API for user {user_id}")
            try:
                workos = get_workos_client()
                user = workos.user_management.get_user(user_id=user_id)
                email = user.email or ""
                first_name = user.first_name or ""
                last_name = user.last_name or ""
                profile_picture_url = user.profile_picture_url
                logger.debug(f"Fetched user info from WorkOS: {email}")
            except Exception as e:
                logger.warning(f"Failed to fetch user from WorkOS: {e}")
                # Continue without email - validation will fail if domain check is enabled

        user_info = {
            "id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "profile_picture_url": profile_picture_url,
        }

        # Cache the verified token
        async with _token_cache_lock:
            _token_cache[token] = user_info
            logger.debug(f"Token cached for user {user_info['id']}")

        return user_info

    except JWTError as e:
        logger.warning(f"JWT validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthenticatedUser:
    """
    FastAPI dependency to get the current authenticated user.

    Raises HTTP 500 if WorkOS is not configured.
    Raises HTTP 401 if no credentials are provided or token is invalid.

    Usage:
        @app.get("/api/conversations")
        async def list_conversations(user: AuthenticatedUser = Depends(get_current_user)):
            return storage.list_conversations(user_id=user.id)
    """
    # Check if WorkOS is configured - fail securely if not
    if not WORKOS_API_KEY or not WORKOS_CLIENT_ID:
        logger.critical("WorkOS credentials not configured. Authentication cannot proceed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication not configured. Please contact your administrator.",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token with WorkOS
    user_info = await verify_workos_token(credentials.credentials)

    # Validate email domain (Phase 1: only @eternal.ag)
    validate_email_domain(user_info.get("email", ""))

    # Build display name
    first_name = user_info.get("first_name", "")
    last_name = user_info.get("last_name", "")
    name = f"{first_name} {last_name}".strip() or user_info.get("email", "").split("@")[0]

    return AuthenticatedUser(
        id=user_info["id"],
        email=user_info.get("email", ""),
        name=name,
        profile_picture_url=user_info.get("profile_picture_url"),
    )

