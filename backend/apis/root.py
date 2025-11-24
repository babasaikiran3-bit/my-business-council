"""Root/health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}

