# CLAUDE.md - LLM Council (Claude Code native fork)

## What this is

This repo started as a clone of [karpathy/llm-council](https://github.com/karpathy/llm-council.git) — a 3-stage LLM deliberation app (first opinions → anonymized peer review → chairman synthesis) originally built as a FastAPI backend + React frontend that called multiple providers through OpenRouter.

That app has been **removed** and replaced with a Claude-Code-native equivalent: `.claude/agents/` + `.claude/skills/council/`. Run it with `/council <question>` inside Claude Code.

**Why:** the user has a Claude Pro/Max subscription but no separate Anthropic API key or OpenRouter account, and didn't want to pay for API access just to run this. Claude Code's Agent tool can pin a subagent to a specific model (`model: opus` / `model: sonnet` in a subagent's frontmatter) and run it headlessly, authenticated via the existing subscription login — no API key, no OpenRouter, no per-token billing. That's the entire mechanism this fork relies on.

## Current architecture

```
.claude/
  agents/
    council-opus.md              # Stage 1/2 member, model: opus
    council-sonnet.md            # Stage 1/2 member, model: sonnet
    council-devils-advocate.md   # Stage 3, Black Hat (risk case), model: sonnet, advisory only
    council-optimist.md          # Stage 3, Yellow Hat (upside case), model: sonnet, advisory only
    council-feasibility.md       # Stage 3, practicality rating, model: sonnet, advisory only
    council-researcher.md        # on-demand only, model: opus, dispatched on NEEDS RESEARCH: flags
    council-chairman.md          # Stage 4, neutral synthesis only, model: opus, never gives a first opinion
  skills/
    council/
      SKILL.md                   # orchestrates /council: 4 stages + research escape hatch
```

This is loosely modeled on Edward de Bono's *Six Thinking Hats* — separate members embody separate modes of judgment (facts, risk, upside, practicality) instead of one model trying to hold all of them at once, which is what produces yes-bias in the first place.

- **Stage 1 (first opinions):** `council-opus` and `council-sonnet` each answer the question independently, dispatched in parallel, no knowledge of each other.
- **Stage 2 (peer review):** responses are anonymized as Response A/B (letter assignment randomized per run) and each agent ranks/critiques the *other's* answer without knowing which model wrote it.
- **Stage 3 (multi-hat critique):** `council-devils-advocate`, `council-optimist`, and `council-feasibility` each independently react to the question and both Stage 1 answers — risk case, upside case, and a Low/Medium/High practicality rating respectively. All three are **advisory only**: they rate and flag, they never block or veto.
- **Research escape hatch:** any stage can end a response with `NEEDS RESEARCH: <question>` when it needs current/external info it doesn't have. The skill collects these and dispatches `council-researcher` before the chairman synthesizes — this agent is never run speculatively, only on demand.
- **Stage 4 (chairman):** `council-chairman` — a dedicated, opinion-free agent — synthesizes the final answer from everything above, with inputs assembled in randomized order specifically so it can't anchor on read-order or favor its own earlier take (it doesn't have one; splitting the chairman out from `council-opus` was a deliberate fix for that bias).
- Output goes straight to the terminal/chat (headings per stage). No artifact by default — only rendered as an HTML artifact if explicitly requested after the fact (see SKILL.md).

To add a further hat (e.g. a "user advocate" or a Green Hat creative-alternatives member, or a third first-opinion model like a local model once that's wired up), add a new `.claude/agents/council-<name>.md` following the existing pattern and wire it into the relevant stage in `SKILL.md` — see the Notes section there.

## Removed from upstream

Deleted entirely (recoverable via `git log` — they were committed once, then removed in the commit that added the agent/skill setup):

- `backend/` — FastAPI app: `config.py` (model list + chairman), `council.py` (the 3-stage prompt logic), `openrouter.py` (HTTP client), `storage.py`, `main.py`
- `frontend/` — React/Vite app with the Stage1/2/3 tabbed UI
- `main.py`, `start.sh`, `pyproject.toml`, `uv.lock`, `.python-version` — Python project plumbing for the above

## Reconciling future upstream pulls

This repo now lives at [MKamel1/llm-council](https://github.com/MKamel1/llm-council) (GitHub fork) as `origin` — `git push`/`git pull` with no args target it directly. `karpathy/llm-council` is wired up as `upstream` for pulling in future changes only (`git fetch upstream`), not for pushing. If upstream changes land and get pulled/merged in (e.g. via `git fetch upstream` + cherry-pick, since this fork's history has diverged structurally):

- **Prompt/logic changes to `backend/council.py`** (Stage 2 ranking format, aggregate-ranking math, chairman prompt) are the most likely thing worth porting — translate the *prompt wording and stage logic*, not the code, into `SKILL.md`'s stage instructions and the relevant agent files' system prompts.
- **New models added to `backend/config.py`'s `COUNCIL_MODELS`** — decide if it's worth adding as a new subagent here (only meaningful for models Claude Code can actually run: Anthropic models via `model:` frontmatter, or self-hosted/local models once that path exists — see below).
- **Frontend UI changes** are not applicable — there's no web UI in this fork. If the user later wants the visual tabbed view back, that's the "render as artifact" path already noted in `SKILL.md`, not a frontend rebuild.
- If upstream restructures `backend/openrouter.py` (e.g. new provider support), that's irrelevant here since this fork doesn't use OpenRouter at all.

## Future: local models / other providers

The user's stated plan is to add local models (e.g. via Ollama) or other API providers later. Tracked as [issue #2](https://github.com/MKamel1/llm-council/issues/2) — don't build until asked, that issue is the placeholder for when this conversation happens. Two integration paths noted there:

1. **Still Claude-Code-native:** if Claude Code ever supports pinning a subagent to a non-Anthropic/local model, extend the same `.claude/agents/council-<name>.md` pattern.
2. **Back to a real backend:** if local/other-provider models need to be called directly (most likely path — Claude Code subagents can only run Claude models), a lightweight script or small server would be needed alongside the skill, called out to for those specific council members while Opus/Sonnet stay on the subagent path. This would be a hybrid, not a full revival of the original OpenRouter backend.

**Also revisit then:** failure handling currently aborts the whole `/council` run on any agent failure (see `SKILL.md` → Failure Handling), on the reasoning that every agent shares one subscription today, so a failure is likely systemic. Once local models are in the mix, a single model's failure becomes a more plausible isolated event, and graceful degradation (continue with a noted gap, matching upstream's original philosophy) may be worth reconsidering.
