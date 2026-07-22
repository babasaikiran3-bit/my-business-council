# LLM Council — Agent Architecture

Generated to accompany `.claude/agents/` and `.claude/skills/council/SKILL.md`. See `CLAUDE.md` for the full rationale.

```mermaid
flowchart TD
    U["/council question"] --> S1

    subgraph S1["Stage 1 — First Opinions (parallel, independent)"]
        opus1["council-opus (Opus)"]
        sonnet1["council-sonnet (Sonnet)"]
    end

    S1 --> S2

    subgraph S2["Stage 2 — Peer Review (anonymized A/B, parallel)"]
        opus2["council-opus reviews the *other* response"]
        sonnet2["council-sonnet reviews the *other* response"]
    end

    S2 --> S3

    subgraph S3["Stage 3 — Multi-Hat Critique (parallel, advisory only)"]
        devil["council-devils-advocate (Black Hat — risk)"]
        yellow["council-optimist (Yellow Hat — upside)"]
        feas["council-feasibility (practicality rating)"]
    end

    S1 -. "both first opinions" .-> S3

    S3 -. "NEEDS RESEARCH: flag" .-> research["council-researcher (Opus, on-demand only)"]

    S1 --> chairman
    S2 --> chairman
    S3 --> chairman
    research -.-> chairman

    chairman["council-chairman (Opus)\nStage 4 — neutral synthesis, no first opinion of its own"] --> out["Final Answer"]

    classDef opus fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a;
    classDef sonnet fill:#dcfce7,stroke:#15803d,color:#14532d;
    classDef advisory fill:#fef3c7,stroke:#b45309,color:#78350f;
    classDef chairman fill:#ede9fe,stroke:#6d28d9,color:#4c1d95;
    classDef research fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d;

    class opus1,opus2 opus;
    class sonnet1,sonnet2 sonnet;
    class devil,yellow,feas advisory;
    class chairman,out chairman;
    class research research;
```

## Roster reference

| Agent | Model | Role | Sees other members' output? |
|---|---|---|---|
| `council-opus` | Opus | Stage 1 first opinion, Stage 2 peer review | No (Stage 1), one anonymized peer response (Stage 2) |
| `council-sonnet` | Sonnet | Stage 1 first opinion, Stage 2 peer review | No (Stage 1), one anonymized peer response (Stage 2) |
| `council-devils-advocate` | Sonnet | Stage 3 — Black Hat, risk/weakness case (advisory) | Both Stage 1 answers only |
| `council-optimist` | Sonnet | Stage 3 — Yellow Hat, upside case (advisory) | Both Stage 1 answers only |
| `council-feasibility` | Sonnet | Stage 3 — practicality rating (advisory) | Both Stage 1 answers only |
| `council-researcher` | Opus | On-demand only — dispatched on `NEEDS RESEARCH:` flags | The specific flagged question only |
| `council-chairman` | Opus | Stage 4 — neutral synthesis, never gives a first opinion | Everything, in randomized order |

## Why it's shaped this way

- **Independence in Stage 1**: `council-opus` and `council-sonnet` never see each other's answer before writing their own — avoids anchoring.
- **Anonymization in Stage 2**: peer review is done on Response A/B, letter assignment randomized per run, so critique isn't colored by which model wrote which answer.
- **Advisory-only hats in Stage 3**: Devil's Advocate, Optimist, and Feasibility rate and flag but never veto — this is modeled on de Bono's Six Thinking Hats, keeping risk/upside/practicality judgments separate rather than blended into one model's single response.
- **Research is on-demand, not standing**: `council-researcher` only runs when something explicitly flags `NEEDS RESEARCH:` — it's never dispatched speculatively.
- **Chairman is a dedicated, opinion-free role**: splitting synthesis out from `council-opus` was a deliberate fix so the final answer isn't biased toward whichever model wrote the chairman prompt; inputs are assembled in randomized order so it can't anchor on read-order either.
