<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# tests

## Purpose
The pytest suite for the Parenting Roundtable backend. Every test targets a `backend/` module: the LLM council pipeline (mocked, never live), the deterministic safety layer, the trusted-domain grounding allowlist, the auth/identity/OAuth/quota stack, and the FastAPI HTTP surface (tenancy, CSRF, limits, health). The LLM pipeline (`run_full_council`, `query_model`, `query_models_parallel`) is always monkeypatched to deterministic dicts so the full suite runs offline with no `OPENROUTER_API_KEY`. There is no `conftest.py`; configuration lives in the root `pyproject.toml` under `[tool.pytest.ini_options]` (notably `asyncio_mode = "auto"`, `pythonpath = ["."]`, `testpaths = ["tests"]`). Live-API tests would carry the `integration` marker, but none currently do.

## Key Files
| File | Description |
| --- | --- |
| `test_council.py` | Mocked unit tests of the 4-stage pipeline in `backend/council.py`: Stage 0 dedupe/allowlist, Stage 1 grounding + graceful-degradation skips, Stage 2 + the load-bearing `FINAL RANKING:` parser (`parse_ranking_from_text`) and its regex fallbacks, `calculate_aggregate_rankings` math, Stage 3 emergency/disclaimer application, source consolidation, title generation, and the per-stage-vs-pipeline timeout budget. |
| `test_council_e2e.py` | End-to-end (mocked) `run_full_council` across the three pilot scenarios (benign toddler, newborn-fever emergency, one-model-down degradation). Uses the real client-prefixed content shape `"Child age: ... . Question: ..."` plus a typed `age_days`. |
| `test_safety.py` | The deterministic, language-aware safety layer (`backend/safety.py`): `age_band` boundaries (newborn→infant flips at exactly 90 days), Korean/English/numeric `mentions_fever` (incl. negatives like `38cm` and `88f`), typed-age `assess_emergency` triage categories (newborn_fever, breathing, seizure_unresponsive, choking_ingestion, self_harm/abuse short-circuit), and idempotent `apply_safety_net` + `KO_DISCLAIMER`. |
| `test_grounding.py` | `_hostname_in_allowlist` (`backend/openrouter.py`) against `TRUSTED_DOMAINS`: Korean authorities + subdomains allowed (kdca, mfds, amc.seoul.kr, pediatric.or.kr), consumer sites (naver blog, daum cafe) blocked, and the KR-before-international ordering precedence rule. |
| `test_accounts.py` | `backend/accounts.AccountStore`: birthdate→age math, async identity linking (merge-in-place, concurrent same-identity no-split via per-key lock), child CRUD + tenant isolation + validation, and required-consent recording. Mutating methods are `async`. |
| `test_auth.py` | `backend/auth.py` session secret + cookies: HMAC `_sign`/`_verify` and `sign_payload`/`verify_payload` tamper rejection, `_load_session_secret` fail-fast in production vs ephemeral dev fallback, and environment-driven cookie flags (SameSite=none+secure in prod, lax in dev). |
| `test_oauth.py` | `backend/oauth.py` provider module: PKCE challenge/verifier, Kakao/Naver userinfo parsers, `provider_enabled` env gating, authorize-URL construction (S256), and mocked `exchange_code`/`fetch_userinfo` over a fake `httpx.AsyncClient`. |
| `test_quota.py` | `backend/quota.DailyQuota`: per-user daily hard ceiling (over-limit blocked without counter corruption), per-user isolation, and stale-date reset to a fresh count of 1. |
| `test_storage_backend.py` | `backend/storage_backend.JsonStorageBackend`: cross-tenant read isolation, async append of user/assistant messages + title, path-traversal id rejection, 100-concurrent-append durability (asyncio.Lock), corrupted-file quarantine vs `StorageCorruptionError`, partial/short_circuit mid-pipeline saves, unicode atomic-write roundtrip, and delete. |
| `test_api.py` | HTTP layer (`backend/main.app` via FastAPI `TestClient`): anonymous-session cookie issuance (`pr_uid`), per-user conversation isolation/404, and session persistence across requests. Storage swapped via `monkeypatch`. |
| `test_api_identity.py` | HTTP layer for Phase 2 identity endpoints: `/api/auth/providers`, children CRUD + isolation + CSRF/birthdate validation, `/api/consents`, `/api/auth/me` (anonymous minimal shape), disabled-provider login 404, and the Kakao OAuth login→callback flow incl. state-mismatch rejection (with `oauth` exchange/userinfo monkeypatched). |
| `test_api_limits.py` | HTTP layer cost/abuse floor + readiness: oversized-content 422, request-too-large 413, missing-CSRF 403, auth-required 401, rate-limit 429 (+`Retry-After`), `/health` & `/ready` (503 without API key), security headers, and the message happy-path + idempotency-key replay. |

## For AI Agents

### Working In This Directory
- **`asyncio_mode = "auto"`** (set in root `pyproject.toml`): write `async def test_...` with NO `@pytest.mark.asyncio` decorator — pytest-asyncio runs them directly. Match the existing style.
- **Run from the project root, not `tests/`.** `pythonpath = ["."]` makes `from backend.x import ...` resolve; imports use the package form (`backend.council`, `backend.safety`, etc.), mirroring the backend's relative-import convention.
- **Never hit the network.** All pipeline tests monkeypatch `council.query_model` / `council.query_models_parallel` (or `main.run_full_council`) with `async def` fakes returning the `{content, reasoning_details, annotations}` dict shape. New pipeline tests must do the same — do not add live calls to the default suite (reserve those for the `integration` marker).
- **The `FINAL RANKING:` block is load-bearing.** `test_council.py` asserts the exact `FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C` format that `parse_ranking_from_text` keys on. If you touch Stage 2 prose in `council.py`, these tests guard the format — do not "fix" them to match a reformatted block.
- **Safety tests assert Korean output and TYPED age.** Emergency callouts use the Korean `> 응급:` marker and the disclaimer is `KO_DISCLAIMER`; triage is driven by `age_days` (an int), not by parsing the age label out of the query string. The newborn→infant boundary is exact at 90 days. Assertions like `.count("응급:") == 1` verify the Hangul-safe idempotency (a JS-`\b`-style regex bug previously doubled it).
- **HTTP state-changing requests need the CSRF header** `{"X-Requested-With": "parenting-roundtable"}` (the `CSRF` constant) because cookies are SameSite=None; omitting it is itself tested as a 403.
- **Isolate global state per test.** `test_api_limits.py` calls `main.limiter.reset()` (rate-limit counters are process-global) and monkeypatches `main.store`/`main.accounts`/`main.quota`/`main.REQUIRE_AUTH`/`main.DATA_DIR`/`main.OPENROUTER_API_KEY`. Use `tmp_path` for all storage so tests never touch `data/`.
- **Backend runs on port 8001** (not 8000) in production, but these tests use `TestClient(app)` and never bind a port.

### Testing Requirements
- Whole suite (offline, no API key needed): `uv run pytest tests/ -q`
- One file: `uv run pytest tests/test_safety.py -q`
- One test: `uv run pytest tests/test_council.py::test_parse_ranking_happy_path -q`
- If pytest isn't already in the env, the self-contained form is: `uv run --with pytest --with pytest-asyncio pytest tests/ -q`
- Lint (line-length 110, E501 ignored): `uvx ruff check tests/`
- `python`/`pytest`/`ruff` are NOT on PATH in this environment — always go through `uv run` / `uvx`.

### Common Patterns
- **`tmp_path` everywhere** — every store/quota/account test constructs its backend rooted at `str(tmp_path)` for full isolation.
- **`monkeypatch` for seams** — pipeline functions, `oauth.exchange_code`/`fetch_userinfo`, `oauth.provider_enabled`, env vars (`KAKAO_REST_API_KEY`, `KAKAO_REDIRECT_URI`, `NAVER_CLIENT_ID`), and `main.*` module globals are all swapped, never the real services.
- **Realistic Korean fixtures** — queries and expected strings are real Korean (`아기 열이 38.5도예요`, `낮잭 전환`, `신생아`), matching the production locale; assertions check for Korean substrings and the `> 응급:` / `KO_DISCLAIMER` markers.
- **Client-prefixed content shape** — pipeline/e2e tests pass `"Child age: {label}. Question: {q}"` plus a separate `age_days` int, mirroring what `ChatInterface.jsx` sends.
- **Graceful-degradation assertions** — a failed model returns `None` and is skipped; a failed Stage 0 yields `{"evidence_brief": "", "sources": []}`; a failed Chairman yields a fallback with `"Error"` in the response.
- Small local helpers (`_resp`, `_install_mocks`, `_setup`, `_new_conv`, `_patch_accounts`) build the canonical dict shapes — reuse them rather than re-deriving the shape.

## Dependencies

### Internal
- `backend.council`, `backend.safety`, `backend.config` (pipeline + timeout/domain constants)
- `backend.openrouter` (`_hostname_in_allowlist`, citation extraction)
- `backend.main` (FastAPI `app` and its module-level `store`/`accounts`/`quota`/`limiter`/`oauth` globals + config flags)
- `backend.storage_backend` (`JsonStorageBackend`, `StorageCorruptionError`)
- `backend.accounts` (`AccountStore`, `age_days_from_birthdate`, `REQUIRED_CONSENTS`)
- `backend.auth`, `backend.oauth`, `backend.quota`

### External
- `pytest` + `pytest-asyncio` (dev dependency group; `asyncio_mode = "auto"`)
- `fastapi.testclient.TestClient` (FastAPI/Starlette) for the HTTP-layer tests
- `httpx` (monkeypatched `AsyncClient` in the OAuth test)
- stdlib only otherwise (`asyncio`, `json`, `base64`, `hashlib`, `datetime`, `urllib.parse`)

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
