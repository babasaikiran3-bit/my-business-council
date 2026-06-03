<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# newport-beach (Parenting Roundtable)

## Purpose
Repository root for **Parenting Roundtable**, a science-based pediatric/parenting advisor. A parent submits a question plus the child's age and a 4-stage LLM-council pipeline answers it: **Stage 0** grounds the answer with an Exa web search restricted to a trusted medical-domain allowlist (AAP, WHO, CDC, NHS, Cochrane, PubMed, Mayo, NIH, AAFP) and produces an advice-free evidence brief + real citations; **Stage 1** has 3 council models reason only from that shared evidence; **Stage 2** runs anonymized peer ranking; **Stage 3** has a Chairman synthesize one safety-first answer with consolidated Sources and a deterministic newborn-fever EMERGENCY backstop. The app is a FastAPI backend (`backend/`) + React/Vite SPA (`frontend/`) with sessions, OAuth (Kakao/Naver), per-user quotas, and a dedicated safety module. This directory holds the project README, technical notes, deployment/runbook, container + Fly.io config, packaging, and a manual smoke test. The root also contains `uv.lock` (the frozen Python lockfile consumed by the Dockerfile) and `header.jpg` (README banner image) — neither is edited directly.

## Key Files
| File | Description |
| --- | --- |
| `README.md` | Project overview, the 4-stage pipeline explanation, local setup (`uv sync`, npm), `.env` config, and how to run via `./start.sh` or manually. |
| `CLAUDE.md` | Deep technical notes: data flow, backend/frontend module responsibilities, key design decisions (deterministic citations, layered safety), and common gotchas. **Note: predates the auth/OAuth/quota/safety-module growth — read the actual `backend/` files, do not assume it is complete.** |
| `DEPLOYMENT.md` | Pilot deployment runbook: env vars, cross-site cookie/CSRF rationale, Fly.io backend + Vercel/Netlify frontend, OAuth registration, smoke checks, backups/rollback, and the single-worker "pilot ceiling." |
| `Dockerfile` | `python:3.11-slim` image; installs from `uv.lock` via `uv sync --frozen --no-dev`, copies only `backend/`, exposes 8001, `/health` HEALTHCHECK, runs `gunicorn` with a **single** Uvicorn worker (`-w 1`, load-bearing). |
| `fly.toml` | Fly.io config (app `parenting-roundtable`, region `nrt`). Pins `ENVIRONMENT=production`, `DATA_DIR=/data/conversations`, mounts persistent volume `pr_data` at `/data`, `min_machines_running=1`, `/health` check on internal port 8001. |
| `main.py` | **Thin placeholder launcher** — only prints "Hello from llm-council!". The real ASGI app is `backend.main:app`; run the backend via `python -m backend.main`, not this file. |
| `pyproject.toml` | Project `llm-council`, `requires-python>=3.10`. Deps: fastapi, uvicorn[standard], python-dotenv, httpx, pydantic, slowapi, gunicorn. Dev: pytest, pytest-asyncio. Configures pytest (`testpaths=["tests"]`, `asyncio_mode=auto`, `integration` marker) and ruff (line-length 110, ignore E501). |
| `start.sh` | Dev convenience script: launches backend (`uv run python -m backend.main`, port 8001) and frontend (`npm run dev`, port 5173) together, traps Ctrl+C to kill both. |
| `test_openrouter.py` | Standalone manual smoke test (`uv run python test_openrouter.py`) for the Stage 0 researcher — calls `query_model` with web search restricted to `TRUSTED_DOMAINS`, prints content, raw annotations, and `extract_citations()` output. Guards on `OPENROUTER_API_KEY`. Not part of the pytest suite in `tests/`. |
| `.env.example` | Annotated template for `.env` (gitignored). Required: `OPENROUTER_API_KEY`, `SESSION_SECRET` (prod fail-fast). Plus `ENVIRONMENT`, `DATA_DIR`, CORS/frontend, rate-limit/quota knobs, per-stage timeouts, and optional Kakao/Naver OAuth. |
| `.dockerignore` | Keeps the image lean: excludes `frontend`, `data`, `tests`, `.github`, `.omc`, `*.md`, `header.jpg`, `.env`, VCS, and caches. |
| `.python-version` | Pins local Python to `3.10` (Docker uses 3.11; `requires-python>=3.10`). |

## Subdirectories
| Directory | Purpose |
| --- | --- |
| `backend/` | FastAPI app, the 4-stage council orchestration, OpenRouter client, storage, auth/OAuth, quotas, and the safety module (see `backend/AGENTS.md`). |
| `frontend/` | React 19 + Vite SPA: chat UI, per-stage components, safe-markdown link neutralization, auth pages (see `frontend/AGENTS.md`). |
| `tests/` | pytest suite (`asyncio_mode=auto`); integration tests guarded behind the `integration` marker + a live API key (see `tests/AGENTS.md`). |
| `.github/` | CI workflows (lint/build/test) (see `.github/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- **`main.py` is a decoy launcher.** Do not wire the app through it. The ASGI entrypoint is `backend.main:app`; run with `uv run python -m backend.main` (dev, port **8001**) or `gunicorn backend.main:app -k uvicorn.workers.UvicornWorker -w 1` (prod).
- **Port is 8001, never 8000** (the original author had another app on 8000). It is hardcoded in `start.sh`, `Dockerfile`, `fly.toml`, and the backend; change all of them together if you ever move it. Frontend dev server is **5173**.
- **Single worker / single machine is an invariant, not a tuning choice.** The storage `asyncio.Lock`, the in-memory rate limiter, and the disk-backed daily quota all assume one process. Never raise `-w` above 1 or run multiple Fly machines without first migrating to Postgres + a shared rate-limit store (the `StorageBackend` seam is ready; see `DEPLOYMENT.md` §9).
- **Persistent disk is load-bearing in prod.** `DATA_DIR` must point at a mounted volume (`/data/conversations` on Fly). A PaaS ephemeral filesystem loses every conversation on redeploy.
- **`SESSION_SECRET` fail-fast.** With `ENVIRONMENT=production`, the app refuses to start without a ≥32-char `SESSION_SECRET` and a valid non-`*` `CORS_ORIGINS`. Keep `.env.example` in sync when adding required env vars.
- **Tooling: `python`/`ruff` are NOT on PATH.** Use `uv run python ...`, `uvx ruff ...`. Install deps with `uv sync`; the Docker build uses `uv sync --frozen`, so regenerate `uv.lock` (via `uv lock`/`uv sync`) whenever you touch `pyproject.toml` dependencies.
- **Relative imports in the backend** (`from .config import ...`) — always run from the repo root, never from inside `backend/`.
- **Dockerfile copies only `backend/`** — it does not include `tests/`, `frontend/`, or root `*.md`. The container serves the API only; the frontend deploys separately to Vercel/Netlify.

### Testing Requirements
```bash
# Backend compile + lint + import sanity (tools via uv)
uv run python -m py_compile backend/*.py test_openrouter.py
uvx ruff check backend/ test_openrouter.py
uv run python -c "from backend import main, council, openrouter, config, storage"

# Unit/async test suite (integration tests are skipped without a key)
uv run pytest

# Stage 0 live smoke (requires OPENROUTER_API_KEY in .env)
uv run python test_openrouter.py

# Frontend build
cd frontend && npm run build

# Container smoke (see DEPLOYMENT.md §6)
docker build -t pr-backend .
curl -s localhost:8001/health   # {"status":"ok"}  ;  /ready → 200 when key+secret+writable disk
```
Safety spot-checks before shipping: a newborn (0–3mo) + fever query MUST surface the red emergency banner with real trusted-domain sources; a benign query (e.g. toddler nap transition) must NOT fear-monger yet still cite sources. (Korean variants are checked in `DEPLOYMENT.md` §6.)

### Common Patterns
- **uv-first Python workflow**: `uv sync` to install, `uv run ...` to execute, `uvx ruff ...` to lint, `uv lock` (frozen in Docker) for reproducibility.
- **Env-driven config**: behavior toggles by `ENVIRONMENT` (`dev` vs `production`) and env vars loaded from `.env`; model/domain config lives in `backend/config.py`, not env.
- **Two run modes**: dev = Uvicorn via `python -m backend.main`; prod = gunicorn 1×UvicornWorker in the container. Health/readiness split: `/health` (liveness) vs `/ready` (key + secret + writable disk).
- **Graceful degradation everywhere**: a failed model returns `None` and is skipped; Stage 0 failure yields an empty evidence base; the request never fails on a single model.

## Dependencies

### Internal
- `backend/` package is the actual application; this root only launches, packages, and deploys it. `start.sh`, `Dockerfile`, and `fly.toml` all target `backend.main:app`.
- `test_openrouter.py` imports `backend.config` and `backend.openrouter`.
- `pyproject.toml` `[tool.pytest]` points the test runner at `tests/`.

### External
- **Runtime**: fastapi, uvicorn[standard], gunicorn (prod), httpx (async OpenRouter calls), pydantic, python-dotenv, slowapi (rate limiting).
- **Dev/test**: pytest, pytest-asyncio; ruff (via `uvx`).
- **Services**: OpenRouter API (LLM access + Exa web-search plugin) keyed by `OPENROUTER_API_KEY`; optional Kakao/Naver OAuth.
- **Tooling/infra**: `uv` (Astral) for Python; Docker (`python:3.11-slim`) and Fly.io for the backend; Vercel/Netlify for the frontend.

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
