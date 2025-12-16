#!/bin/bash
# ============================================
# Eternal Ops Control - Frontend Runner
# ============================================
# Usage:
#   ./run-frontend.sh              - Run in development mode (default)
#   ./run-frontend.sh --staging    - Run in staging mode
#   ./run-frontend.sh --production - Run in production mode
#   ./run-frontend.sh --help       - Show this help message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default environment
MODE="development"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --development|-d)
            MODE="development"
            shift
            ;;
        --staging|-s)
            MODE="staging"
            shift
            ;;
        --production|-p)
            MODE="production"
            shift
            ;;
        --help|-h)
            echo "Eternal Ops Control - Frontend Runner"
            echo ""
            echo "Usage: ./run-frontend.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -d, --development  Run in development mode (default)"
            echo "  -s, --staging      Run in staging mode"
            echo "  -p, --production   Run in production mode"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run-frontend.sh                # Development mode"
            echo "  ./run-frontend.sh --staging      # Staging mode"
            echo "  ./run-frontend.sh --production   # Production mode"
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
if [ "$MODE" = "production" ]; then
    echo -e "${RED}⚠️  WARNING: You are about to run frontend in PRODUCTION mode!${NC}"
    echo -e "${YELLOW}This will use production API endpoints and credentials.${NC}"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 1
    fi
fi

MODE_UPPER=$(echo "$MODE" | tr '[:lower:]' '[:upper:]')
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Eternal Ops Control Frontend - ${MODE_UPPER} Mode${NC}"
echo -e "${BLUE}============================================${NC}"

cd frontend

# Check for required environment file
ENV_FILE=".env.${MODE}"
if [ "$MODE" = "development" ] && [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env" ]; then
        ENV_FILE=".env"
        echo -e "${YELLOW}Note: Using .env as fallback (no .env.development found)${NC}"
    fi
fi

if [ ! -f "$ENV_FILE" ] && [ "$MODE" != "development" ]; then
    echo -e "${RED}Error: $ENV_FILE not found!${NC}"
    echo -e "Please create $ENV_FILE from ${ENV_FILE}.example"
    exit 1
fi

echo -e "${GREEN}✓ Environment file: $ENV_FILE${NC}"
echo -e "${GREEN}✓ Vite mode: $MODE${NC}"

# Start the frontend dev server
echo ""
echo -e "${BLUE}Starting frontend dev server on port 5173...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

npm run dev -- --mode "$MODE"

