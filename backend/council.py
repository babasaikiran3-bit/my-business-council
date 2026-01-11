"""3-stage LLM Council orchestration with conversation context."""

from typing import List, Dict, Any, Tuple
from .groq_client import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL


def format_conversation_history(conversation_messages: List[Dict[str, Any]]) -> str:
    """
    Format conversation history for context.
    
    Args:
        conversation_messages: List of previous messages in the conversation
    
    Returns:
        Formatted conversation history string
    """
    if not conversation_messages:
        return "No previous conversation history."
    
    history_lines = []
    for msg in conversation_messages[-6:]:  # Last 6 messages for context
        if msg["role"] == "user":
            history_lines.append(f"User: {msg['content']}")
        elif msg["role"] == "assistant":
            # For assistant messages, include the final synthesized response
            if msg.get("stage3"):
                response = msg["stage3"].get("response", "")
                # Take first 200 chars to avoid too much context
                if len(response) > 200:
                    response = response[:200] + "..."
                history_lines.append(f"Assistant: {response}")
    
    return "\n".join(history_lines)


async def stage1_collect_responses(
    user_query: str,
    conversation_history: str = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.
    
    Args:
        user_query: The user's current question
        conversation_history: Previous conversation context (optional)
    
    Returns:
        List of dicts with 'model' and 'response' keys
    """
    # Build system prompt with conversation context
    system_prompt = """You are a helpful AI assistant."""
    
    if conversation_history:
        system_prompt = f"""You are a helpful AI assistant continuing a conversation.

Previous conversation:
{conversation_history}

Please continue the conversation naturally, considering the context above."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

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


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    conversation_history: str = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.
    
    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        conversation_history: Previous conversation context (optional)
    
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

    # Build the ranking prompt with conversation context
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    # Add conversation context to the ranking prompt
    context_note = ""
    if conversation_history:
        context_note = f"""\n\nIMPORTANT: This is part of an ongoing conversation. 
Here is the conversation history for context:
{conversation_history}

Consider how well each response continues the conversation naturally."""

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}
{context_note}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Consider how well each response understands and continues from the conversation context (if provided).
3. Then, at the very end of your response, provide a final ranking.

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

    messages = [
        {"role": "system", "content": "You are an evaluator tasked with ranking responses to a question."},
        {"role": "user", "content": ranking_prompt}
    ]

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
    conversation_history: str = None
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response with conversation context.
    
    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        conversation_history: Previous conversation context (optional)
    
    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response'][:500]}..." 
        if len(result['response']) > 500 else 
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking'][:500]}..." 
        if len(result['ranking']) > 500 else 
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    # Add conversation context for chairman
    context_section = ""
    if conversation_history:
        context_section = f"""
CONVERSATION HISTORY:
{conversation_history}
"""

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

{context_section}
CURRENT QUESTION: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's current question. 

IMPORTANT: Consider the conversation history (if provided) and make sure your response:
1. Naturally continues from the previous conversation
2. Acknowledges or builds upon any relevant context
3. Provides a coherent answer that fits within the ongoing dialogue
4. Does not repeat information unnecessarily

Provide a clear, well-reasoned final answer that represents the council's collective wisdom and continues the conversation naturally:"""

    messages = [
        {"role": "system", "content": "You are the Chairman synthesizing responses from multiple AI models."},
        {"role": "user", "content": chairman_prompt}
    ]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.
    """
    import re

    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.
    """
    from collections import defaultdict

    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    aggregate.sort(key=lambda x: x['average_rank'])
    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [
        {"role": "system", "content": "You generate concise titles for questions."},
        {"role": "user", "content": title_prompt}
    ]

    response = await query_model("groq/compound-mini", messages, max_tokens=30)

    if response is None:
        words = user_query.split()[:4]
        return " ".join(words) + "..."

    title = response.get('content', '').strip()
    title = title.strip('"\'')
    
    if len(title) > 50:
        title = title[:47] + "..."
    
    return title or "New Conversation"


async def run_full_council(
    user_query: str,
    conversation_messages: List[Dict[str, Any]] = None
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process with conversation context.
    
    Args:
        user_query: The user's question
        conversation_messages: Previous messages in the conversation (optional)
    
    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Format conversation history if provided
    conversation_history = None
    if conversation_messages:
        conversation_history = format_conversation_history(conversation_messages)
        print(f"[COUNCIL] Using conversation history ({len(conversation_messages)} previous messages)")

    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query, conversation_history)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, conversation_history
    )

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        conversation_history
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "had_context": conversation_history is not None
    }

    return stage1_results, stage2_results, stage3_result, metadata