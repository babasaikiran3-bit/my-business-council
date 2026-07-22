---
name: council
description: "Run a question or idea through the full LLM Council — independent first opinions, anonymized peer review, multi-hat critique (devil's advocate, optimist, feasibility), on-demand research, and neutral chairman synthesis. Use when the user invokes /council, asks for 'the council's' opinion, wants an idea stress-tested from multiple angles, or wants to avoid single-model yes-bias."
argument-hint: "<your question or idea>"
---

# LLM Council

Runs the user's question or idea through a full multi-stage council process. All stages run via subagent invocations — no external API key, everything runs through GitHub Copilot's model-pinned subagents.

If the input is empty, ask the user what question or idea to put to the council before doing anything else.

**This skill is deliberately heavy, always.** There's no lightweight mode — every invocation runs the full roster. `/council` is reserved for genuine decisions and ideas where independent opinions, adversarial critique, and risk-gated re-deliberation actually earn their cost. For quick factual questions, ask directly instead.

## Roster

| Agent                     | Role                                                               |
| ------------------------- | ------------------------------------------------------------------ |
| `council-opus`            | Stage 1 first opinion, Stage 2 peer review                         |
| `council-sonnet`          | Stage 1 first opinion, Stage 2 peer review                         |
| `council-devils-advocate` | Stage 3 — Black Hat, risk/weakness case (advisory)                 |
| `council-optimist`        | Stage 3 — Yellow Hat, upside case (advisory)                       |
| `council-feasibility`     | Stage 3 — practicality rating (advisory)                           |
| `council-status-quo`      | Stage 3 — Status Quo Defender, cost-of-change case (advisory)      |
| `council-researcher`      | On-demand only — dispatched when any stage flags `NEEDS RESEARCH:` |
| `council-chairman`        | Stage 4 — neutral synthesis, never gives a first opinion           |

## Stage 1 — First Opinions

**Label convention:** `council-opus` is always "Council Member A" and `council-sonnet` is always "Council Member B" for this run. These labels are for your orchestration bookkeeping only — never disclose actual agent or model names to any agent in any stage.

Dispatch the question to both `council-opus` and `council-sonnet` via separate subagent invocations. Each gets only the raw question — no mention of the other model, no hint that this is a council.

Collect both responses before proceeding to Stage 2.

Print both answers under `## Stage 1: First Opinions`, labeled by agent name (Opus / Sonnet).

## Stage 2 — Peer Review

Fixed cross-review: send `council-sonnet` the Opus answer (framed as "a fellow Council Member's response to the same question," no name attached), and send `council-opus` the Sonnet answer with the same framing. Ask each to evaluate accuracy and insight. Each reviewer only ever sees one other response, never its own — this sidesteps self-preference bias by construction.

Invoke both as separate subagent calls. Collect both before proceeding to Stage 3.

Print both raw evaluations under `## Stage 2: Peer Review`, labeled by which model wrote the original answer being reviewed (this label is for user-visible output only — when passing Stage 2 content to any downstream agent, use the A/B labels, not model names).

## Stage 3 — Multi-Hat Critique

Send `council-devils-advocate`, `council-optimist`, `council-feasibility`, and `council-status-quo` the same package: the original question, both Stage 1 answers labeled as "Council Member A" and "Council Member B" (using the assignment from the start of this run), and both Stage 2 peer reviews using the same A/B labels. **Never include actual agent or model names in any prompt passed to these advisors.** Each is invoked separately so they stay independent.

Collect all four responses.

Print all four under `## Stage 3: Multi-Hat Critique`, subheaded by role (Devil's Advocate / Optimist / Feasibility / Status Quo).

**Research escape hatch:** If any Stage 1, 2, or 3 output ends with a line starting exactly `NEEDS RESEARCH:`, collect those questions. Before dispatching anything, dedupe within this run — if two flagged questions are essentially the same, research it once and give the answer to both flaggers. Dispatch `council-researcher` (one invocation per distinct question after deduping) before moving to Stage 4.

Then loop each answer back to whichever agent(s) raised it: re-invoke that agent with its own original output plus the research brief, and ask it to revise its output in light of the answer. Use the **revised** output in everything downstream (printing, and what the Chairman sees).

Print results under `## Research` (the brief) and update the relevant stage's printed output to the revised version. If nothing flagged `NEEDS RESEARCH:`, skip this entirely.

## Stage 4 — Chairman Synthesis (with bounded, risk-gated escalation)

Invoke `council-chairman` with everything gathered so far: the original question, both first opinions (labeled as "Council Member A" and "Council Member B"), both peer reviews (using the same A/B labels — no model names), all four hats' output (labeled by role only: Devil's Advocate, Optimist, Feasibility, Status Quo), and any research briefs. **Model names must not appear anywhere in the Chairman's context.**

**Escalation loop:** track a cycle counter starting at 1. If the Chairman's response includes a Likelihood/Exposure assessment and an explicit decision to escalate:

1. If the cycle counter is already 4, do not escalate — tell the chairman this is the final cycle and ask it to finalize with an explicit caveat instead.
2. Otherwise, run one escalation cycle: dispatch `council-researcher` for the flagged question → re-run all four Stage 3 advisors (`council-devils-advocate`, `council-optimist`, `council-feasibility`, `council-status-quo`) with their original context plus the research brief, asking each to revise its position or explicitly counter-argue its earlier take → re-run `council-chairman` with the updated Stage 3 output and increment the cycle counter.
3. Repeat from the top of this list with the new Chairman response.

Print the Chairman's per-input acknowledgments, then its Likelihood/Exposure reasoning and escalate/finalize decision, alongside its answer at every cycle — this is part of the deliberation, not internal bookkeeping.

Print the final result under `## Stage 4: Final Answer`.

## Failure Handling

If any subagent invocation in Stage 1, 2, or 3 fails or errors, **stop the run** — don't proceed to the next stage or to Stage 4. Report to the user which agent failed and why (if known), and that the council run was aborted rather than completed with a silent gap.

## After the Run

Terminal/chat output is the deliverable. Do not render an artifact by default. Only build an HTML artifact (tabbed view of all stages) if the user explicitly asks for a shareable view after the run completes.

## Notes

- Devil's Advocate, Optimist, Feasibility, and Status Quo are strictly advisory — they rate and flag, they never block or veto. Only the Chairman produces a final verdict.
- To add a further hat (e.g. a "user advocate"), add a new `.github/agents/council-<name>.agent.md` following the pattern of the Stage 3 members, then wire it into Stage 3 above.
- This is a VS Code GitHub Copilot port of the Claude Code-native setup at https://github.com/MKamel1/llm-council. The architecture mirrors the original: 3-stage deliberation + research escape hatch + risk-gated chairman escalation.
