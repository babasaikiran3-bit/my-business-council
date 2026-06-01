"""Stage-based Parenting Roundtable orchestration."""

import re
from typing import List, Dict, Any, Tuple
from .openrouter import query_models_parallel, query_model, extract_citations
from .config import (
    COUNCIL_MODELS,
    CHAIRMAN_MODEL,
    SEARCH_MODEL,
    TRUSTED_DOMAINS,
    SEARCH_SYSTEM_PROMPT,
    STAGE1_SYSTEM_PROMPT,
    STAGE3_CHAIRMAN_PROMPT,
)


def _format_sources_list(sources: List[Dict[str, str]]) -> str:
    """Render a numbered markdown list of sources, or a placeholder if empty."""
    if not sources:
        return "(no sources were retrieved)"
    return "\n".join(
        f"{i}. {src.get('title') or src.get('url')} — {src.get('url')}"
        for i, src in enumerate(sources, start=1)
    )


# --- Deterministic safety backstop -------------------------------------------
# Safety is primarily prompt-based, but we add ONE narrow, universally-agreed
# deterministic rule as a last line of defense: any fever in a baby under 3
# months old is a medical emergency (AAP/NHS/CDC). If the structured age says
# newborn (0-3mo) and the question mentions fever, we guarantee an EMERGENCY
# callout even if the LLM forgets to lead with one. Kept intentionally narrow to
# avoid false positives.

_EMERGENCY_BLOCKQUOTE_RE = re.compile(r"^\s*>?\s*\**\s*EMERGENCY\b", re.IGNORECASE | re.MULTILINE)

NEWBORN_FEVER_EMERGENCY = (
    "> EMERGENCY: A fever in a baby under 3 months old is a medical emergency. "
    "Contact a doctor immediately or go to the nearest emergency department now — "
    "do not wait. Babies this young can become seriously ill very quickly, even "
    "when they look well."
)


def _is_newborn(user_query: str) -> bool:
    """Detect a newborn (0-3 month) child from the query/age prefix."""
    q = user_query.lower()
    return any(
        marker in q
        for marker in ("newborn", "0-3mo", "0-3 mo", "under 3 month", "under three month")
    )


def _mentions_fever(user_query: str) -> bool:
    """Detect a fever mention, including an explicit high temperature value."""
    q = user_query.lower()
    if any(k in q for k in ("fever", "febrile", "temperature", "high temp")):
        return True
    m = re.search(r"(\d{2,3}(?:\.\d)?)\s*°?\s*([cf])\b", q)
    if m:
        value = float(m.group(1))
        unit = m.group(2)
        if unit == "c" and value >= 38.0:
            return True
        if unit == "f" and value >= 100.4:
            return True
    return False


def _apply_safety_net(response_text: str, user_query: str) -> str:
    """Prepend a canonical EMERGENCY callout for the newborn-fever red flag if missing."""
    text = response_text or ""
    if _is_newborn(user_query) and _mentions_fever(user_query):
        if not _EMERGENCY_BLOCKQUOTE_RE.search(text):
            return f"{NEWBORN_FEVER_EMERGENCY}\n\n{text}"
    return text


async def stage0_research(user_query: str) -> Dict[str, Any]:
    """
    Stage 0: Build a neutral, advice-free evidence digest via web search.

    Runs a single researcher model with the Exa web search plugin restricted
    to trusted medical domains, producing the shared evidence base for all
    downstream council members.

    Args:
        user_query: The user's question

    Returns:
        Dict with 'evidence_brief' (markdown str) and 'sources' (list of
        {"url", "title"} citations)
    """
    messages = [
        {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    resp = await query_model(
        SEARCH_MODEL,
        messages,
        web_search=True,
        search_domains=TRUSTED_DOMAINS,
    )

    if resp is None:
        return {"evidence_brief": "", "sources": []}

    return {
        "evidence_brief": resp.get('content', ''),
        # Allowlist-filter so only trusted-domain URLs are ever surfaced as sources.
        "sources": extract_citations(resp.get('annotations'), allowed_domains=TRUSTED_DOMAINS),
    }


async def stage1_collect_responses(
    user_query: str,
    stage0: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Each model reasons ONLY from the Stage 0 evidence base (no web search).

    Args:
        user_query: The user's question
        stage0: The Stage 0 result dict with 'evidence_brief' and 'sources'

    Returns:
        List of dicts with 'model', 'response', and 'sources' keys
    """
    evidence_brief = stage0.get('evidence_brief', '')
    sources = stage0.get('sources', [])
    sources_list = _format_sources_list(sources)

    grounded_message = f"""Parent's question: {user_query}

EVIDENCE BASE (cite ONLY these real sources; do not invent others):

{evidence_brief}

Sources:
{sources_list}"""

    messages = [
        {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
        {"role": "user", "content": grounded_message},
    ]

    # Query all models in parallel (no web search at this stage)
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.get('content', ''),
                "sources": sources
            })

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly. Judge each response on: scientific accuracy; source quality/recency; safety & red-flag handling; age-appropriateness; clarity for a panicked parent.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    stage0: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        stage0: The Stage 0 result dict with 'evidence_brief' and 'sources'

    Returns:
        Dict with 'model', 'response', and 'sources' keys
    """
    # Consolidate sources: union of stage0 sources and each stage1 item's
    # sources, deduped by url, order-preserving.
    consolidated_sources: List[Dict[str, str]] = []
    seen_urls = set()
    for src in stage0.get('sources', []):
        url = src.get('url')
        if url and url not in seen_urls:
            seen_urls.add(url)
            consolidated_sources.append(src)
    for result in stage1_results:
        for src in result.get('sources', []):
            url = src.get('url')
            if url and url not in seen_urls:
                seen_urls.add(url)
                consolidated_sources.append(src)

    sources_text = _format_sources_list(consolidated_sources)

    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""{STAGE3_CHAIRMAN_PROMPT}

Parent's question: {user_query}

EVIDENCE BASE (from trusted medical sources):
{stage0.get('evidence_brief', '')}

STAGE 1 - Panelist Answers:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

AVAILABLE SOURCES (these are shown to the parent automatically — refer to them by name; do not paste raw URLs):
{sources_text}

Now write the final answer for the parent:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis.",
            "sources": []
        }

    # Deterministic backstop: guarantee the newborn-fever emergency callout.
    final_text = _apply_safety_net(response.get('content', ''), user_query)

    return {
        "model": CHAIRMAN_MODEL,
        "response": final_text,
        "sources": consolidated_sources
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(user_query: str) -> Tuple[Dict, List, List, Dict, Dict]:
    """
    Run the complete staged council process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage0, stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 0: Build the shared evidence base via web search
    stage0 = await stage0_research(user_query)

    # Stage 1: Collect individual responses grounded in the evidence base
    stage1_results = await stage1_collect_responses(user_query, stage0)

    # If no models responded successfully, return error (still return stage0)
    if not stage1_results:
        return stage0, [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again.",
            "sources": []
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        stage0
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    return stage0, stage1_results, stage2_results, stage3_result, metadata
