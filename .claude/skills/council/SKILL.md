---
name: council
description: Run a question or idea through the full LLM Council — independent first opinions, anonymized peer review, multi-hat critique (devil's advocate, optimist, feasibility), on-demand research, and neutral chairman synthesis. Use when the user invokes /council, asks for "the council's" opinion, wants an idea stress-tested from multiple angles, or wants to avoid single-model yes-bias.
---

# LLM Council

Runs `args` (the user's question or idea) through the full council process. All stages run via Agent tool calls to the subagents below — no API key, no external server, everything runs through Claude Code's own model-pinned subagents under the current subscription.

If `args` is empty, ask the user what question or idea to put to the council before doing anything else.

**This skill is deliberately heavy, always.** There's no lightweight mode and no auto-detection of "this is just a quick fact lookup" — every invocation runs the full roster, and worst case (max escalation) can trigger 25+ Agent calls. That's intentional: `/council` is reserved for genuine decisions/ideas where independent opinions, adversarial critique, and risk-gated re-deliberation actually earn their cost. For quick factual questions, ask directly instead of invoking this skill — the burden is on the caller to invoke `/council` only when it's warranted, not on the skill to guess.

## Roster

| Agent | Model | Role |
|---|---|---|
| `council-opus` | Opus | Stage 1 first opinion, Stage 2 peer review |
| `council-sonnet` | Sonnet | Stage 1 first opinion, Stage 2 peer review |
| `council-devils-advocate` | Sonnet | Stage 3 — Black Hat, risk/weakness case (advisory) |
| `council-optimist` | Sonnet | Stage 3 — Yellow Hat, upside case (advisory) |
| `council-feasibility` | Sonnet | Stage 3 — practicality rating (advisory) |
| `council-researcher` | Opus | On-demand only — dispatched when any stage flags `NEEDS RESEARCH:` |
| `council-chairman` | Opus | Stage 4 — neutral synthesis only, never gives a first opinion |

## Stage 1 — First Opinions

Dispatch the question to both `council-opus` and `council-sonnet`, single message, two parallel Agent tool calls, `run_in_background: false` for both (nothing can proceed until both return). Each gets only the raw question — no mention of the other model, no hint that this is a council.

Print both answers under `## Stage 1: First Opinions`, labeled by model name.

## Stage 2 — Peer Review

Fixed cross-review, no letter/label scheme needed: send `council-sonnet` the Opus answer (as "a fellow Council Member's response to the same question," no name attached — Council Members are already instructed never to self-identify, so there's nothing to strip), and send `council-opus` the Sonnet answer, same framing. Each reviewer only ever sees one other response, never its own — this sidesteps self-preference bias by construction, since neither model reviews its own answer. Ask each to evaluate accuracy and insight. Two parallel Agent calls, `run_in_background: false`.

Print both raw evaluations under `## Stage 2: Peer Review`, labeled by which model wrote the original answer being reviewed (for the reader's benefit only — the agents themselves never saw that label).

## Stage 3 — Multi-Hat Critique

Send `council-devils-advocate`, `council-optimist`, and `council-feasibility` the same package: the original question plus both Stage 1 answers, labeled by model this time (no need to anonymize — these three are evaluating the idea, not ranking model quality). Three parallel Agent calls, `run_in_background: false`, each blind to the other two's output so they stay independent.

Print all three under `## Stage 3: Multi-Hat Critique`, subheaded by role (Devil's Advocate / Optimist / Feasibility).

**Research escape hatch:** if any Stage 1, 2, or 3 output ends with a line starting exactly `NEEDS RESEARCH:`, collect those questions. Before dispatching anything, dedupe within this run — if two flagged questions are asking essentially the same thing, research it once and give the answer to both flaggers. Dispatch `council-researcher` — one Agent call per distinct question after deduping, in parallel if there's more than one — before moving to Stage 4.

Then loop each answer back to whichever agent(s) raised it: re-invoke that agent with its own original output plus the research brief, and ask it to revise its output in light of the answer. Use the **revised** output in everything downstream (printing, and what the Chairman sees) — not the pre-research original.

Print results under `## Research` (the brief) and update the relevant stage's printed output to the revised version. If nothing flagged it, skip this stage entirely; don't invoke the researcher speculatively.

Note: this dedupes only *within a single run*. Caching research across separate `/council` invocations (so a later run doesn't re-research something a past run already answered) is a real but separate design problem — tracked as [issue #1](https://github.com/MKamel1/llm-council/issues/1), not built yet.

## Stage 4 — Chairman Synthesis (with bounded, risk-gated escalation)

Call `council-chairman` with everything gathered so far — the original question, both first opinions (labeled by model), both peer reviews, all three hats' output, and any research briefs. No ordering scheme needed: the Chairman is required to explicitly acknowledge every input by name before writing its final answer (see `council-chairman.md`), which is what actually prevents skimming or positional underweighting — not the order things are presented in.

**Escalation loop:** track a cycle counter starting at 1. If the Chairman's response includes a Likelihood/Exposure assessment and an explicit decision to escalate (see `council-chairman.md`):

1. If the cycle counter is already 4, do not escalate regardless of the Chairman's assessment — tell it this is the final cycle and ask it to finalize with an explicit caveat instead.
2. Otherwise, run one escalation cycle: dispatch `council-researcher` for the flagged question → re-run all three Stage 3 advisors with their original context plus the research brief, asking each to revise its position or explicitly counter-argue its earlier take → re-run `council-chairman` with the updated Stage 3 output and increment the cycle counter.
3. Repeat from the top of this list with the new Chairman response.

Print the Chairman's per-input acknowledgments, then its Likelihood/Exposure reasoning and escalate/finalize decision, alongside its answer at every cycle — this is part of the deliberation, not internal bookkeeping, and the user should be able to see why a run did or didn't spend extra cycles, and whether the Chairman actually engaged with each input.

Print the final result under `## Stage 4: Final Answer`.

## Failure Handling

If any Agent call in Stage 1, 2, or 3 fails or errors, **stop the run** — don't proceed to the next stage or to Stage 4. Report to the user plainly which agent failed and why (if known), and that the council run was aborted rather than completed with a gap.

This is deliberate, not an oversight: every agent right now runs on the same underlying Claude subscription, so one failure is more likely a systemic issue (rate limit, usage cap, outage) than an isolated fluke — continuing past it risks feeding the Chairman a silent gap instead of a real signal worth investigating first. Revisit this once local models are added (see `CLAUDE.md`), where a single model's failure becomes a more plausible isolated event and graceful degradation may make more sense.

## After the run

Don't render an artifact by default — terminal output above is the deliverable. Only build an HTML artifact (tabbed view of all stages, mirroring the original web UI's stage tabs) if the user explicitly asks to see it as an artifact, or asks for a shareable view once the discussion has wound down. Load the `artifact-design` skill first when that happens.

## Notes

- This replaced the original OpenRouter-based FastAPI/React app from upstream `karpathy/llm-council`. See `CLAUDE.md` for why, and what to do if upstream changes need reconciling.
- Devil's Advocate, Optimist, and Feasibility are strictly advisory — they rate and flag, they never block or veto. Only the Chairman produces a final verdict, and it isn't bound by majority sentiment.
- To add a further hat (e.g. a "user advocate" or a Green Hat creative-alternatives member), add a new `.claude/agents/council-<name>.md` following the pattern of the Stage 3 members, then wire it into Stage 3 above.
