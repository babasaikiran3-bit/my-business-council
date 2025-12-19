"""FastAPI backend for Eternal Copilot."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging for the backend module to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from .config import (
    WORKOS_API_KEY,
    WORKOS_CLIENT_ID,
    ALLOWED_ORIGINS,
    TYPESENSE_HOST,
    TYPESENSE_API_KEY,
    TYPESENSE_SEARCH_ONLY_KEY,
)
from .routes import (
    health_router,
    search_router,
    conversations_router,
    messages_router,
    responses_router,
)

logger = logging.getLogger(__name__)


def _check_required_configuration():
    """
    Check that all required services are configured on startup.
    Raises an exception if critical configuration is missing.
    """
    missing_vars = []

    # Check WorkOS configuration (required for authentication)
    if not WORKOS_API_KEY:
        missing_vars.append("WORKOS_API_KEY")
    if not WORKOS_CLIENT_ID:
        missing_vars.append("WORKOS_CLIENT_ID")

    # Check Typesense configuration (required for search)
    if not TYPESENSE_HOST:
        missing_vars.append("TYPESENSE_HOST")
    if not TYPESENSE_API_KEY:
        missing_vars.append("TYPESENSE_API_KEY")
    if not TYPESENSE_SEARCH_ONLY_KEY:
        missing_vars.append("TYPESENSE_SEARCH_ONLY_KEY")

    if missing_vars:
        error_message = (
            "\n"
            "=" * 60 + "\n"
            "❌ CONFIGURATION ERROR: Required environment variables missing\n"
            "=" * 60 + "\n"
            f"\nMissing variables:\n"
        )
        for var in missing_vars:
            error_message += f"  • {var}\n"

        error_message += (
            "\n"
            "How to fix:\n"
            "  1. Copy the appropriate .env file for your environment:\n"
            "     - Development: .env.development\n"
            "     - Staging: .env.staging\n"
            "     - Production: .env.production\n"
            "\n"
            "  2. Ensure all required variables are set:\n"
            "\n"
            "     WorkOS Authentication:\n"
            "       WORKOS_API_KEY=sk_test_...\n"
            "       WORKOS_CLIENT_ID=client_...\n"
            "\n"
            "     Typesense Cloud (https://cloud.typesense.org/):\n"
            "       TYPESENSE_HOST=xxx.a1.typesense.net\n"
            "       TYPESENSE_API_KEY=your-admin-api-key\n"
            "       TYPESENSE_SEARCH_ONLY_KEY=your-search-only-key\n"
            "\n"
            "  3. Restart the application after updating environment variables.\n"
            "\n"
            "=" * 60 + "\n"
        )

        logger.critical(error_message)
        raise RuntimeError(error_message)


# Validate required configuration on startup
_check_required_configuration()

app = FastAPI(title="Eternal Copilot API")

# Enable CORS - uses ALLOWED_ORIGINS from config (defaults to localhost for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(health_router)
app.include_router(search_router)
app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(responses_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
