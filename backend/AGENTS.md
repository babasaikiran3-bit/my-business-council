<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# backend

## Purpose
The FastAPI backend and LLM-council pipeline for Parenting Roundtable, a science-based pediatric advisor for Korean parents. The core is a 4-stage council (`council.py`): a single searcher model grounds the answer with Exa web search restricted to a trusted-domain allowlist (Stage 0), three council models reason only from that shared evidence (Stage 1), they peer-rank each other's answers anonymized (Stage 2), and a Chairman synthesizes one safety-first Korean answer (Stage 3). A deterministic, LLM-independent safety layer (`safety.py`) drives a pre-pipeline emergency triage and guarantees the newborn-fever EMERGENCY callout. The directory has since grown a full SaaS spine: anonymous + OAuth (Kakao/Naver) sessions, per-user accounts with child profiles and PIPA consents, per-user tenant-isolated JSON storage, daily quotas, structured JSON logging, and a production security floor (CORS validation, CSRF header, HSTS, cookie hardening). Run as `python -m backend.main` from the project root (relative imports); the server listens on port 8001.

## Key Files
| File | Description |
| --- | --- |
| `__init__.py` | Package marker (`"""Parenting Roundtable backend package."""`). |
| `config.py` | Env-driven config: model IDs (`SEARCH_MODEL` gpt-5.1, `COUNCIL_MODELS`, `CHAIRMAN_MODEL`), `TRUSTED_DOMAINS` (Korean authorities first, then international), prompt constants (`SEARCH_SYSTEM_PROMPT`, `STAGE1_SYSTEM_PROMPT`, `STAGE3_CHAIRMAN_PROMPT`), CORS/CSRF/quota/timeout knobs, and `validate_runtime_config()` (fails fast in production). |
| `openrouter.py` | OpenRouter HTTP client: `query_model` (single async call; `web_search` adds the explicit Exa `plugins` block with `include_domains`), `query_models_parallel` (fan-out via `asyncio.gather`), `extract_citations` (annotations → deduped `{url,title}`, allowlist-filtered via `_hostname_in_allowlist`). Returns `None` on any failure (graceful degradation). |
| `council.py` | The 4-stage orchestrator: `stage0_research`, `stage1_collect_responses`, `stage2_collect_rankings`, `stage3_synthesize_final`, `run_full_council` (returns the 5-tuple `stage0, stage1, stage2, stage3, metadata`). Also `parse_ranking_from_text`, `calculate_aggregate_rankings`, `generate_conversation_title`, and `_timed_stage` (per-stage `asyncio.wait_for` cap). |
| `safety.py` | Deterministic, bilingual (KR/EN) pediatric safety spine, independent of any LLM. `assess_emergency(age_days, query)` → fast pre-pipeline red-flag triage (newborn+fever, breathing, seizure, choking/ingestion, self-harm, abuse); `apply_safety_net(text, age_days, query)` guarantees the newborn-fever `> 응급:` callout and appends the Korean disclaimer. Age is a typed `age_days`, never parsed from prose. |
| `storage_backend.py` | Tenant-isolated conversation storage behind an operations-shaped `StorageBackend` ABC. `JsonStorageBackend` partitions files as `{DATA_DIR}/{user_id}/{conversation_id}.json`; atomic write (temp+fsync+`os.replace`), per-key `asyncio.Lock` (`KeyedLocks`), advisory `flock`, corruption quarantine. Exports module-level `store` (selected by `STORAGE_BACKEND`, default `json`). |
| `accounts.py` | Per-user account store (`AccountStore`, module-level `accounts`): display name, linked OAuth providers, child profiles, and itemized PIPA consents. `link_identity` merges an OAuth identity into the caller's existing anon `user_id` in place (identity-keyed lock). `age_days_from_birthdate` converts a child's birthdate to typed age (KST). |
| `auth.py` | Anonymous/device session identity via an HMAC-signed cookie (`pr_uid`, stdlib only). `get_current_user` FastAPI dependency mints an anon `user_id` on first request; `set_session_cookie`/`clear_session_cookie`, `sign_payload`/`verify_payload` (OAuth state cookie), env-aware cookie flags. `_load_session_secret` fails fast on an insecure prod secret. |
| `oauth.py` | Custom OAuth flow for Kakao (primary, PKCE) and Naver (state-only). `PROVIDERS` registry, `provider_enabled` (env-gated), `build_authorize_url`, `exchange_code`, `fetch_userinfo` (normalized to `{provider_user_id, display_name}`). Each provider 404s its login until credentials are configured. |
| `quota.py` | Per-user daily message quota (`DailyQuota`, module-level `quota`). `check_and_increment(user_id)` is the disk-backed hard ceiling on paid LLM spend; JSON counter under `{DATA_DIR}/quotas/`, resets on KST date rollover, reuses the storage atomic-write + lock primitives. |
| `logging_config.py` | Stdlib structured logging: `JsonFormatter` emits one JSON line per log to stdout; `trace_id_var` ContextVar correlates all lines within a request; `configure_logging()` installs it on the root logger. |
| `main.py` | FastAPI app (`title="Parenting Roundtable API"`, port 8001). Conversation CRUD, OAuth login/callback, session/profile/consent endpoints, and the council pipeline (non-streaming `POST .../message` + SSE `.../message/stream`). Holds rate limiting (slowapi), CSRF + security-header middleware, size cap, idempotency replay, emergency short-circuit, and partial-persistence on failure/disconnect. |

## For AI Agents

### Working In This Directory
- **Run from the project root**, not from `backend/`. Modules use relative imports (`from .config import ...`); launch with `python -m backend.main` (or `uv run python -m backend.main`). Port is **8001** (8000 is taken by another app).
- **Stage 2 `FINAL RANKING:` format is load-bearing.** The prompt block in `stage2_collect_rankings` (the `FINAL RANKING:` header + `N. Response X` numbered lines) is parsed by `parse_ranking_from_text` (with regex fallbacks). Enrich the *criteria* prose if needed, but never alter the format block or the `Response A/B/C` labeling.
- **Age is typed, never parsed from prose.** The safety layer takes `age_days: Optional[int]`. The request supplies `age_days` directly or a `child_profile_id` whose birthdate is converted server-side in `_resolve_age_days`. Do not reintroduce prompt-string age parsing — that contract was a blocker in the consensus review.
- **`safety.py` is intentionally conservative and bilingual.** Korean detection comes first. Note the Hangul regex gotcha: `\b` never fires after Hangul in Python/JS, so `_EMERGENCY_BLOCKQUOTE_RE` matches a trailing separator instead (keeps `apply_safety_net` idempotent — do not "fix" it back to `\b`). `_FEVER_TERMS` deliberately excludes bare `열`/`체온` to avoid false substring hits.
- **Citations are deterministic and allowlist-filtered.** Real `annotations` → `extract_citations(..., allowed_domains=TRUSTED_DOMAINS)`. The Chairman is told to cite by name (no raw URLs). Subdomains are matched (`_hostname_in_allowlist`), so e.g. `health.kdca.go.kr` is covered by `kdca.go.kr`.
- **Graceful degradation everywhere.** A failed model returns `None` and is skipped; Stage 0 failure yields an empty evidence base. Never surface `str(exception)` to clients — use `GENERIC_ERROR_KO` / `INCOMPLETE_KO`. The pipeline persists a partial (`short_circuit=True`) on timeout/disconnect.
- **Storage is tenant-partitioned and id-validated.** Every path is built from the authenticated `user_id`; `_SAFE_ID_RE` blocks traversal. Mutations are async and serialized by a per-conversation `asyncio.Lock`; the app **must** run single-worker with `DATA_DIR` on a persistent disk. Reuse `KeyedLocks`, `_atomic_write_json`, `_read_json_or_quarantine` for any new disk-backed store (quota/accounts already do).
- **Idempotency + quota ordering.** `idempotency_key` replays the stored answer without re-running paid calls; quota is reserved *before* the pipeline and intentionally **not** refunded on failure (prevents retry-storm amplification). Keep that ordering.
- **Production security floor.** In production (`ENVIRONMENT=production`): `validate_runtime_config()` + `_validate_frontend_url()` fail-fast on bad CORS/FRONTEND_URL, cookies become `Secure; SameSite=None`, HSTS is set, `SESSION_SECRET` is mandatory, and `REQUIRE_AUTH_FOR_MESSAGES` defaults on. State-changing endpoints require the `x-requested-with: parenting-roundtable` CSRF header (`require_csrf`).

### Testing Requirements
From the project root:
- Compile: `uv run python -m py_compile backend/*.py`
- Lint: `uvx ruff check backend/`
- Import smoke: `uv run python -c "from backend import main, council, openrouter, config, storage_backend, safety, accounts, auth, oauth, quota, logging_config"`
- OpenRouter smoke (needs `OPENROUTER_API_KEY`): `uv run python test_openrouter.py`
- Unit tests (if present at repo root, e.g. `test_auth.py`, `test_safety.py`): `uv run python -m pytest`
- Safety spot-check: a newborn (`age_days < 90`) + fever query MUST surface the `> 응급:` banner with trusted-domain sources; a benign query ("toddler nap transition") must NOT fear-monger yet still cite sources.

### Common Patterns
- **Module-level singletons** selected/built at import time: `store`, `accounts`, `quota` (each a small store class instance). Import the instance, not the class.
- **Async stores, sync reads.** Mutating store methods are `async` (lock held across read→mutate→write via `asyncio.to_thread` for the file write); single-atomic reads stay sync.
- **`extra=` structured logging.** Pass fields via `logger.info("msg", extra={...})`; `JsonFormatter` merges non-reserved keys into the JSON line. Never f-string secrets into messages.
- **Env-gated optional features.** OAuth providers, storage backend, and the prod security floor are all driven by env vars with safe local-dev defaults, so the app runs with zero external config.
- **5-tuple council contract.** `run_full_council` returns `(stage0, stage1, stage2, stage3, metadata)`; `metadata` (`label_to_model`, `aggregate_rankings`) is ephemeral (API-only, never persisted). Assistant messages persist `stage0..stage3` only.

## Dependencies

### Internal
- `config.py` is imported by nearly every module (models, prompts, domains, env knobs, timeouts).
- `council.py` depends on `openrouter.py`, `safety.py`, `config.py`.
- `accounts.py`, `quota.py` reuse storage primitives from `storage_backend.py` (`KeyedLocks`, `_atomic_write_json`, `_read_json_or_quarantine`, `_is_safe_id`, `StorageCorruptionError`).
- `main.py` wires everything together: `auth`, `oauth`, `accounts`, `council`, `safety`, `quota`, `storage_backend.store`, `logging_config`.

### External
- `fastapi` + `pydantic` — app, dependencies, request validation.
- `httpx` — async HTTP to OpenRouter and OAuth providers.
- `slowapi` — per-minute rate limiting (in-memory; daily `quota` is the durable ceiling).
- `python-dotenv` — `.env` loading in `config.py`.
- `uvicorn` — ASGI server (`python -m backend.main`).
- Stdlib only for crypto/identity/logging (`hmac`, `hashlib`, `secrets`, `contextvars`, `json`, `fcntl`).

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
