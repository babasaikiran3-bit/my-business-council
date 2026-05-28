# Backend

This directory contains the FastAPI backend and the core council orchestration logic.

## Entry Point

Run the backend from the project root:

```bash
uv run python -m backend.main
```

The API listens on port `8001`.

## Required Environment

The backend requires:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

This is loaded from the project root `.env` file by [config.py](config.py).

## Main Modules

- [main.py](main.py): FastAPI routes and streaming response orchestration
- [council.py](council.py): three-stage council flow, ranking parsing, aggregate ranking calculation, and chairman fallback
- [openrouter.py](openrouter.py): OpenRouter request helpers and error formatting
- [storage.py](storage.py): JSON-backed conversation persistence
- [config.py](config.py): model configuration, API key loading, and data directory settings

## API Routes

- `GET /`: health check
- `GET /api/conversations`: list conversations
- `POST /api/conversations`: create a conversation shell
- `DELETE /api/conversations`: delete all conversations
- `GET /api/conversations/{conversation_id}`: load one conversation
- `DELETE /api/conversations/{conversation_id}`: delete one conversation
- `POST /api/conversations/{conversation_id}/message`: run the full council flow and return all stage results
- `POST /api/conversations/{conversation_id}/message/stream`: stream each stage as server-sent events

## Storage Model

Conversation history is persisted as JSON files under `data/conversations/`.

Implications:

- simple local development
- easy inspection and backup
- not safe for horizontal scaling without replacing the storage layer

## Deployment Notes

- Local development expects the frontend at `http://localhost:5173`.
- The Kubernetes manifest mounts `/app/data` from a persistent volume claim.
- Keep backend replicas at `1` unless you move storage to a shared system.
