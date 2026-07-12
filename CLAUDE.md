# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 4-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites. Stage 0 (optional) gathers current web research before the council deliberates.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Re-exports model defaults (`DEFAULT_MEMBERS`, `DEFAULT_CHAIRMAN`, `TITLE_MODEL`)
  from `models_registry.py` and deterministic paths from `paths.py`
  (`DB_PATH`, `DATA_DIR`, `COUNCIL_CONFIG_PATH`, `AGENT_CWD`).
- No `.env` file; provider keys live in individual files
  (`~/.deepseek_key`, `~/.aiapi_key`) read at execution time by `providers.py`.
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`paths.py`** — Deterministic data paths (ADR 0002 §2)
- Computes absolute paths via `pathlib.Path`, rooted at the project directory
  (the directory containing `backend/`).  No cwd-dependence.
- Derives `DB_PATH`, `DATA_DIR`, `COUNCIL_CONFIG_PATH`, `AGENT_CWD` from
  `COUNCIL_HOME` (default: `<project_root>/data`).
- Individual overrides: `COUNCIL_DB_PATH`, `COUNCIL_DATA_DIR`,
  `COUNCIL_CONFIG_PATH`, `COUNCIL_AGENT_CWD` — each trumps the
  `COUNCIL_HOME`-derived default.
- For tests, set `COUNCIL_HOME=<tmpdir>` to isolate every data file in a
  temp directory.

**`migrations.py`** — Ordered, transactional schema migrations (ADR 0002 §2)
- Registry of `(version, name, callable)` tuples decorated with `@register`.
- `migrate(conn)` applies all pending migrations in version order, each in
  its own transaction.
- `current_version(conn)` returns the highest applied version (0 if none).
- Migrations table: `_migrations(version INTEGER PK, name TEXT, applied_at TEXT)`.
- Current migrations:
  1. `bootstrap_schema` — conversations + messages tables (idempotent, `IF NOT EXISTS`)
  2. `add_repo_path_column` — `ALTER TABLE` guarded by `PRAGMA table_info`
  3. `add_message_position_unique` — unique index on `(conversation_id, position)`
- `storage.init_db()` delegates to `migrations.migrate()`; no more ad-hoc DDL.

**`providers.py`** — Data-driven provider dispatch (replaces the deleted `openrouter.py`)
- `query_model()` / `query_models_parallel()`: route a model id to its transport.
- Three transports resolved from `models_registry.py`:
  - `cli_native` — local agent binary (`claude`, `codex`, `agy`) with filesystem access
  - `anthropic_agent` — Claude Code pointed at an Anthropic-compatible API (DeepSeek, GLM, etc.)
  - `openai_api` — blind REST POST, no tools (titles only)
- `allow_write` flag enables workspace-write sandbox on codex; ignored by other transports.
- Graceful degradation: returns None on failure, continues with successful responses.

**`models_registry.py`** — Declarative model universe
- `REGISTRY` dict maps model ids to transport specs (bin, key_file, base URL, model name).
- `DEFAULT_MEMBERS` / `DEFAULT_CHAIRMAN` define the out-of-box council.
- To add a model, add its entry here — no logic changes needed.

**`council_config.py`** — Active council selection + health checks
- Persists active members + chairman to `data/council_config.json`.
- `health()` checks binary/key availability without network calls.
- `load_config()` filters out unavailable models; `validate_config()` rejects
  unknown or unhealthy models on PUT.

**`streaming.py`** — Live SSE event emission for Stage 1
- Wraps each provider's native event format into canonical SSE events via `WorkerExecutor`.
- Parsers: `parse_claude_event` (stream-json), `parse_codex_event` (--json).
- Gemini has no event stream → falls back to batch with working→done emission.

**`council.py`** - The Core Logic
- `stage0_research()`: Research officer gathers current web facts before deliberation.
- `stage1_collect_responses()`: Parallel queries to all council models (batch mode).
- `stage2_collect_rankings()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Prompts models to evaluate and rank (with strict format requirements)
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
- `stage3_synthesize_final()`: Chairman synthesizes from all responses + rankings
  (always read-only; consensus write is a separate post-deliberation action).
- `generate_consensus_doc()`: Chairman generates (does not write) a consensus markdown
  document for preview before approval.
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both
  numbered lists and plain format.
- `calculate_aggregate_rankings()`: Computes average rank position across all
  peer evaluations.
- `run_full_council()`: Batch orchestration (used by CLI `debate.py`).
- `run_full_council_streaming()`: SSE orchestration with per-agent live events.
- `generate_conversation_title()`: Auto-titles new conversations via a cheap model.

**`storage.py`**
- SQLite-based conversation storage in `data/council.db` (path from `paths.py`)
- Schema is now applied via ``migrations.migrate()``; ``init_db()`` is the
  single entry point that ensures directory, file, and schema exist.
- Connection policy: ``busy_timeout=5000``, ``journal_mode=WAL``,
  ``foreign_keys=ON``.  Each public API function opens/closes its own
  connection via ``with _connect()``.
- Conversation format: `{id, created_at, title, repo_path, messages[]}`
- Assistant messages contain: `{role, stage1, stage2, stage3}`
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- POST `/api/conversations/{id}/message` returns metadata in addition to stages
- Metadata includes: label_to_model mapping and aggregate_rankings

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- Handles message sending, SSE event dispatch, and metadata storage
- Important: metadata is stored in the UI state for display but not persisted to backend storage
  (the DB stores stage1/2/3; label_to_model and aggregate_rankings are ephemeral API return values)

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable)
- Enter to send, Shift+Enter for new line
- User messages wrapped in markdown-content class for padding

**`components/Stage1.jsx`**
- Tab view of individual model responses
- ReactMarkdown rendering with markdown-content wrapper

**`components/Stage2.jsx`**
- **Critical Feature**: Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display (models receive anonymous labels)
- Shows "Extracted Ranking" below each evaluation so users can validate parsing
- Aggregate rankings shown with average position and vote count
- Explanatory text clarifies that boldface model names are for readability only

**`components/Stage3.jsx`**
- Final synthesized answer from chairman
- Green-tinted background (#f0fff0) to highlight conclusion

**Styling (`*.css`)**
- Light mode theme (not dark mode)
- Primary color: #4a90e2 (blue)
- Global markdown styling in `index.css` with `.markdown-content` class
- 12px padding on all markdown content to prevent cluttered appearance

## Key Design Decisions

### Stage 2 Prompt Format
The Stage 2 prompt is very specific to ensure parseable output:
```
1. Evaluate each response individually first
2. Provide "FINAL RANKING:" header
3. Numbered list format: "1. Response C", "2. Response A", etc.
4. No additional text after ranking section
```

This strict format allows reliable parsing while still getting thoughtful evaluations.

### De-anonymization Strategy
- Models receive: "Response A", "Response B", etc.
- Backend creates mapping: `{"Response A": "claude", "Response B": "codex", ...}`
- Frontend displays model names in **bold** for readability
- Users see explanation that original evaluation used anonymous labels
- This prevents bias while maintaining transparency

### Error Handling Philosophy
- Continue with successful responses if some models fail (graceful degradation)
- Never fail the entire request due to single model failure
- Log errors but don't expose to user unless all models fail

### UI/UX Transparency
- All raw outputs are inspectable via tabs
- Parsed rankings shown below raw text for validation
- Users can verify system's interpretation of model outputs
- This builds trust and allows debugging of edge cases

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`) not absolute imports. This is critical for Python's module system to work correctly when running as `python -m backend.main`.

### Port Configuration
- Backend: 8001 (changed from 8000 to avoid conflict)
- Frontend: 5173 (Vite default)
- Update both `backend/main.py` and `frontend/src/api.js` if changing

### Markdown Rendering
All ReactMarkdown components must be wrapped in `<div className="markdown-content">` for proper spacing. This class is defined globally in `index.css`.

### WorkerExecutor Lifecycle (ADR 0002 §3-4)
Subprocess execution is managed by `backend/worker_executor.py`:
- Each worker runs in its own process group (`start_new_session=True`).
- stdout and stderr are consumed concurrently (no stderr pipe stall).
- Terminal states: `completed | failed | timed_out | cancelled`.
- `CancellationToken` supports cooperative cancellation; SIGTERM then SIGKILL
  escalation on the process group.
- Temp files are cleaned up even on exception paths.
- `final_file` option reads result from a sidecar file (used by codex `-o`).
- `inactivity_timeout` kills workers that produce no output for N seconds.

### Consensus Write Flow (ADR 0001)
Consensus documentation is a three-step, human-gated workflow:
1. **Preview** (`POST .../document-consensus`) — chairman generates markdown
   read-only; no file is written. The draft is stored in the message as
   `pending_consensus`.
2. **Approve** (`POST .../document-consensus/approve`) — the *backend* writes
   the approved content to `docs/council/<slug>.md` inside the repo. Path is
   forced to that subdirectory (anti-traversal).
3. **Discard** (`POST .../document-consensus/discard`) — drops the draft.

### Security: Dangerous Flags Are Not a Sandbox
`--dangerously-skip-permissions`, `--sandbox workspace-write`, and similar CLI
flags are transport-level instructions, not a security boundary. The CLIs run
with the user's full authority. Always review `git diff` after a session with
write enabled. No worker pushes to remotes by default; push, force-push, and
destructive Git operations are never authorized in current flows.

### Model Configuration
Models are defined declaratively in `backend/models_registry.py` (the universe).
Active members and chairman are persisted to `data/council_config.json` via the
UI (⚙️ Models panel) or directly via `PUT /api/council/config`. The current
default chairman is Claude (`"claude"`). `DEFAULT_MEMBERS` = `["claude", "codex",
"gemini", "deepseek"]`.

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Ranking Parse Failures**: If models don't follow format, fallback regex extracts any "Response X" patterns in order
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only available in API responses

## Future Enhancement Ideas

- **Room mode (ADR 0003):** persistent multi-agent conversations with turn-taking,
  parallel code tasks in isolated Git worktrees. Not yet implemented; blocked on
  ADR 0002 stabilization gate.
- Export conversations to markdown/PDF
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models with special handling

Already implemented:
- ✅ Configurable council/chairman via UI (⚙️ Models panel, persisted to `council_config.json`)
- ✅ Streaming responses via SSE (Stage 1 live events: thoughts, tools, results)
- ✅ Research stage (Stage 0) — optional web research before deliberation

## Testing Notes

Tests live under `tests/` and use **isolated temporary databases**: the
`temp_db` / `temp_db_raw` fixtures set `COUNCIL_HOME=<tmpdir>` and reload
backend modules so every test runs against its own files.  No real providers
or API keys are consumed.

Run:
```bash
uv run pytest tests/ -v
```

Backend import sanity check:
```bash
uv run python -c "from backend import storage, migrations, paths; print('OK')"
```

## Data Flow Summary

```
User Query
    ↓
Stage 0 (optional): Research officer gathers current web facts → research brief
    ↓
Stage 1: Parallel agent queries with live SSE → [individual responses]
    ↓
Stage 2: Anonymize → Parallel ranking queries → [evaluations + parsed rankings]
    ↓
Aggregate Rankings Calculation → [sorted by avg position]
    ↓
Stage 3: Chairman synthesis with full context (read-only)
    ↓
Return: {stage1, stage2, stage3, metadata}
    ↓
Frontend: Display with tabs + validation UI
```

The entire flow is async/parallel where possible to minimize latency.
