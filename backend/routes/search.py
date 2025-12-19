"""Search API endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from ..auth import AuthenticatedUser, get_current_user
from ..search import generate_scoped_search_key, is_typesense_configured
from ..config import TYPESENSE_HOST, TYPESENSE_PORT, TYPESENSE_PROTOCOL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/key")
async def get_search_key(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get a scoped Typesense API key for the authenticated user.

    The returned key has the user_id filter embedded at the Typesense level,
    ensuring the user can only search their own data. The key expires after 1 hour.

    Returns:
        JSON with search_key, typesense_host, and typesense_port for client configuration.
    """
    if not is_typesense_configured():
        raise HTTPException(
            status_code=503,
            detail="Search is not configured. Contact your administrator."
        )

    try:
        scoped_key = generate_scoped_search_key(user.id)
        return {
            "search_key": scoped_key,
            "typesense_host": TYPESENSE_HOST,
            "typesense_port": TYPESENSE_PORT,
            "typesense_protocol": TYPESENSE_PROTOCOL,
        }
    except Exception as e:
        logger.error(f"Failed to generate search key: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate search key"
        )

