"""MCP server exposing the LLM Council as a tool.

One file, two transports:
    uv run python -m backend.mcp_server              -> stdio   (Claude Desktop / Claude Code)
    MCP_TRANSPORT=streamable-http uv run python -m backend.mcp_server   -> HTTP (Railway)

A full council run is ~9 model calls in 3 sequential rounds and takes 45s+.
Progress is reported between stages because some clients only reset their
per-call timeout on notifications/progress.
"""

import os
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Literal

from mcp.server.mcpserver import Context, MCPServer

from .config import CHAIRMAN_MODEL, COUNCIL_MODELS
from .council import (
    calculate_aggregate_rankings,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
)

mcp = MCPServer(
    name="llm-council",
    version="1.0.0",
    instructions=(
        "Ask a panel of frontier models the same question, have them rank each "
        "other's answers anonymously, then return a synthesised answer plus the "
        "peer rankings. Use when a question is genuinely contested and one "
        "model's answer is not enough."
    ),
)


# Chained-call state. Stage 1 returns a council_id; later stages look the data up
# here rather than having the client pass four full answers back as arguments.
# That keeps the label->model mapping server-side, which is what makes the
# anonymous ranking in stage 2 real rather than decorative.
# ponytail: in-memory, single process, capped at 32. Lost on restart, which is
# fine while a chain completes inside one conversation. Move to pg if this ever
# runs multi-instance on Railway.
_COUNCILS: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_MAX_COUNCILS = 32


def _load(council_id: str) -> Dict[str, Any]:
    """Fetch a council session, or raise with the exact recovery step."""
    session = _COUNCILS.get(council_id)
    if session is None:
        raise ValueError(
            f"Unknown council_id {council_id!r}. It may have expired (only the "
            f"{_MAX_COUNCILS} most recent are kept, and all are lost on restart). "
            "Call council_open to start a new council."
        )
    return session


async def _progress(ctx: Context, done: float, total: float, message: str) -> None:
    """Report progress, best-effort.

    Progress is a keep-alive for slow clients, not part of the result. A client
    that does not support it - or any call made outside a live session - must
    not take the whole council run down with it.
    """
    try:
        await ctx.report_progress(done, total, message)
    except Exception:
        pass


def _consensus(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
) -> Dict[str, Any]:
    """Did the judges agree on a single best answer?

    Agreement is the null result - it means the question had a clear answer and
    the council cost 9 calls to confirm what one would have said. A split is the
    informative outcome: the models genuinely disagree, so treat the answer as
    contested.
    """
    tops = [
        label_to_model.get((r.get("parsed_ranking") or [None])[0])
        for r in stage2_results
    ]
    tops = [t for t in tops if t]

    if not tops:
        return {"verdict": "unknown", "note": "No ranking could be parsed."}
    if all(t == tops[0] for t in tops):
        return {
            "verdict": "unanimous",
            "top_model": tops[0],
            "note": "All judges picked the same best answer - the question was not contested.",
        }
    return {
        "verdict": "split",
        "note": "Judges disagreed on the best answer - treat this as genuinely contested.",
    }


@mcp.tool(
    name="ask_council",
    title="Ask the LLM Council",
)
async def ask_council(
    question: str,
    ctx: Context,
    detail: Literal["summary", "full"] = "summary",
) -> Dict[str, Any]:
    """Ask several frontier models the same question, have them rank each other's
    answers anonymously, and return a synthesised final answer.

    When to use: a question is genuinely contested, high-stakes, or open-ended and
    one model's answer is not enough. Also use when you want to know whether
    frontier models AGREE - a split verdict is a signal the question is unsettled.
    Do not use for routine factual lookups: the models will simply agree and the
    call costs ~9 model requests and 45+ seconds.

    Args:
        question: The question to put to the council. Plain text, any length.
        detail: "summary" (default) returns the synthesised answer, the consensus
            verdict and the peer ranking table. "full" additionally returns every
            council member's individual answer - much larger output.

    Returns:
        answer (the chairman's synthesis), consensus (unanimous/split/unknown with
        a note), ranking (each model with its average peer rank and vote count),
        models_responded, chairman, and - only when detail="full" - responses.
        Returns an "error" key instead if every council member failed.
    """
    await _progress(ctx, 0, 3, f"Asking {len(COUNCIL_MODELS)} council members...")
    stage1 = await stage1_collect_responses(question)
    if not stage1:
        return {
            "error": (
                "Every council member failed to respond. Check that the provider "
                "API keys in .env are valid and that the model IDs in "
                "backend/config.py are current."
            )
        }

    await _progress(ctx, 1, 3, "Collecting anonymous peer rankings...")
    stage2, label_to_model = await stage2_collect_rankings(question, stage1)
    rankings = calculate_aggregate_rankings(stage2, label_to_model)

    await _progress(ctx, 2, 3, f"{CHAIRMAN_MODEL} is synthesising...")
    stage3 = await stage3_synthesize_final(question, stage1, stage2)

    await _progress(ctx, 3, 3, "Done.")

    result: Dict[str, Any] = {
        "answer": stage3.get("response", ""),
        "chairman": stage3.get("model", CHAIRMAN_MODEL),
        "consensus": _consensus(stage2, label_to_model),
        "ranking": rankings,
        "models_responded": f"{len(stage1)}/{len(COUNCIL_MODELS)}",
    }
    if detail == "full":
        result["responses"] = stage1
    return result




@mcp.tool(name="council_open", title="Council: collect opinions (stage 1)")
async def council_open(question: str, ctx: Context) -> Dict[str, Any]:
    """Ask every council member the question independently and return all their
    answers, plus a council_id for the next stage.

    When to use: first step of a chained council run, and often sufficient on its
    own - four independent answers frequently settle a question without needing the
    peer ranking. Use ask_council instead if you want all three stages in one call.

    Args:
        question: The question to put to the council. Plain text, any length.

    Returns:
        council_id (pass to council_rank / council_close), responses (one entry per
        member with model and response), models_responded, and next_step.
        Costs one model call per member; no ranking or synthesis is performed.
    """
    await _progress(ctx, 0, 1, f"Asking {len(COUNCIL_MODELS)} council members...")
    stage1 = await stage1_collect_responses(question)
    if not stage1:
        return {
            "error": (
                "Every council member failed to respond. Check the provider API keys "
                "in .env and the model IDs in backend/config.py."
            )
        }

    council_id = str(uuid.uuid4())[:8]
    _COUNCILS[council_id] = {"question": question, "stage1": stage1}
    while len(_COUNCILS) > _MAX_COUNCILS:
        _COUNCILS.popitem(last=False)

    await _progress(ctx, 1, 1, "Opinions collected.")
    return {
        "council_id": council_id,
        "responses": stage1,
        "models_responded": f"{len(stage1)}/{len(COUNCIL_MODELS)}",
        "next_step": (
            f"Call council_rank(council_id='{council_id}') to have the members rank "
            "each other anonymously - do that when the answers disagree. If they "
            "already agree, the question was not contested and you can stop here."
        ),
    }


@mcp.tool(name="council_rank", title="Council: anonymous peer ranking (stage 2)")
async def council_rank(council_id: str, ctx: Context) -> Dict[str, Any]:
    """Have each council member rank the stage-1 answers, with authorship hidden,
    and return the aggregate ranking plus whether they agreed.

    When to use: after council_open, when the answers diverge and you need to know
    which the models themselves rate highest. Identities are anonymised server-side,
    so no member can favour its own answer.

    Args:
        council_id: The id returned by council_open.

    Returns:
        consensus (unanimous/split/unknown with a note), ranking (each model with
        average peer rank and vote count), and next_step. A "split" verdict is the
        informative one - it means the question is genuinely contested.
        Errors if council_id is unknown or expired.
    """
    session = _load(council_id)

    await _progress(ctx, 0, 1, "Collecting anonymous peer rankings...")
    stage2, label_to_model = await stage2_collect_rankings(
        session["question"], session["stage1"]
    )
    session["stage2"] = stage2
    session["label_to_model"] = label_to_model

    await _progress(ctx, 1, 1, "Rankings collected.")
    return {
        "council_id": council_id,
        "consensus": _consensus(stage2, label_to_model),
        "ranking": calculate_aggregate_rankings(stage2, label_to_model),
        "next_step": (
            f"Call council_close(council_id='{council_id}') for a synthesised final "
            "answer from the chairman."
        ),
    }


@mcp.tool(name="council_close", title="Council: chairman synthesis (stage 3)")
async def council_close(council_id: str, ctx: Context) -> Dict[str, Any]:
    """Have the chairman model read every answer and every ranking, and write one
    synthesised final answer.

    When to use: last step of a chained council run, after council_rank. Prefer this
    over synthesising the answers yourself: you are a council member, so writing the
    summary of a ranking you may have won is marking your own homework. The chairman
    is deliberately a separate model.

    Args:
        council_id: The id returned by council_open. council_rank must have been
            called first - the chairman needs the rankings.

    Returns:
        answer (the synthesis) and chairman (which model wrote it).
        Errors if council_id is unknown, or if council_rank has not been run.
    """
    session = _load(council_id)
    if "stage2" not in session:
        return {
            "error": (
                f"council_rank has not been run for council_id {council_id!r}. "
                f"Call council_rank(council_id='{council_id}') first - the chairman "
                "synthesises from the rankings, not just the raw answers."
            )
        }

    await _progress(ctx, 0, 1, f"{CHAIRMAN_MODEL} is synthesising...")
    stage3 = await stage3_synthesize_final(
        session["question"], session["stage1"], session["stage2"]
    )
    await _progress(ctx, 1, 1, "Done.")
    return {
        "answer": stage3.get("response", ""),
        "chairman": stage3.get("model", CHAIRMAN_MODEL),
    }


def main() -> None:
    """stdio by default; streamable-http when MCP_TRANSPORT says so.

    MCP_PATH carries a long random secret in production (e.g. "/mcp/<random>").
    That is obscurity, not authentication - it keeps scanners off an endpoint
    that spends real money per call, but anyone holding the URL holds the keys.
    ponytail: swap for OAuth if this is ever shared beyond one operator.
    """
    if os.getenv("MCP_TRANSPORT") == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=int(os.getenv("PORT", "8000")),
            # Leading slash is required by the router; a misconfigured env var
            # that drops it would otherwise fail at startup with a bare assert.
            streamable_http_path="/" + os.getenv("MCP_PATH", "/mcp").lstrip("/"),
            stateless_http=True,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
