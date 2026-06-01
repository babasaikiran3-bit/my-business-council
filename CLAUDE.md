# CLAUDE.md - Technical Notes for Parenting Roundtable

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

**Parenting Roundtable** is a science-based pediatric/parenting advisor. It answers a parent's question (plus the child's age) by first gathering trusted medical evidence, then having a panel of LLMs reason from that shared evidence, peer-rank each other, and finally a Chairman synthesizes one careful-but-decisive answer.

The two defining ideas:
1. **Stage 0 grounding** — a dedicated web-search agent runs *first*, restricted to a strict allowlist of trusted medical domains. Its real citations become the canonical **Sources**; the council reasons only from that evidence (it does not browse). This stops models from "citing from memory" (stale/fabricated health links).
2. **Anonymized peer review** (Stage 2) — models rank each other's answers without knowing the author, preventing favoritism.

This was originally a generic "LLM Council"; it was rebranded and extended into a health-advice product. Safety is primarily **prompt-based**, with one deterministic backstop (see below) — it is not a certified medical device.

## Architecture

### Data flow (4 stages)

```
User Query (+ child age, prepended client-side as "Child age: {label}. Question: {q}")
   ↓
Stage 0 — stage0_research(): 1 searcher model · Exa web search · TRUSTED_DOMAINS only
   → { evidence_brief (neutral, advice-free), sources: [{url,title}] (deduped, allowlist-filtered) }
   ↓
Stage 1 — stage1_collect_responses(query, stage0): 3 council models, grounded in stage0, NO web search
   → [ {model, response, sources} ]   (each cites only the provided real sources)
   ↓
Stage 2 — stage2_collect_rankings(): anonymized A/B/C peer ranking (enriched criteria; FINAL RANKING: format UNCHANGED)
   ↓
calculate_aggregate_rankings() → sorted-by-avg-position
   ↓
Stage 3 — stage3_synthesize_final(query, stage1, stage2, stage0): Chairman, safety-first + consolidated Sources
   → { model, response, sources }   ( _apply_safety_net() guarantees newborn-fever EMERGENCY callout )
   ↓
Return { stage0, stage1, stage2, stage3, metadata }
```

The flow is async/parallel where possible (Stage 0 and Stage 3 are single calls; Stages 1 & 2 fan out via `asyncio.gather`).

### Backend Structure (`backend/`)

**`config.py`**
- `SEARCH_MODEL` — the Stage 0 researcher (default `openai/gpt-5.1`; Perplexity Sonar is an alternative).
- `COUNCIL_MODELS` — the 3 grounded panelists (gpt-5.1 is the searcher, so it's not in the council).
- `CHAIRMAN_MODEL` — synthesizes the final answer (default Gemini). Overlap with the council is acceptable.
- `TRUSTED_DOMAINS` — allowlist for Stage 0 web search (AAP, healthychildren.org, WHO, CDC, NHS, Cochrane, PubMed/NCBI, Mayo, NIH, AAFP).
- Prompt constants: `SEARCH_SYSTEM_PROMPT` (neutral, advice-free digest), `STAGE1_SYSTEM_PROMPT` (age-aware, cite-only-provided-sources, lead with red flags), `STAGE3_CHAIRMAN_PROMPT` (safety-first, decisive, benign-reassurance, cite-by-name-no-raw-URLs). Stage 2 criteria stay inline in `council.py`.
- Uses `OPENROUTER_API_KEY` from `.env`. Backend runs on **port 8001** (NOT 8000 — user had another app on 8000).

**`openrouter.py`**
- `query_model(model, messages, timeout=120, web_search=False, search_domains=None, max_results=5)` — single async query. When `web_search`, adds the explicit `plugins:[{id:"web", engine:"exa", max_results, search_prompt, include_domains}]` block. (Use the explicit `plugins` param, **NOT** the `:online` suffix, which would override the chosen model.) Returns `{content, reasoning_details, annotations}`; `None` on failure (graceful degradation).
- `query_models_parallel(models, messages, **kwargs)` — fan-out via `asyncio.gather`; `**kwargs` forwarded to each `query_model`.
- `extract_citations(annotations, allowed_domains=None)` — pulls `annotations[].url_citation` into deduped `[{url,title}]`, order-preserving, title→url fallback. When `allowed_domains` is given, drops any URL whose hostname is not within the allowlist (defense-in-depth — see `_hostname_in_allowlist`).
- OpenRouter annotation schema (verified against live docs): `choices[0].message.annotations[]`, each `{type:"url_citation", url_citation:{url, title, content, start_index, end_index}}`.

**`council.py`** — The Core Logic
- `stage0_research(query)` — single `query_model(SEARCH_MODEL, [system, user], web_search=True, search_domains=TRUSTED_DOMAINS)`. Returns `{evidence_brief, sources}` with sources allowlist-filtered. Returns `{evidence_brief:"", sources:[]}` if the searcher fails.
- `stage1_collect_responses(query, stage0)` — injects the evidence brief + numbered source list into the user message; prepends `STAGE1_SYSTEM_PROMPT`; `web_search=False`. Attaches `stage0['sources']` to each result item.
- `stage2_collect_rankings(query, stage1)` — anonymizes as "Response A/B/C", builds `label_to_model`, enriched evaluation criteria (accuracy → source quality → safety/red-flags → age-appropriateness → clarity). **The `FINAL RANKING:` block is verbatim** — `parse_ranking_from_text()` depends on it. Do not change it.
- `stage3_synthesize_final(query, stage1, stage2, stage0)` — consolidates stage0 + stage1 sources (deduped by url), feeds the Chairman, then runs `_apply_safety_net()` on the output. Returns `{model, response, sources}`.
- **Deterministic safety backstop**: `_apply_safety_net(text, query)` prepends a canonical `> EMERGENCY:` blockquote when `_is_newborn(query)` AND `_mentions_fever(query)` and no EMERGENCY callout already exists. Intentionally narrow (newborn 0–3mo + fever is the one universally-agreed pediatric red flag) to avoid false positives. Helpers: `_is_newborn`, `_mentions_fever` (keyword + explicit ≥38C/100.4F temperature regex), `_EMERGENCY_BLOCKQUOTE_RE`, `NEWBORN_FEVER_EMERGENCY`.
- `parse_ranking_from_text()` / `calculate_aggregate_rankings()` — unchanged; now operate over 3 responses.
- `run_full_council(query)` — runs Stage 0 first, threads it through, returns the 5-tuple `(stage0, stage1, stage2, stage3, metadata)`.

**`storage.py`**
- JSON storage in `data/conversations/`. Assistant messages now contain `{role, stage0, stage1, stage2, stage3}` (`stage0` persists; sources nest inside the stage dicts).
- `add_assistant_message(id, stage0, stage1, stage2, stage3)` — note the new leading `stage0` positional arg.
- Metadata (`label_to_model`, `aggregate_rankings`) is still **ephemeral** — returned via API, not persisted.

**`main.py`**
- FastAPI app (`title="Parenting Roundtable API"`), CORS for localhost:5173 / 3000.
- Streaming endpoint emits SSE `stage0_start` / `stage0_complete` (data = `{evidence_brief, sources}`) **before** stage1; otherwise the event shape is unchanged. Non-streaming `POST /api/conversations/{id}/message` includes top-level `stage0`.
- Both paths unpack the 5-tuple and pass `stage0` to `add_assistant_message`.

### Frontend Structure (`frontend/src/`)

**`App.jsx`** — orchestration. Optimistic assistant message carries `stage0` + `loading.stage0`; SSE reducer handles `stage0_start`/`stage0_complete` (before stage1). Metadata is UI-only (not persisted).

**`components/ChatInterface.jsx`** — always-visible safety disclaimer banner; child-age `<select>` (Newborn 0–3mo / Infant 3–12mo / Toddler 1–3yr / Older) above the textarea; composes `Child age: {label}. Question: {q}` on submit. Renders Stage0 first. Single-turn input (form only when `messages.length === 0`). Enter sends, Shift+Enter newline.

**`components/Stage0.jsx`** (+ css) — collapsible "Sources consulted · Evidence base" panel; renders the evidence brief (ReactMarkdown) + consulted source links. Rendered first in the assistant block.

**`components/Stage1.jsx`** — tab view of panelist answers + per-model source chips.

**`components/Stage2.jsx`** — tab view of RAW evaluation text; de-anonymization is CLIENT-SIDE for display (models received anonymous labels); shows "Extracted Ranking" for validation + aggregate rankings.

**`components/Stage3.jsx`** (+ css) — final answer. Extracts any `> EMERGENCY:` line via `extractEmergency()` and pins it as a high-contrast red banner at the **top** of the answer (deterministic, above-the-fold). In-body blockquotes are styled neutral so red stays meaningful. Renders a deterministic **Sources** section (green theme) from `finalResponse.sources`.

**`components/markdownComponents.jsx`** — `makeSafeMarkdownComponents(sources)` returns a ReactMarkdown `components` map whose link renderer keeps a link clickable **only** if its href exactly matches a verified source URL; everything else renders as plain `.blocked-link` text. Applied to Stage 0 / 1 / 3 bodies so a model-hallucinated URL is structurally impossible to click.

**Styling (`*.css`)** — light theme; primary `#4a90e2`; Stage 3 green; emergency red `#c0392b`. Global `.markdown-content` (12px padding) + `.blocked-link` in `index.css`.

## Key Design Decisions

### Citations are deterministic, not model-typed
The user-facing Sources lists are rendered from the real `annotations`-derived citations, allowlist-filtered server-side. The Chairman is told to cite by *name* (no raw URLs). Even so, model-authored markdown links are neutralized client-side unless they match a verified source — belt and suspenders against fabricated health links.

### Safety is layered
- Prompt-level: Stage 0 is advice-free; Stage 1 leads with red flags and is age-aware; Chairman leads with `> EMERGENCY:` when warranted and reassures plainly for benign cases.
- Deterministic backstop: `_apply_safety_net()` guarantees the newborn-fever EMERGENCY callout regardless of model behavior.
- Rendering: deterministic top-pinned emergency banner; trusted-domain-only source links.
- Honest limitation: the disclaimer states this is prompt-based safety, not a certified device.

### Stage 2 format is load-bearing
`parse_ranking_from_text()` keys on the `FINAL RANKING:` header + numbered `N. Response X` lines (with regex fallbacks). Enrich the *criteria* prose, never the format block.

### Error Handling Philosophy
Graceful degradation: a failed model returns `None` and is skipped; the request never fails on a single model. Stage 0 failing yields an empty evidence base (council still answers, just less grounded).

## Important Implementation Details

- **Relative imports**: backend modules use `from .config import ...`. Run as `python -m backend.main` (or `uv run python -m backend.main`) from the project root.
- **Tooling note**: `python` / `ruff` are not on PATH in this environment; use `uv run python ...`, `uvx ruff check ...`.
- **Ports**: backend 8001, frontend 5173. Update both `backend/main.py` and `frontend/src/api.js` if changing.
- **Markdown rendering**: wrap ReactMarkdown in `<div className="markdown-content">`. For model-authored text, also pass `components={makeSafeMarkdownComponents(sources)}`.
- **Model config**: hardcoded in `backend/config.py`.

## Common Gotchas

1. **Module import errors** — run from project root, not `backend/`.
2. **CORS** — frontend origin must match the `main.py` CORS list.
3. **Ranking parse failures** — fallback regex extracts any `Response X` in order; don't touch the `FINAL RANKING:` block.
4. **Missing metadata** — `label_to_model` / `aggregate_rankings` are ephemeral (API only).
5. **`add_assistant_message` signature** — `stage0` is now the first stage arg; both `main.py` call sites pass it positionally.
6. **Safety net scope** — `_apply_safety_net` only fires for newborn + fever by design; broadening it risks false positives.

## Testing / Verification

- `test_openrouter.py` — async smoke test (`uv run python test_openrouter.py`). Guards on `OPENROUTER_API_KEY`, calls the Stage 0 searcher on a sample fever question, prints content, raw `annotations`, and `extract_citations()` output.
- Backend: `uv run python -m py_compile backend/*.py test_openrouter.py`; `uvx ruff check backend/ test_openrouter.py`; `uv run python -c "from backend import main, council, openrouter, config, storage"`.
- Frontend: `cd frontend && npm run build`.
- Safety spot-checks: *"My 2-month-old has a 38.1°C fever at 2am"* (age = Newborn) MUST surface the ER emergency banner with real trusted-domain sources; a benign query ("toddler nap transition") must NOT fear-monger yet still cite sources.

## Future Enhancement Ideas

- Per-model "cited subset" of sources (currently every Stage 1 item carries the full Stage 0 list).
- Configurable council/chairman/domains via UI instead of config file.
- Persist a partial/error assistant message when a stage raises mid-stream.
- Token-level streaming within a stage (currently per-stage).
- Broader (but still high-precision) structured red-flag detection passed from the age selector as a real field rather than parsed from prose.
