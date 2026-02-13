"""3-stage LLM Council orchestration."""

from .openrouter import query_models_parallel, query_model, query_model_stream # explicitly import query_model_stream
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL
from typing import List, Dict, Any, Tuple


async def stage1_collect_responses(
    user_query: str, 
    history: List[Dict[str, str]] = [],
    context: str = ""
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question
        history: Previous conversation history
        context: RAG context string

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    # Construct message content with context
    content = user_query
    if context:
        content = f"Reference Documents:\n{context}\n\nQuestion: {user_query}"

    # Combine history with new user query
    messages = history + [{"role": "user", "content": content}]

    # Query all models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results






async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    history: List[Dict[str, str]] = [],
    context: str = ""
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        history: Previous conversation history
        context: RAG context string

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    # Format history for context if present
    history_text = ""
    if history:
        history_text = "\n\nConversation Context:\n"
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"
        history_text += "\n"

    # Format rag context
    rag_text = ""
    if context:
        rag_text = f"\n\nReference Documents:\n{context}\n"

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question.

{rag_text}
{history_text}Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    try:
        response = await query_model(CHAIRMAN_MODEL, messages)
    except Exception as e:
        print(f"Error querying chairman model: {e}")
        response = None

    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "The Chairman model is currently unavailable or encountered an error. Please refer to the council member responses above."
        }


    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


async def stage3_synthesize_final_stream(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    history: List[Dict[str, str]] = [],
    context: str = ""
):
    """
    Stage 3: Chairman synthesizes final response (streaming).
    
    Yields:
        Chunks of the response text
    """
    from .openrouter import query_model_stream
    
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    # Format history for context if present
    history_text = ""
    if history:
        history_text = "\n\nConversation Context:\n"
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"
        history_text += "\n"

    # Format rag context
    rag_text = ""
    if context:
        rag_text = f"\n\nReference Documents:\n{context}\n"

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question.

{rag_text}
{history_text}Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Stream the chairman model
    full_response = ""
    try:
        async for chunk in query_model_stream(CHAIRMAN_MODEL, messages):
            full_response += chunk
            yield chunk
    except Exception as e:
        print(f"Error streaming chairman model: {e}")
        error_msg = f"\n\n[System: Chairman model failed. Verdict skipped.]"
        yield error_msg
        
    return


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

    # Use nvidia/nemotron-3-nano-30b-a3b:free for title generation (free and fast)
    response = await query_model(COUNCIL_MODELS[0], messages, timeout=30.0)

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


async def run_full_council(
    user_query: str, 
    history: List[Dict[str, str]] = [],
    context: str = ""
) -> Tuple[List, Dict]:
    """
    Run the 2-stage council process (Stage 1 -> Stage 3).

    Args:
        user_query: The user's question
        history: Previous conversation history
        context: RAG context string

    Returns:
        Tuple of (stage1_results, stage3_result)
    """
    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query, history, context)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }

    # Stage 3: Synthesize final answer (Skipped Stage 2)
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        history,
        context
    )

    return stage1_results, stage3_result
