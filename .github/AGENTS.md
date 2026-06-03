<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# .github

## Purpose
GitHub-specific repository configuration. Currently this holds only the GitHub Actions CI pipeline (`workflows/ci.yml`), which gates every push and pull request by linting, compiling, and testing the Python backend and building the React frontend. The pipeline is intentionally credential-free: no `OPENROUTER_API_KEY` is exposed to CI, so live-API integration tests must self-skip rather than fail. This is the place to add future GitHub config (issue/PR templates, CODEOWNERS, Dependabot, additional workflows).

## Key Files
| File | Description |
| --- | --- |
| `workflows/ci.yml` | The sole CI workflow (`name: CI`). Triggers on `push` to any branch (`["**"]`) and on every `pull_request`. Defines two parallel `ubuntu-latest` jobs — see below. |

**`workflows/ci.yml` — `backend` job:** checks out (`actions/checkout@v4`), installs `uv` via `astral-sh/setup-uv@v5`, syncs deps with `uv sync --frozen --group dev`, lints with `uvx ruff check backend/ tests/ test_openrouter.py`, compiles via `uv run python -m py_compile backend/*.py test_openrouter.py`, then runs `uv run pytest -q`. `OPENROUTER_API_KEY` is deliberately absent so integration tests auto-skip.

**`workflows/ci.yml` — `frontend` job:** runs with `working-directory: frontend`, checks out, sets up Node 20 (`actions/setup-node@v4`, `cache: npm`, `cache-dependency-path: frontend/package-lock.json`), then `npm ci` and `npm run build`. Note: this job builds only — it does NOT run `npm run lint`.

## For AI Agents

### Working In This Directory
- This is the canonical record of how the repo is validated. If you change build/lint/test conventions elsewhere, the corresponding step here MUST be updated to match, or CI drifts from local reality.
- The `backend` job mirrors the verification commands in the root `CLAUDE.md`. Keep `ruff check` paths (`backend/ tests/ test_openrouter.py`) and the `py_compile` glob in sync with what actually exists; a renamed/added top-level test file or backend module must be reflected here.
- **`--frozen` is load-bearing:** `uv sync --frozen --group dev` fails if `uv.lock` is stale. After changing `pyproject.toml` deps, regenerate the lockfile locally (`uv lock`) and commit it, or CI breaks.
- **No API key by design:** never add `OPENROUTER_API_KEY` (or other live secrets) to this workflow. Tests that need a live key must skip when it is absent — do not "fix" CI by injecting the secret.
- The frontend job uses `npm ci` (not `npm install`), which requires `frontend/package-lock.json` to be present and in sync with `frontend/package.json`.
- Trigger scope is broad: `push` fires on every branch. Be aware that pushing a feature branch already runs the full pipeline (pushes + PRs can double-run on the same commit).
- YAML is whitespace-sensitive: preserve the existing 2-space indentation and the `defaults.run.working-directory: frontend` block for the frontend job.

### Testing Requirements
Reproduce CI locally before changing the workflow. From the repo root:
- Backend: `uv sync --frozen --group dev` · `uvx ruff check backend/ tests/ test_openrouter.py` · `uv run python -m py_compile backend/*.py test_openrouter.py` · `uv run pytest -q`
- Frontend: `cd frontend && npm ci && npm run build`
- To validate the workflow file itself, lint the YAML (e.g. `uvx yamllint .github/workflows/ci.yml`) or run it with `act` if available.

### Common Patterns
- Two independent, parallel jobs (`backend`, `frontend`) — keep them separate; do not merge into one job.
- Backend uses `uv` / `uvx` exclusively (bare `python`/`ruff`/`pytest` are not assumed on PATH, matching the repo's tooling convention).
- Pinned action major versions (`@v4`, `@v5`) and an explicit Node version (`"20"`) with npm caching keyed to the lockfile.

## Dependencies

### Internal
- Backend job depends on repo-root `pyproject.toml` + `uv.lock`, the `dev` dependency group, the `backend/` package, the `tests/` suite, and `test_openrouter.py`.
- Frontend job depends on `frontend/package.json`, `frontend/package-lock.json`, and the `npm run build` (Vite) script.

### External
- GitHub Actions: `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/setup-node@v4`.
- Toolchain: `uv` / `uvx` (Astral) for Python; `ruff` (lint); `pytest` (tests); Node 20 + npm (frontend build, Vite under the hood).

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
