# LLM Council

![llmcouncil](header.jpg)

LLM Council is a local web app that asks multiple large language models the same question, has them rank each other's answers anonymously, and then uses a chairman model to synthesize a final response.

## What It Does

Each message runs through three stages:

1. Stage 1 collects independent answers from each configured council model.
1. Stage 2 anonymizes those answers as `Response A`, `Response B`, and so on, then asks the models to rank them.
1. Stage 3 asks the chairman model to synthesize a final answer using the stage 1 responses and stage 2 rankings.

The UI exposes the full pipeline so you can inspect what happened instead of only seeing the final answer.

## Current Features

- Tabbed stage 1 model responses.
- Stage 2 raw peer evaluations, extracted rankings, aggregate rankings, and a ranking heatmap.
- Stage 3 final synthesis with chairman attribution.
- Copy buttons for user prompts, stage 1 responses, and the final answer.
- Conversation title generation from the first user message.
- Per-conversation delete and clear-history actions.
- Chairman fallback when the configured chairman model fails during synthesis.
- Optional Kubernetes deployment manifests with separate frontend and backend images.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- An [OpenRouter](https://openrouter.ai/) API key

## Quick Start

### Install Dependencies

Backend:

```bash
uv sync
```

Frontend:

```bash
cd frontend
npm install
cd ..
```

### Configure Environment

Create a `.env` file in the project root. You can start from `.env.example`.

```bash
cp .env.example .env
```

Required variable:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

The backend validates this at startup and will fail fast if it is missing.

### Run Locally

Use the provided launcher:

```bash
./start.sh
```

Or run each service manually.

Backend:

```bash
uv run python -m backend.main
```

Frontend:

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Configuration

Edit [backend/config.py](backend/config.py) to change the council members, chairman model, or data directory.

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
DATA_DIR = "data/conversations"
```

### Frontend API Base

Local development defaults to `http://localhost:8001`.

If you need the frontend to target a different backend, set `VITE_API_BASE` before building or running the frontend:

```bash
cd frontend
VITE_API_BASE=http://localhost:8001 npm run dev
```

In the production container, `VITE_API_BASE` is intentionally left empty so the frontend calls `/api/...` and lets Nginx proxy requests to the backend service.

## Project Layout

- [backend/](backend): FastAPI app, council orchestration, OpenRouter client, and JSON conversation storage.
- [frontend/](frontend): React and Vite single-page app.
- [k8s/](k8s): Kubernetes manifests and deployment notes.
- [Dockerfile.backend](Dockerfile.backend): Backend image build.
- [Dockerfile.frontend](Dockerfile.frontend): Frontend image build.

## Backend API

The backend entry point is [backend/main.py](backend/main.py).

Routes:

- `GET /`: health check
- `GET /api/conversations`: list conversation metadata
- `POST /api/conversations`: create a conversation
- `DELETE /api/conversations`: clear all conversations
- `GET /api/conversations/{conversation_id}`: load one conversation
- `DELETE /api/conversations/{conversation_id}`: delete one conversation
- `POST /api/conversations/{conversation_id}/message`: run the full council flow synchronously
- `POST /api/conversations/{conversation_id}/message/stream`: stream stage progress as server-sent events

Additional backend notes are in [backend/README.md](backend/README.md).

## Frontend Notes

The frontend renders each assistant message as a three-stage council transcript.

- Stage 1 shows individual model tabs.
- Stage 2 shows raw evaluations, parsed rankings, aggregate rankings, and the ranking heatmap.
- Stage 3 shows the final chairman answer.

Additional frontend notes are in [frontend/README.md](frontend/README.md).

## Kubernetes

This repo can run on Kubernetes as two workloads:

- A FastAPI backend on port `8001`
- An Nginx-served frontend on port `80`

The frontend service proxies `/api/*` to the backend service, so the browser only needs to talk to one public origin.

### Build and Push Images

```bash
docker build -f Dockerfile.backend -t ghcr.io/your-org/llm-council-backend:latest .
docker build -f Dockerfile.frontend -t ghcr.io/your-org/llm-council-frontend:latest .

docker push ghcr.io/your-org/llm-council-backend:latest
docker push ghcr.io/your-org/llm-council-frontend:latest
```

### Deploy

1. Update the image names in [k8s/llm-council.yaml](k8s/llm-council.yaml).
1. Update the ingress host in [k8s/llm-council.yaml](k8s/llm-council.yaml).
1. Create the secret:

```bash
kubectl create namespace llm-council
kubectl create secret generic llm-council-secrets \
  --namespace llm-council \
  --from-literal=OPENROUTER_API_KEY=sk-or-v1-...
```

1. Apply the manifest:

```bash
kubectl apply -f k8s/llm-council.yaml
```

Deployment details are documented in [k8s/README.md](k8s/README.md).

## Limitations

- Conversation storage is local JSON on disk, not a shared database.
- Because of that storage model, the backend should stay at one replica unless you change persistence.
- Model availability, latency, and pricing depend on OpenRouter and the configured model set.
- The frontend uses server-sent events for streaming, so reverse proxies need buffering disabled for the streaming endpoint.

## Troubleshooting

### Missing API Key

If the backend exits immediately with an `OPENROUTER_API_KEY is not set` error, create `.env` in the project root or export the variable before starting the backend.

### Frontend Cannot Reach Backend

For local development, verify the backend is running on port `8001` or override `VITE_API_BASE`.

### Kubernetes Streaming Seems Stuck

The ingress and Nginx template in this repo disable proxy buffering for `/api/`, which is required for the streaming endpoint. If you use a different ingress controller or proxy, make sure it also allows streaming responses.

## Developer Docs

- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)
- [k8s/README.md](k8s/README.md)
