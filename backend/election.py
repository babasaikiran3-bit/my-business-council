"""Election logic for the LLM Council."""

from typing import List, Dict, Any, Optional
import asyncio
import random
from .openrouter import query_model, query_models_parallel
from .config import COUNCIL_MODELS

async def get_manifesto(model: str) -> Dict[str, str]:
    """
    Ask a model for its manifesto.
    
    Args:
        model: The model identifier
        
    Returns:
        Dict with 'model' and 'manifesto'
    """
    prompt = """You are a candidate for the Chairman of the LLM Council.
Please write a short manifesto (max 50 words) explaining why you should be elected as Chairman.
Focus on your ability to synthesize information and provide fair, balanced summaries.
Do not use any markdown formatting or bullet points. Just a single paragraph."""

    messages = [{"role": "user", "content": prompt}]
    
    response = await query_model(model, messages, max_tokens=100)
    
    manifesto = "I promise to serve well." # Fallback
    if response and response.get('content'):
        manifesto = response.get('content').strip()
        
    return {
        "model": model,
        "manifesto": manifesto
    }

async def cast_vote(model: str, manifestos: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Ask a model to vote for the best candidate.
    
    Args:
        model: The voting model
        manifestos: List of manifestos from all candidates
        
    Returns:
        Dict with 'voter' and 'vote_for' (model name)
    """
    # Filter out self (models shouldn't vote for themselves ideally, but for simplicity we allow it or just prompt them)
    # Actually, let's allow them to vote for anyone including themselves, or prompt them to be objective.
    
    candidates_text = "\n\n".join([
        f"Candidate: {m['model']}\nManifesto: {m['manifesto']}"
        for m in manifestos
    ])
    
    prompt = f"""You are a member of the LLM Council. It is time to elect a Chairman.
Here are the candidates and their manifestos:

{candidates_text}

Please vote for the candidate you think would make the best Chairman.
You must return ONLY the exact model identifier of your chosen candidate.
Do not add any explanation or punctuation."""

    messages = [{"role": "user", "content": prompt}]
    
    response = await query_model(model, messages, max_tokens=20)
    
    vote_for = None
    if response and response.get('content'):
        vote_content = response.get('content').strip()
        # Simple heuristic to find the voted model in the response
        for m in manifestos:
            if m['model'] in vote_content:
                vote_for = m['model']
                break
        
        # If exact match failed, try to see if the response IS the model name
        if not vote_for:
             # Check if response is close to a model name or just pick random if failed to parse
             pass

    # Fallback: random vote if parsing failed
    if not vote_for:
        vote_for = random.choice([m['model'] for m in manifestos])

    return {
        "voter": model,
        "vote_for": vote_for
    }

async def run_election() -> Dict[str, Any]:
    """
    Run the full election process.
    
    Returns:
        Dict with election results (manifestos, votes, winner)
    """
    # 1. Get manifestos from all models in parallel
    manifesto_tasks = [get_manifesto(model) for model in COUNCIL_MODELS]
    manifestos = await asyncio.gather(*manifesto_tasks)
    
    # 2. Cast votes in parallel
    vote_tasks = [cast_vote(model, manifestos) for model in COUNCIL_MODELS]
    votes = await asyncio.gather(*vote_tasks)
    
    # 3. Count votes
    vote_counts = {}
    for vote in votes:
        voted_for = vote['vote_for']
        vote_counts[voted_for] = vote_counts.get(voted_for, 0) + 1
        
    # 4. Determine winner
    # Find max votes
    max_votes = 0
    winners = []
    
    for model, count in vote_counts.items():
        if count > max_votes:
            max_votes = count
            winners = [model]
        elif count == max_votes:
            winners.append(model)
            
    # Resolve tie randomly
    winner = random.choice(winners)
    
    return {
        "manifestos": manifestos,
        "votes": votes,
        "vote_counts": vote_counts,
        "winner": winner
    }
