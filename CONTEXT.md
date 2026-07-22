# LLM Council

A Claude Code-native multi-agent setup that runs a question or idea through independent opinions, anonymized peer review, and advisory critique before a neutral synthesis — designed to avoid the single-model "yes bias" of asking one LLM directly.

## Language

**Council Member**:
An agent that independently answers the original question (Stage 1) and is subject to anonymized peer review (Stage 2). Currently `council-opus` and `council-sonnet`.
_Avoid_: Panelist, participant

**Advisor**:
An agent that reacts to the question and the Council Members' answers with a specific lens (risk, upside, practicality), but never gives an independent first opinion and is never peer-reviewed itself. Purely advisory — rates and flags, never blocks or vetoes. Currently `council-devils-advocate`, `council-optimist`, `council-feasibility`.
_Avoid_: Hat, reviewer, critic (informal flavor references to Six Thinking Hats are fine in prose, but not the canonical term)

**Chairman**:
The single agent that synthesizes everything the Council and its Advisors produced into the final, binding answer. Never gives an independent first opinion. Not a Council Member or an Advisor — a distinct role.

**Researcher**:
An on-demand utility agent, dispatched only when a `NEEDS RESEARCH:` question is flagged. Produces a research brief consumed by other roles; doesn't itself hold or vote an opinion. Not a Council Member or an Advisor.

**Cross-Review**:
The fixed Stage 2 pairing where each Council Member reviews only the *other* Council Member's answer, never its own. Deliberately not randomized and not letter-anonymized — the fixed pairing already guarantees no model ever reviews itself, which is what actually matters (see ADR on self-preference bias).
_Avoid_: Peer ranking (implies N-way comparison; with two members it's a 1:1 swap)

**Escalation Cycle**:
One round of research → Stage 3 revision → Chairman re-synthesis, triggered when the Chairman flags a load-bearing gap in its synthesis. Capped at 4 cycles per `/council` run. Not automatic — gated by the Chairman's own Likelihood/Exposure risk assessment of the gap (see below); a low-stakes gap gets noted as a caveat and finalized instead of escalated.

**Likelihood/Exposure Assessment**:
The Chairman's risk-register-style gate for deciding whether an unresolved gap is worth an Escalation Cycle: Likelihood (how likely resolving it is to change the synthesis) and Exposure (how costly being wrong about it would be), each rated Low/Medium/High. Only a genuinely high-stakes combination escalates; everything else is finalized with an explicit caveat.

**Per-Input Acknowledgment**:
The Chairman's requirement to explicitly address every Stage 1/2/3/research input by name before writing its final answer, including inputs it dismisses. Replaces order-randomization as the mechanism for preventing positional bias — forces genuine engagement with each input instead of making the bias unpredictable-but-still-present.
