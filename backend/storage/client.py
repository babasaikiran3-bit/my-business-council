"""Supabase client singleton.

This module provides a centralized Supabase client instance for the storage layer.
"""

import logging
from typing import Optional

from supabase import create_client, Client

from ..config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

# Supabase client singleton
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get or create Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client

