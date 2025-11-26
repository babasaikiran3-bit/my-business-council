"""Background job to update estimated costs with actual costs from OpenRouter."""

import asyncio
import time
from typing import Dict, Any

from .openrouter import fetch_actual_cost
from .storage import get_conversation, save_conversation


async def _fetch_all_actual_costs(generation_ids: Dict[str, str]) -> Dict[str, float]:
    """Fetch all actual costs from OpenRouter concurrently."""
    actual_costs = {}
    
    async def fetch_one(key: str, gen_id: str):
        if gen_id:
            cost = await fetch_actual_cost(gen_id)
            if cost > 0:
                actual_costs[key] = cost
    
    await asyncio.gather(*[fetch_one(k, v) for k, v in generation_ids.items()])
    return actual_costs


def update_conversation_costs_sync(conversation_id: str, generation_ids: Dict[str, str]):
    """
    Synchronous wrapper to update conversation with actual costs.
    Called from RQ worker (sync context).
    
    Args:
        conversation_id: ID of the conversation to update
        generation_ids: Dict mapping stage+model to generation_id
    """
    # Wait a bit for OpenRouter to calculate costs
    time.sleep(3)
    
    # Run async cost fetching
    actual_costs = asyncio.run(_fetch_all_actual_costs(generation_ids))
    
    if not actual_costs:
        print(f"⚠️ No actual costs available for conversation {conversation_id}")
        return
    
    # Load conversation
    conversation = get_conversation(conversation_id)
    if not conversation:
        return
    
    # Update costs in the last assistant message
    messages = conversation.get('messages', [])
    if not messages or messages[-1]['role'] != 'assistant':
        return
    
    assistant_msg = messages[-1]
    total_updated_cost = 0.0
    
    # Update stage1 costs
    if 'stage1' in assistant_msg:
        for resp in assistant_msg['stage1']:
            key = f"stage1_{resp['model']}"
            if key in actual_costs:
                resp['cost'] = actual_costs[key]
                resp['cost_status'] = 'actual'
                total_updated_cost += actual_costs[key]
            elif resp.get('cost', 0) > 0:
                total_updated_cost += resp['cost']
    
    # Update stage2 costs
    if 'stage2' in assistant_msg:
        for rank in assistant_msg['stage2']:
            key = f"stage2_{rank['model']}"
            if key in actual_costs:
                rank['cost'] = actual_costs[key]
                rank['cost_status'] = 'actual'
                total_updated_cost += actual_costs[key]
            elif rank.get('cost', 0) > 0:
                total_updated_cost += rank['cost']
    
    # Update stage3 cost
    if 'stage3' in assistant_msg:
        key = f"stage3_{assistant_msg['stage3']['model']}"
        if key in actual_costs:
            assistant_msg['stage3']['cost'] = actual_costs[key]
            assistant_msg['stage3']['cost_status'] = 'actual'
            total_updated_cost += actual_costs[key]
        elif assistant_msg['stage3'].get('cost', 0) > 0:
            total_updated_cost += assistant_msg['stage3']['cost']
    
    # Update stage_costs in metadata
    if 'metadata' in assistant_msg and 'stage_costs' in assistant_msg['metadata']:
        stage_costs = assistant_msg['metadata']['stage_costs']
        has_actual = any(k in actual_costs for k in actual_costs)
        stage_costs['status'] = 'actual' if has_actual else 'estimated'
        
        # Recalculate stage totals
        stage1_total = sum(r.get('cost', 0) for r in assistant_msg.get('stage1', []))
        stage2_total = sum(r.get('cost', 0) for r in assistant_msg.get('stage2', []))
        stage3_cost = assistant_msg.get('stage3', {}).get('cost', 0)
        
        stage_costs['stage1'] = stage1_total
        stage_costs['stage2'] = stage2_total
        stage_costs['stage3'] = stage3_cost
        stage_costs['total'] = stage1_total + stage2_total + stage3_cost
    
    # Update conversation total_cost
    if total_updated_cost > 0:
        conversation['total_cost'] = total_updated_cost
    
    # Save updated conversation
    save_conversation(conversation)
    print(f"✅ Updated conversation {conversation_id} with actual costs: ${total_updated_cost:.5f}")
