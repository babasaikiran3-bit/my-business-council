---
name: council
description: Convene a panel of frontier models on a hard question, have them rank each other anonymously, and return a synthesised answer. Use when the user says "ask the council", "convene the council", "get a second opinion", "what do other models think", or when a question is genuinely contested, high-stakes, or open-ended and one model's answer is not enough. NOT for factual lookups - the models will simply agree and it costs 9 model calls.
---

# Council

Four frontier models answer independently, rank each other with authorship hidden,
and a fifth synthesises. Runs over the `llm-council` MCP server.

## When NOT to use it

Do not convene the council for a factual lookup, a definition, or anything with one
settled answer. The members will agree, and agreement is the null result: nine model
calls to confirm what one would have told you. Say so and answer directly instead.

Convene it when the question is genuinely contested, the stakes are high, or the
answer depends on judgement rather than fact.

## The chain

Call these in order. Each returns a `next_step` naming the following call.

1. **`council_open(question)`** — every member answers independently.
   Returns `council_id` and all responses.
   **Stop here and show the user the answers.** If the members clearly agree, say
   so and stop: the question was not contested, and stages 2-3 add cost, not insight.

2. **`council_rank(council_id)`** — members rank each other's answers, anonymised.
   Returns `consensus` (unanimous / split) and the aggregate ranking.
   Only run this when the stage-1 answers actually diverge.

3. **`council_close(council_id)`** — the chairman writes the final synthesis.

`ask_council(question)` does all three in one call. Prefer the chain: it stays inside
client timeouts, and it lets the user stop early.

## Do not synthesise the answers yourself

You are a council member. Writing the summary of a ranking you may have won is
marking your own homework. Use `council_close` — the chairman is deliberately a
different model. If the user explicitly asks for *your* view as well, give it
separately and label it as yours, after the chairman's synthesis.

## Reading the result

- **`split`** is the informative verdict. The models genuinely disagree, so the
  question is unsettled — present the disagreement, do not paper over it.
- **`unanimous`** means the question had a clear answer. Say that plainly rather
  than implying the council did hard work.
- Always report `models_responded`. If it is below 4/4, a provider failed and the
  ranking rests on fewer opinions than it appears to.

## Cost

Each full run is roughly nine model calls across four vendors and takes 45+ seconds.
Tell the user before convening if they did not explicitly ask for it.

## Compliance

Council output is generic AI commentary. It is not credit advice, not personal
advice, and carries no client circumstances or lender comparison. Never present it
to a client, reuse it in marketing, or treat model consensus as verification -
the members share training data, so they share blind spots. Four models agreeing
is correlated error, not independent confirmation.
