# LLM Council

![llmcouncil](header.jpg)

Instead of asking one LLM, convene your personal **LLM Council**. Multiple
models answer independently, review each other's work anonymously, and a
chairman synthesizes the final response. The council runs on your machine using
local CLI agents (Claude Code, Codex, Gemini) and optional API-based providers
(DeepSeek, GLM, Kimi, Grok) — not a third-party proxy.

When you select a repository, council members explore its code before answering
and can document their consensus directly into `docs/council/`.

## How It Works (4 stages)

1. **Stage 0 — Research.** A research officer gathers current web information
   relevant to the question so the council works from up-to-date facts, not
   stale training data. (Optional; toggleable per query.)

2. **Stage 1 — First opinions.** Every council member receives the question
   (with conversation history, research brief, and repository context) and
   explores independently. Live progress streams to the UI via SSE — tool
   calls, file reads, and intermediate thoughts are visible as they happen.

3. **Stage 2 — Peer review.** Each member receives the anonymized Stage 1
   responses labeled "Response A", "Response B", etc. They evaluate and rank
   them. Identities are revealed only on the client side for display;
   evaluators never know whose response they're judging.

4. **Stage 3 — Chairman synthesis.** The chairman reads all responses and
   rankings, then produces a single consolidated answer. When a repository is
   selected, you can preview, approve, and persist that consensus as a
   markdown document (`docs/council/<slug>.md`) inside the repo.

## Prerequisites

- **Python 3.10+** and [uv](https://docs.astral.sh/uv/) for backend
  dependencies.
- **Node.js** and **npm** for the frontend.
- **Provider CLIs** — at least one of `claude`, `codex`, or `agy` in `PATH`
  (or `~/.local/bin/`). These are the native agents with file-system access.
- **API keys** (optional) — for API-based models, create plain-text key files
  at the paths expected by `models_registry.py`:
  - `~/.deepseek_key` — DeepSeek (agent + flash title model)
  - `~/.aiapi_key` — GLM, Kimi, Grok via aiapi.world

No `.env` file is required. Keys are read from individual files, never from
environment variables in the backend process.

## Setup

```bash
# Backend (Python)
uv sync

# Frontend (JavaScript)
cd frontend && npm install && cd ..
```

## Configuration

### Council membership

Edit the council's active members and chairman through the web UI (⚙️ Models
panel). The selection is persisted to `data/council_config.json`. Unavailable
models (missing binary or key) are filtered out automatically.

### Model registry

`backend/models_registry.py` defines every known model and its transport:

| Transport | Mechanism | Example models |
|---|---|---|
| `cli_native` | Local agent binary (`claude`, `codex`, `agy`) | Claude, Codex, Gemini |
| `anthropic_agent` | Claude Code pointed at an Anthropic-compatible API | DeepSeek, GLM, Kimi, Grok |
| `openai_api` | Blind REST POST (no tools, no file access) | DeepSeek Flash (titles only) |

To add a new model, add its entry to the `REGISTRY` dict — no logic changes
needed.

### Data paths

All runtime data lives under `COUNCIL_HOME` (default: `<project_root>/data`).
Paths are absolute and deterministic regardless of the working directory.

| Path | Default | Override env var |
|---|---|---|
| SQLite database | `data/council.db` | `COUNCIL_DB_PATH` |
| Council config | `data/council_config.json` | `COUNCIL_CONFIG_PATH` |
| Agent working dir | `data/agent-cwd/` | `COUNCIL_AGENT_CWD` |
| Legacy JSON dir | `data/conversations/` | `COUNCIL_DATA_DIR` |

Set `COUNCIL_HOME=<tmpdir>` to isolate every data file for tests. Individual
overrides (`COUNCIL_DB_PATH`, etc.) take precedence over `COUNCIL_HOME`.
`:memory:` is preserved verbatim for in-memory SQLite.

### Repository detection

Autodetected from `~`, `~/GitHub`, and `/mnt/Datos` (one level deep). Extend
via `COUNCIL_REPO_ROOTS` (comma-separated). A repo is validated against these
roots (anti-path-traversal) before agents receive it as `cwd`.

## Running the Application

### council.sh (recommended)

```bash
./council.sh start          # start both services, open browser
./council.sh start --no-open  # start without opening browser
./council.sh stop           # stop both services
./council.sh restart        # restart
./council.sh status         # are backend/frontend up?
./council.sh logs           # tail both logs
```

`council.sh` manages pidfiles and logs under `data/run/`, uses `setsid` for
process-group cleanup, and waits for the backend to become healthy before
reporting success.

> **Note:** `council.sh` hardcodes `DIR="/home/andres/llm-council"` (line 5).
> If you cloned the repository elsewhere, either edit that path or use
> `start.sh` / the manual commands instead.

### start.sh (simple alternative)

```bash
./start.sh     # Ctrl+C to stop both
```

Launches backend and frontend in the background; traps SIGINT/SIGTERM to tear
both down.

### Manual

```bash
# Terminal 1 — Backend (port 8001)
uv run python -m backend.main

# Terminal 2 — Frontend (port 5173)
cd frontend && npm run dev
```

Open **http://localhost:5173**.

## Tech Stack

- **Backend:** FastAPI (Python 3.10+), asyncio, httpx
- **Frontend:** React 19 + Vite 7, react-markdown
- **Storage:** SQLite with ordered transactional migrations (WAL mode,
  `busy_timeout=5000ms`, foreign keys enforced)
- **Streaming:** Server-Sent Events (SSE) — one event per line, canonical
  event contract shared by all providers
- **Providers:** Data-driven dispatch via `models_registry.py` →
  `providers.py` / `streaming.py`. `WorkerExecutor` manages subprocess
  lifecycle (stdout/stderr, timeouts, cancellation, process-group cleanup).
- **Package management:** uv (Python), npm (JavaScript)

## Development

### Tests

```bash
# Backend (no real providers, no API keys consumed) — 121 tests total
uv run pytest tests/ backend/tests/ -v

# Frontend
cd frontend && npm test && cd ..
```

### Lint

```bash
cd frontend && npm run lint && cd ..
```

### Build

```bash
cd frontend && npm run build && cd ..
```

### Backend import check

```bash
uv run python -c "from backend import storage, migrations, paths; print('OK')"
```

### Full local gate

```bash
uv run pytest tests/ backend/tests/ -v && \
  uv run python -c "from backend import storage, migrations, paths; print('OK')" && \
  cd frontend && npm run lint && npm run build && cd .. && \
  git diff --check
```

## Security

**Read-only by policy, not by OS sandbox.** During deliberation (Stages 0–3):

- **Codex** runs with `--sandbox read-only`, which technically enforces a
  read-only filesystem view.
- **Claude, agy, and all anthropic_agent models** (DeepSeek, GLM, Kimi,
  Grok) are launched with `--dangerously-skip-permissions`, which bypasses
  the agent's own permission prompts and gives them the **user's full
  filesystem authority**. They can write, modify, or delete files. The
  "read-only" property is upheld by prompt instructions and flow design,
  not by a technical enforcement boundary.

- **Consensus write is opt-in and staged.** You must (a) select a repo,
  (b) request a preview (read-only), (c) review the generated document, and
  (d) explicitly approve it. Only then does the _backend_ (not the model)
  write a single file to `docs/council/<slug>.md`. You can discard the
  preview at any point. This is the only *intended* application write flow.

- **Dangerous flags grant real authority.** `--dangerously-skip-permissions`
  (used for Claude, agy, and anthropic_agent transports) gives the agent the
  same filesystem access as your user account. `--sandbox workspace-write`
  (used for Codex when ``allow_write=True``) enables a writable sandbox.
  These are CLI-level flags, not sandbox boundaries. Always review
  ``git diff`` after any session where an agent had write access.

- **No-push is a policy, not a programmatic boundary.** Workers do not push
  to remotes under normal operation because the prompts and flow never
  authorize it. There is no network-level or git-hook enforcement. Push,
  force-push, and destructive Git operations are only guarded by the prompt
  instructions given to each agent.

- **Repository validation.** Repos are checked against allowed roots
  (`COUNCIL_REPO_ROOTS`) with `realpath`-based anti-traversal before any
  agent receives them as `cwd`.

- **No secrets in prompts or events.** API keys live in separate files
  (`~/.deepseek_key`, `~/.aiapi_key`), are read at execution time, and are
  never included in conversation storage, SSE events, or UI state.

## Roadmap (future — not implemented)

**ADR 0003** defines a **Room** mode with persistent multi-agent conversations
and parallel code tasks in isolated Git worktrees. It is **not yet built**.
The current application is the Council pipeline described above. Room
requires the stabilization gate defined in **ADR 0002** to be met first.

Summary of what Room will add (when implemented):

- Persistent participants with presence states (active / listening / muted /
  left)
- Round-based turn-taking with `@mentions`, handoff, and pass
- Explicit `/assign` of code tasks to individual agents
- One Git worktree + branch per task, isolated from the main working tree
- Review → accept → integrate workflow with human approval at each
  irreversible step

## Architecture Decision Records

See `docs/adr/` and `docs/SSD.md` in the main repository:

- **ADR 0001** — Chairman can write consensus into the analyzed repo
  (Accepted; opt-in preview-then-approve)
- **ADR 0002** — Stabilize baseline and runtime before implementing Room
  (Proposed; stabilization in-progress)
- **ADR 0003** — Room mode with coordinated turns and parallel worktree tasks
  (Proposed; blocked on ADR 0002 gate)
- **SSD** — Software Design Specification (SSE transport, event
  normalization, repo autodetection, model registry, security)
