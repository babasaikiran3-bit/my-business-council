"""3-stage collaborative LLM orchestration with optional internal deliberation."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .config import (
    CHAIRMAN_MODEL,
    COUNCIL_LITE_MODE,
    COUNCIL_MODELS,
    JUDGE_MODELS,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_DOCUMENTS_DIR,
    RAG_ENABLED,
    RAG_TOP_K,
    TITLE_MODEL,
)
from .providers.factory import get_provider
from .rag import retrieve_context


provider = get_provider()

TRIVIAL_PROMPT_PATTERN = re.compile(
    r"^(hi|hello|hey|yo|hola|sup|thanks|thank you|ok|okay|good morning|good afternoon|good evening)[!.?\s]*$",
    re.IGNORECASE,
)

CRITIQUE_FIELDS = [
    "strengths",
    "weaknesses",
    "missing_information",
    "unsupported_claims",
    "suggested_improvements",
]


def _response_label(index: int) -> str:
    """Generate stable anonymous labels for candidate responses."""
    return f"Response {chr(65 + index)}"


def is_trivial_prompt(user_query: str) -> bool:
    """Return True for short greeting-like prompts that should skip deliberation."""
    normalized = re.sub(r"\s+", " ", user_query.strip())
    if not normalized:
        return True
    if TRIVIAL_PROMPT_PATTERN.match(normalized):
        return True
    if len(normalized.split()) <= 2 and normalized.lower() in {
        "hello there",
        "hi there",
        "howdy",
    }:
        return True
    return False


def _extract_json_payload(text: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from model output."""
    candidates = [text.strip()]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates.extend(fenced)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(text[first_brace:last_brace + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def _normalize_string_list(value: Any) -> List[str]:
    """Normalize any JSON-like list field into a string list."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def parse_structured_critiques(
    critique_text: str,
    valid_labels: List[str],
) -> List[Dict[str, Any]]:
    """Parse structured critique JSON from evaluator output."""
    payload = _extract_json_payload(critique_text)
    if payload is None:
        return []

    critiques = payload.get("critiques", [])
    if not isinstance(critiques, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in critiques:
        if not isinstance(item, dict):
            continue
        label = str(item.get("response_label", "")).strip()
        if label not in valid_labels:
            continue

        entry = {"response_label": label}
        for field in CRITIQUE_FIELDS:
            entry[field] = _normalize_string_list(item.get(field))
        normalized.append(entry)

    return normalized


def _aggregate_structured_critiques(
    stage2_results: List[Dict[str, Any]],
    valid_labels: List[str],
) -> List[Dict[str, Any]]:
    """Aggregate all evaluator critiques into response-scoped structured summaries."""
    aggregate: Dict[str, Dict[str, List[str]]] = {
        label: {field: [] for field in CRITIQUE_FIELDS}
        for label in valid_labels
    }

    for evaluator in stage2_results:
        for critique in evaluator.get("structured_critiques", []):
            label = critique.get("response_label")
            if label not in aggregate:
                continue
            for field in CRITIQUE_FIELDS:
                for item in critique.get(field, []):
                    if item and item not in aggregate[label][field]:
                        aggregate[label][field].append(item)

    return [
        {
            "response_label": label,
            **aggregate[label],
        }
        for label in valid_labels
    ]


def _select_best_existing_response(stage1_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the strongest available direct response fallback."""
    if not stage1_results:
        return None

    chairman_candidate = next(
        (
            result
            for result in stage1_results
            if result.get("model") == CHAIRMAN_MODEL and result.get("response", "").strip()
        ),
        None,
    )
    if chairman_candidate is not None:
        return chairman_candidate

    non_empty = [
        result for result in stage1_results if result.get("response", "").strip()
    ]
    if not non_empty:
        return None
    return max(non_empty, key=lambda item: len(item.get("response", "").strip()))


async def stage1_collect_responses(user_query: str) -> List[Dict[str, Any]]:
    """Stage 1: collect candidate responses from all council models."""
    messages = [{"role": "user", "content": user_query}]
    responses = await provider.query_models_parallel(COUNCIL_MODELS, messages)

    stage1_results = []
    for model, response in responses.items():
        if response is not None:
            stage1_results.append(
                {
                    "model": model,
                    "response": response.get("content", ""),
                    "usage": response.get("usage"),
                    "latency_ms": response.get("latency_ms"),
                }
            )
    return stage1_results


async def _stage2_collect_critiques_structured(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Original stage 2: structured JSON peer critiques over anonymous responses."""
    labels = [_response_label(i) for i in range(len(stage1_results))]
    label_to_model = {
        label: result["model"]
        for label, result in zip(labels, stage1_results)
    }
    responses_text = "\n\n".join(
        [
            f"{label}:\n{result['response']}"
            for label, result in zip(labels, stage1_results)
        ]
    )

    critique_prompt = f"""You are reviewing anonymous candidate answers to a user question.

Question:
{user_query}

Candidate responses:
{responses_text}

Return ONLY valid JSON (no markdown, no prose) using this schema:
{{
  "critiques": [
    {{
      "response_label": "Response A",
      "strengths": ["..."],
      "weaknesses": ["..."],
      "missing_information": ["..."],
      "unsupported_claims": ["..."],
      "suggested_improvements": ["..."]
    }}
  ]
}}

Requirements:
- Include one critique entry for every listed response label.
- Keep each bullet short and concrete.
- If no unsupported claims are present, return an empty list for unsupported_claims.
- Do not include model names, votes, or rankings."""

    messages = [{"role": "user", "content": critique_prompt}]
    responses = await provider.query_models_parallel(JUDGE_MODELS, messages)

    stage2_results: List[Dict[str, Any]] = []
    for model, response in responses.items():
        if response is None:
            continue
        critique_text = response.get("content", "")
        stage2_results.append(
            {
                "model": model,
                "critique": critique_text,
                "usage": response.get("usage"),
                "latency_ms": response.get("latency_ms"),
                "structured_critiques": parse_structured_critiques(
                    critique_text, labels
                ),
            }
        )

    return stage2_results, label_to_model


async def _stage2_collect_critiques_lite(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Lite stage 2: short plain-text critiques, no JSON schema.

    Small local models are unreliable at multi-field JSON output — when they
    fail the schema the structured path silently drops their critique. This
    trades structure for reliability and speed, which matters more on
    limited local hardware.
    """
    labels = [_response_label(i) for i in range(len(stage1_results))]
    label_to_model = {
        label: result["model"] for label, result in zip(labels, stage1_results)
    }
    responses_text = "\n\n".join(
        f"{label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    )

    critique_prompt = f"""Question: {user_query}

Candidate answers:
{responses_text}

In 3-5 short bullet points total, note the biggest problems across these
answers: wrong facts, missing information, or unclear parts. Do not restate
the answers. Do not use JSON. Plain bullet points only, nothing else."""

    messages = [{"role": "user", "content": critique_prompt}]
    responses = await provider.query_models_parallel(JUDGE_MODELS, messages)

    stage2_results: List[Dict[str, Any]] = []
    for model, response in responses.items():
        if response is None:
            continue
        stage2_results.append(
            {
                "model": model,
                "critique": response.get("content", ""),
                "usage": response.get("usage"),
                "latency_ms": response.get("latency_ms"),
                "structured_critiques": [],
            }
        )

    return stage2_results, label_to_model


async def stage2_collect_critiques(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Stage 2: collect peer critiques over anonymous responses.

    Dispatches to the plain-text ("lite") path or the structured JSON path
    based on COUNCIL_LITE_MODE.
    """
    if COUNCIL_LITE_MODE:
        return await _stage2_collect_critiques_lite(user_query, stage1_results)
    return await _stage2_collect_critiques_structured(user_query, stage1_results)


async def generate_direct_response(user_query: str) -> Dict[str, Any]:
    """Direct response path for trivial prompts."""
    direct_prompt = (
        "Answer the user directly. Keep it concise, helpful, and natural.\n\n"
        f"User message: {user_query}"
    )
    response = await provider.query_model(
        CHAIRMAN_MODEL,
        [{"role": "user", "content": direct_prompt}],
    )
    if response is not None and response.get("content", "").strip():
        return {"model": CHAIRMAN_MODEL, "response": response.get("content", "")}

    stage1_results = await stage1_collect_responses(user_query)
    fallback = _select_best_existing_response(stage1_results)
    if fallback is not None:
        return {
            "model": fallback.get("model", CHAIRMAN_MODEL),
            "response": fallback.get("response", ""),
        }
    return {"model": CHAIRMAN_MODEL, "response": "Hello! How can I help you today?"}


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Stage 3: synthesize final answer from anonymous responses + peer critiques."""
    labels = [_response_label(i) for i in range(len(stage1_results))]
    anonymous_responses = [
        {
            "response_label": label,
            "response": result["response"],
        }
        for label, result in zip(labels, stage1_results)
    ]

    if COUNCIL_LITE_MODE:
        critique_notes = "\n\n".join(
            r.get("critique", "").strip()
            for r in stage2_results
            if r.get("critique", "").strip()
        ) or "No specific issues were flagged."

        chairman_prompt = f"""Question: {user_query}

Draft answers:
{json.dumps(anonymous_responses, indent=2)}

Notes on problems with the drafts:
{critique_notes}

Write ONE final answer to the question above. Use the best parts of the
drafts, fix anything the notes flagged, and leave out anything you're not
sure is correct. Output only the final answer — nothing about drafts,
notes, or process."""
    else:
        aggregated_critiques = _aggregate_structured_critiques(stage2_results, labels)
        chairman_prompt = f"""You are producing the final answer for the user.

Original user question:
{user_query}

Anonymous candidate responses (JSON):
{json.dumps(anonymous_responses, indent=2)}

Structured peer critiques (JSON):
{json.dumps(aggregated_critiques, indent=2)}

Rules:
- Write only the final answer to the user.
- Do not mention internal process, deliberation, critique, ranking, model names, labels, council, or chairman.
- Do not mention "Response A/B/C" or any anonymized label.
- Resolve unsupported claims by removing them or clearly qualifying uncertainty.
- Merge the strongest ideas and fill missing information where possible."""

    response = await provider.query_model(
        CHAIRMAN_MODEL,
        [{"role": "user", "content": chairman_prompt}],
    )

    if response is not None and response.get("content", "").strip():
        return {
            "model": CHAIRMAN_MODEL,
            "response": response.get("content", ""),
            "usage": response.get("usage"),
            "latency_ms": response.get("latency_ms"),
        }

    fallback = _select_best_existing_response(stage1_results)
    if fallback is not None:
        return {
            "model": fallback.get("model", CHAIRMAN_MODEL),
            "response": fallback.get("response", ""),
        }
    return {
        "model": CHAIRMAN_MODEL,
        "response": "I’m sorry, I couldn’t generate a complete answer right now.",
    }


async def generate_conversation_title(user_query: str) -> str:
    """Generate a short title for a conversation based on first user message."""
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    response = await provider.query_model(TITLE_MODEL, messages, timeout=30.0)
    if response is None:
        return "New Conversation"

    title = response.get("content", "New Conversation").strip().strip('"\'')
    if len(title) > 50:
        title = f"{title[:47]}..."
    return title


async def run_full_council(
    user_query: str,
    developer_mode: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """Run collaborative response pipeline with hidden internal deliberation by default."""
    metadata: Dict[str, Any] = {
        "developer_mode": developer_mode,
        "review_skipped": False,
        "pipeline": "collaborative-critique",
        "lite_mode": COUNCIL_LITE_MODE,
        "provider": provider.name,
        "models": {
            "council": COUNCIL_MODELS,
            "judge": JUDGE_MODELS,
            "chairman": CHAIRMAN_MODEL,
        },
    }
    effective_query = user_query
    if RAG_ENABLED:
        context, retrievals = retrieve_context(
            user_query,
            RAG_DOCUMENTS_DIR,
            RAG_TOP_K,
            RAG_CHUNK_SIZE,
            RAG_CHUNK_OVERLAP,
        )
        metadata["rag"] = {
            "enabled": True,
            "top_k": RAG_TOP_K,
            "results": retrievals,
        }
        if context:
            effective_query = (
                f"{user_query}\n\nUse the following retrieved sources when relevant. "
                "Cite sources as [Source N] and do not invent citations:\n"
                f"{context}"
            )
    else:
        metadata["rag"] = {"enabled": False, "results": []}

    if is_trivial_prompt(user_query):
        stage3_result = await generate_direct_response(effective_query)
        metadata["review_skipped"] = True
        metadata["skip_reason"] = "trivial_prompt"
        return [], [], stage3_result, metadata

    stage1_results = await stage1_collect_responses(effective_query)
    metadata["errors"] = []
    failed_stage1 = [model for model in COUNCIL_MODELS if model not in {
        result["model"] for result in stage1_results
    }]
    if failed_stage1:
        metadata["errors"].append({"stage": "stage1", "models": failed_stage1})
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again.",
        }, metadata

    stage2_results, label_to_model = await stage2_collect_critiques(
        effective_query, stage1_results
    )
    failed_stage2 = [model for model in JUDGE_MODELS if model not in {
        result["model"] for result in stage2_results
    }]
    if failed_stage2:
        metadata["errors"].append({"stage": "stage2", "models": failed_stage2})
    stage3_result = await stage3_synthesize_final(
        effective_query,
        stage1_results,
        stage2_results,
    )

    if developer_mode:
        metadata["label_to_model"] = label_to_model
        metadata["structured_summary"] = _aggregate_structured_critiques(
            stage2_results,
            list(label_to_model.keys()),
        )
        return stage1_results, stage2_results, stage3_result, metadata

    return [], [], stage3_result, metadata