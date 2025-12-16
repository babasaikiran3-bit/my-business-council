#!/bin/bash
# ============================================
# Eternal Ops Control - Development Runner
# ============================================
# Usage:
#   ./run.sh              - Run in development mode (default)
#   ./run.sh --staging    - Run in staging mode
#   ./run.sh --production - Run in production mode
#   ./run.sh --help       - Show this help message
#
# Environment:
#   Development: Uses .env.development or .env
#   Staging:     Uses .env.staging (requires explicit flag)
#   Production:  Uses .env.production (requires explicit flag)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default environment
ENV="development"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --development|-d)
            ENV="development"
            shift
            ;;
        --staging|-s)
            ENV="staging"
            shift
            ;;
        --production|-p)
            ENV="production"
            shift
            ;;
        --help|-h)
            echo "Eternal Ops Control - Development Runner"
            echo ""
            echo "Usage: ./run.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -d, --development  Run in development mode (default)"
            echo "  -s, --staging      Run in staging mode"
            echo "  -p, --production   Run in production mode"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run.sh                # Development mode"
            echo "  ./run.sh --staging      # Staging mode"
            echo "  ./run.sh --production   # Production mode"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Safety check for production
if [ "$ENV" = "production" ]; then
    echo -e "${RED}⚠️  WARNING: You are about to run in PRODUCTION mode!${NC}"
    echo -e "${YELLOW}This will connect to the live database and services.${NC}"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 1
    fi
fi

ENV_UPPER=$(echo "$ENV" | tr '[:lower:]' '[:upper:]')
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Eternal Ops Control - ${ENV_UPPER} Mode${NC}"
echo -e "${BLUE}============================================${NC}"

# Check for required environment file
ENV_FILE=".env.${ENV}"
if [ "$ENV" = "development" ] && [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env" ]; then
        ENV_FILE=".env"
        echo -e "${YELLOW}Note: Using .env as fallback (no .env.development found)${NC}"
    fi
fi

if [ ! -f "$ENV_FILE" ] && [ "$ENV" != "development" ]; then
    echo -e "${RED}Error: $ENV_FILE not found!${NC}"
    echo -e "Please create $ENV_FILE from ${ENV_FILE}.example"
    exit 1
fi

echo -e "${GREEN}✓ Environment file: $ENV_FILE${NC}"

# Export environment variable
export ENV="$ENV"

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d ".venv" ]; then
        echo -e "${YELLOW}Activating virtual environment...${NC}"
        source .venv/bin/activate
    else
        echo -e "${YELLOW}Warning: No virtual environment found. Using system Python.${NC}"
    fi
fi

echo -e "${GREEN}✓ Python: $(which python)${NC}"

# Start the backend server
echo ""
echo -e "${BLUE}Starting backend server on port 8001...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

python -m backend.main

