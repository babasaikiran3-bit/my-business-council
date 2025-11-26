"""Background worker for processing LLM Council jobs."""

import asyncio
from typing import Dict, Any
from . import jobs, storage
from .council import run_full_council_with_cancel_check, JobCancelledException as CouncilCancelledException
from .cost_updater import update_conversation_costs_sync


class JobCancelledException(Exception):
    """Raised when a job is cancelled by user."""
    pass


def check_job_cancelled(job_id: str) -> bool:
    """Check if job has been cancelled."""
    job = jobs.get_job(job_id)
    if job and job.get('status') == 'failed' and job.get('error') == 'Cancelled by user':
        return True
    return False


def process_council_job(job_id: str, conversation_id: str, user_query: str) -> Dict[str, Any]:
    """
    Process a council job in the background.
    
    This function is called by RQ worker. It runs the full 3-stage council process
    and updates the job status accordingly.

    Args:
        job_id: Job identifier
        conversation_id: Conversation identifier
        user_query: User's question

    Returns:
        Result dict with stage1, stage2, stage3 data
    """
    try:
        # Check if already cancelled before starting
        if check_job_cancelled(job_id):
            print(f"⚠️ Job {job_id} was cancelled before processing started")
            raise JobCancelledException("Job cancelled by user")
        
        # Update job status to processing
        jobs.update_job_status(job_id, "processing")

        # Create cancel check function for council
        def cancel_check():
            return check_job_cancelled(job_id)

        # Run the full council process with cancel check
        stage1_results, stage2_results, stage3_result, metadata, total_cost = asyncio.run(
            run_full_council_with_cancel_check(user_query, cancel_check)
        )

        # Final check before saving results
        if check_job_cancelled(job_id):
            print(f"⚠️ Job {job_id} was cancelled after processing")
            raise JobCancelledException("Job cancelled by user")

        # Prepare result
        result = {
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata,
            "cost": total_cost
        }

        # Update job with result
        jobs.update_job_result(job_id, result)

        # Save to conversation storage with metadata
        storage.add_assistant_message(
            conversation_id,
            stage1_results,
            stage2_results,
            stage3_result,
            metadata
        )
        
        # Update conversation cost
        storage.add_cost_to_conversation(conversation_id, total_cost)
        
        # Fetch and update actual costs from OpenRouter (sync call)
        generation_ids = metadata.get('generation_ids', {})
        if generation_ids:
            try:
                update_conversation_costs_sync(conversation_id, generation_ids)
            except Exception as e:
                print(f"⚠️ Failed to update actual costs: {e}")

        return result

    except (JobCancelledException, CouncilCancelledException):
        print(f"✓ Job {job_id} cancelled successfully")
        return None

    except Exception as e:
        # Update job with error (only if not already cancelled)
        if not check_job_cancelled(job_id):
            error_msg = f"Error processing job: {str(e)}"
            jobs.update_job_error(job_id, error_msg)
        raise
