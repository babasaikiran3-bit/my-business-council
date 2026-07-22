# /council stays deliberately heavy — no lightweight-question auto-detection

`/council` always runs the full roster (up to 25+ Agent calls in the worst case with max escalation), with no lightweight path for simple factual questions. We considered having the skill detect "this is just a quick fact lookup" and skip Stage 3 / escalation in that case, but rejected it: the burden is on the caller to invoke `/council` only when a genuine decision/idea justifies the cost, not on the skill to guess intent. Quick factual questions should be asked directly instead of through this skill.
