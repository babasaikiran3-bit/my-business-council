#!/usr/bin/env bash
set -euo pipefail

# Simple helper to:
# 1) Create a conversation
# 2) Verify and store the conversation ID
# 3) Send the first message (non-stream or stream)
#
# Usage:
#   bash scripts/council.sh -m "Your question"
#   bash scripts/council.sh --stream -m "Your question"
#   bash scripts/council.sh               # will prompt for message
#
# Env:
#   COUNCIL_API_URL (default: http://127.0.0.1:8001)
#
# Outputs:
#   - Prints the conversation ID
#   - Saves it to .council_last_cid in project root

API_URL="${COUNCIL_API_URL:-http://127.0.0.1:8001}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CID_FILE="${PROJECT_ROOT}/.council_last_cid"

STREAM=0
MESSAGE=""

usage() {
  echo "Usage: $0 [--stream] [-m MESSAGE]"
  echo "       COUNCIL_API_URL can override API base (default: ${API_URL})"
}

while (( "$#" )); do
  case "$1" in
    --stream)
      STREAM=1
      shift
      ;;
    -m)
      if [ "${2:-}" = "" ]; then
        echo "Error: -m requires a message"
        usage
        exit 1
      fi
      MESSAGE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      usage
      exit 1
      ;;
  esac
done

command -v jq >/dev/null 2>&1 || { echo "Error: jq is required."; exit 1; }

# Health check
if ! curl -fsS "${API_URL}/" >/dev/null; then
  echo "Error: Council API not reachable at ${API_URL}"
  exit 1
fi

# Create conversation
CID="$(curl -sS -H "Content-Type: application/json" -d '{}' "${API_URL}/api/conversations" | jq -r .id)"
if [ -z "${CID}" ] || [ "${CID}" = "null" ]; then
  echo "Error: Failed to create conversation (no ID returned)."
  exit 1
fi

echo "${CID}" > "${CID_FILE}"
echo "Conversation ID: ${CID}"
echo "(Saved to ${CID_FILE})"

# Get message if not provided
if [ -z "${MESSAGE}" ]; then
  echo -n "Enter your first message: "
  IFS= read -r MESSAGE
fi

# Build JSON safely
PAYLOAD="$(jq -n --arg content "$MESSAGE" '{content:$content}')"

if [ "${STREAM}" -eq 1 ]; then
  echo "Streaming response (SSE)..."
  curl -N -H "Content-Type: application/json" \
    -d "${PAYLOAD}" \
    "${API_URL}/api/conversations/${CID}/message/stream"
else
  curl -sS -H "Content-Type: application/json" \
    -d "${PAYLOAD}" \
    "${API_URL}/api/conversations/${CID}/message" | jq .
fi


