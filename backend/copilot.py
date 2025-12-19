"""3-stage Eternal Copilot orchestration."""

import logging
from typing import List, Dict, Any, Tuple, Callable, Optional

from .llm import get_default_provider, LLMResponse
from .config import COPILOT_MODELS, CHAIRMAN_MODEL, PROMPT_IMPROVER_MODEL
from .prompts import get_prompt, format_prompt

logger = logging.getLogger(__name__)


def _get_provider():
    """Get the default LLM provider."""
    return get_default_provider()


def get_copilot_models() -> List[str]:
    """Return the list of copilot models."""
    return COPILOT_MODELS.copy()


async def improve_user_prompt(original_prompt: str) -> str:
    """
    Use an LLM to improve the user's prompt.

    Args:
        original_prompt: The user's original prompt

    Returns:
        The improved prompt text
    """
    system_prompt = get_prompt("prompt_improver")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": original_prompt}
    ]

    provider = _get_provider()
    response = await provider.query(PROMPT_IMPROVER_MODEL, messages)
    return response.content if response and response.content else original_prompt


async def stage1_collect_responses(user_query: str) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all copilot models.

    Args:
        user_query: The user's question

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = [{"role": "user", "content": user_query}]

    # Query all models in parallel
    provider = _get_provider()
    responses = await provider.query_parallel(COPILOT_MODELS, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None and response.success:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.content or ''
            })

    return stage1_results


async def stage1_collect_responses_with_progress(
    user_query: str,
    on_model_complete: Optional[Callable] = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses with progress callbacks.

    Args:
        user_query: The user's question
        on_model_complete: Async callback(model, response_content, success, elapsed_ms) called when each model completes

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = [{"role": "user", "content": user_query}]
    stage1_results = []

    async def handle_model_complete(model: str, response: Optional[LLMResponse], success: bool, elapsed_ms: int):
        if success and response and response.success:
            content = response.content or ''
            stage1_results.append({
                "model": model,
                "response": content
            })
            if on_model_complete:
                await on_model_complete(model, content, True, elapsed_ms)
        else:
            if on_model_complete:
                await on_model_complete(model, None, False, elapsed_ms)

    # Query all models in parallel with progress
    provider = _get_provider()
    await provider.query_parallel_with_progress(COPILOT_MODELS, messages, handle_model_complete)

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

    ranking_prompt = format_prompt(
        "stage2_ranking",
        user_query=user_query,
        responses_text=responses_text
    )

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all copilot models in parallel
    provider = _get_provider()
    responses = await provider.query_parallel(COPILOT_MODELS, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None and response.success:
            full_text = response.content or ''
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


def _truncate_response(response: str, max_chars: int = 12000) -> str:
    """
    Truncate a response to a maximum character count, preserving complete sentences.

    Args:
        response: The response text to truncate
        max_chars: Maximum number of characters to keep (default ~3000 tokens)

    Returns:
        Truncated response with ellipsis if truncated
    """
    if len(response) <= max_chars:
        return response

    # Try to find the last complete sentence within the limit
    truncated = response[:max_chars]

    # Look for sentence endings (., !, ?) followed by space or end
    last_sentence_end = -1
    for i in range(len(truncated) - 1, max(0, len(truncated) - 500), -1):
        if truncated[i] in '.!?' and (i + 1 >= len(truncated) or truncated[i + 1].isspace()):
            last_sentence_end = i + 1
            break

    if last_sentence_end > max_chars // 2:  # Only use if we keep at least half
        return truncated[:last_sentence_end] + "\n\n[Response truncated for context limits...]"

    return truncated + "...\n\n[Response truncated for context limits...]"


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Maximum characters per response to avoid context overflow
    # ~3000 tokens per response * 4 models = ~12000 tokens for Stage 1
    # This keeps total prompt under ~20000 tokens which is safe for most models
    MAX_RESPONSE_CHARS = 12000

    # Build comprehensive context for chairman with truncation
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {_truncate_response(result['response'], MAX_RESPONSE_CHARS)}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = format_prompt(
        "stage3_chairman",
        user_query=user_query,
        stage1_text=stage1_text,
        stage2_text=stage2_text
    )

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    logger.info(f"[STAGE3] Querying chairman model: {CHAIRMAN_MODEL}")
    logger.info(f"[STAGE3] Chairman prompt size: {len(chairman_prompt)} chars (~{len(chairman_prompt) // 4} tokens)")
    provider = _get_provider()
    response = await provider.query(CHAIRMAN_MODEL, messages)
    logger.info(f"[STAGE3] Chairman response received: {response}")

    if response is None:
        # Fallback if chairman fails
        logger.warning(f"[STAGE3] Chairman model returned None, using fallback")
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    content = response.content or ''
    if not content:
        logger.warning(f"[STAGE3] Chairman response content is empty. Full response: {response}")

    return {
        "model": CHAIRMAN_MODEL,
        "response": content
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
    title_prompt = format_prompt("title_generation", user_query=user_query)

    messages = [{"role": "user", "content": title_prompt}]

    # Use grok-4.1-fast for title generation (fast response times)
    provider = _get_provider()
    response = await provider.query("x-ai/grok-4.1-fast", messages, timeout=30.0)

    if response is None or not response.success:
        # Fallback to a generic title
        return "New Conversation"

    title = (response.content or 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_copilot(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage copilot process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
        metadata includes label_to_model, aggregate_rankings, and timing info
    """
    import time

    # Stage 1: Collect individual responses
    stage1_start = time.time()
    stage1_results = await stage1_collect_responses(user_query)
    stage1_duration_ms = int((time.time() - stage1_start) * 1000)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {"stage1_duration_ms": stage1_duration_ms}

    # Stage 2: Collect rankings
    stage2_start = time.time()
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)
    stage2_duration_ms = int((time.time() - stage2_start) * 1000)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_start = time.time()
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )
    stage3_duration_ms = int((time.time() - stage3_start) * 1000)

    # Prepare metadata with timing
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "stage1_duration_ms": stage1_duration_ms,
        "stage2_duration_ms": stage2_duration_ms,
        "stage3_duration_ms": stage3_duration_ms,
    }

    return stage1_results, stage2_results, stage3_result, metadata
