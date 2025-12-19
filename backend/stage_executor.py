"""
Stage Executor - Encapsulates the common logic for executing deliberation stages.

This module reduces code duplication between event_generator and resume_generator
by providing a unified interface for stage execution, timing, and persistence.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, AsyncIterator

from . import storage
from .copilot import (
    stage1_collect_responses,
    stage1_collect_responses_with_progress,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
)

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    """Result of a stage execution."""
    data: Any
    duration_ms: int
    success: bool
    error_message: str | None = None


@dataclass
class StageContext:
    """Context for stage execution - holds shared state and configuration."""
    response_id: str
    user_query: str
    log_prefix: str = "[STAGE]"

    # Stage results (filled as stages complete)
    stage1_results: list = field(default_factory=list)
    stage2_results: list = field(default_factory=list)
    stage3_result: dict | None = None

    # Stage metadata
    label_to_model: dict = field(default_factory=dict)
    aggregate_rankings: list = field(default_factory=list)

    # Timing
    stage1_duration_ms: int = 0
    stage2_duration_ms: int = 0
    stage3_duration_ms: int = 0

    @property
    def total_duration_ms(self) -> int:
        return self.stage1_duration_ms + self.stage2_duration_ms + self.stage3_duration_ms

    @property
    def metadata(self) -> dict:
        return {
            "label_to_model": self.label_to_model,
            "aggregate_rankings": self.aggregate_rankings,
        }


def sse_event(event_type: str, **kwargs) -> str:
    """Format an SSE event."""
    return f"data: {json.dumps({'type': event_type, **kwargs})}\n\n"


async def execute_stage1(
    ctx: StageContext,
    with_progress: bool = False,
    on_model_complete: Callable | None = None,
) -> StageResult:
    """
    Execute Stage 1: Collect responses from all models.

    Args:
        ctx: Stage context with user_query and response_id
        with_progress: If True, use progress-tracking version with callbacks
        on_model_complete: Callback for model completion (only used if with_progress=True)

    Returns:
        StageResult with list of model responses
    """
    storage.update_response_status(ctx.response_id, "stage1_in_progress")

    start_time = time.time()
    try:
        if with_progress and on_model_complete:
            results = await stage1_collect_responses_with_progress(
                ctx.user_query, on_model_complete
            )
        else:
            results = await stage1_collect_responses(ctx.user_query)

        duration_ms = int((time.time() - start_time) * 1000)
        ctx.stage1_results = results
        ctx.stage1_duration_ms = duration_ms

        if not results:
            error_msg = "All models failed to respond. Please try again later."
            storage.set_response_error(ctx.response_id, error_msg, "stage1")
            logger.error(f"{ctx.log_prefix} Stage 1 failed - no responses")
            return StageResult(data=[], duration_ms=duration_ms, success=False, error_message=error_msg)

        storage.update_response_stage1(ctx.response_id, results, duration_ms)
        storage.update_response_status(ctx.response_id, "stage1_complete")
        logger.info(f"{ctx.log_prefix} Stage 1 completed in {duration_ms/1000:.1f}s")

        return StageResult(data=results, duration_ms=duration_ms, success=True)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        storage.set_response_error(ctx.response_id, error_msg, "stage1")
        logger.exception(f"{ctx.log_prefix} Stage 1 error")
        return StageResult(data=[], duration_ms=duration_ms, success=False, error_message=error_msg)


async def execute_stage2(ctx: StageContext) -> StageResult:
    """
    Execute Stage 2: Collect rankings from all models.

    Args:
        ctx: Stage context with stage1_results populated

    Returns:
        StageResult with list of rankings and metadata
    """
    storage.update_response_status(ctx.response_id, "stage2_in_progress")

    start_time = time.time()
    try:
        results, label_to_model = await stage2_collect_rankings(
            ctx.user_query, ctx.stage1_results
        )
        aggregate_rankings = calculate_aggregate_rankings(results, label_to_model)
        duration_ms = int((time.time() - start_time) * 1000)

        ctx.stage2_results = results
        ctx.label_to_model = label_to_model
        ctx.aggregate_rankings = aggregate_rankings
        ctx.stage2_duration_ms = duration_ms

        if not results:
            error_msg = "All ranking models failed to respond. Please try again later."
            storage.set_response_error(ctx.response_id, error_msg, "stage2")
            logger.error(f"{ctx.log_prefix} Stage 2 failed - no rankings")
            return StageResult(data=[], duration_ms=duration_ms, success=False, error_message=error_msg)

        storage.update_response_stage2(ctx.response_id, results, duration_ms, ctx.metadata)
        storage.update_response_status(ctx.response_id, "stage2_complete")
        logger.info(f"{ctx.log_prefix} Stage 2 completed in {duration_ms/1000:.1f}s")

        return StageResult(data=results, duration_ms=duration_ms, success=True)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        storage.set_response_error(ctx.response_id, error_msg, "stage2")
        logger.exception(f"{ctx.log_prefix} Stage 2 error")
        return StageResult(data=[], duration_ms=duration_ms, success=False, error_message=error_msg)


async def execute_stage3(ctx: StageContext) -> StageResult:
    """
    Execute Stage 3: Synthesize final answer.

    Args:
        ctx: Stage context with stage1_results and stage2_results populated

    Returns:
        StageResult with synthesized answer
    """
    storage.update_response_status(ctx.response_id, "stage3_in_progress")

    start_time = time.time()
    try:
        result = await stage3_synthesize_final(
            ctx.user_query, ctx.stage1_results, ctx.stage2_results
        )
        duration_ms = int((time.time() - start_time) * 1000)

        ctx.stage3_result = result
        ctx.stage3_duration_ms = duration_ms

        storage.update_response_stage3(ctx.response_id, result, duration_ms)
        logger.info(f"{ctx.log_prefix} Stage 3 completed in {duration_ms/1000:.1f}s")

        return StageResult(data=result, duration_ms=duration_ms, success=True)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        storage.set_response_error(ctx.response_id, error_msg, "stage3")
        logger.exception(f"{ctx.log_prefix} Stage 3 error")
        return StageResult(data=None, duration_ms=duration_ms, success=False, error_message=error_msg)


def finalize_response(ctx: StageContext) -> None:
    """
    Mark response as complete and cleanup partial stage data.

    Args:
        ctx: Stage context with response_id
    """
    storage.update_response_status(ctx.response_id, "complete")
    storage.cleanup_partial_stage_responses(ctx.response_id)
    logger.info(
        f"{ctx.log_prefix} Deliberation completed: "
        f"Stage1={ctx.stage1_duration_ms/1000:.1f}s, "
        f"Stage2={ctx.stage2_duration_ms/1000:.1f}s, "
        f"Stage3={ctx.stage3_duration_ms/1000:.1f}s, "
        f"Total={ctx.total_duration_ms/1000:.1f}s"
    )


def reuse_stage1_data(ctx: StageContext, stage1_data: list) -> None:
    """
    Reuse Stage 1 data from a previous attempt (smart retry).

    Args:
        ctx: Stage context
        stage1_data: Previously collected Stage 1 results
    """
    ctx.stage1_results = stage1_data
    ctx.stage1_duration_ms = 0  # No time spent
    storage.update_response_stage1(ctx.response_id, stage1_data, 0)
    logger.info(f"{ctx.log_prefix} Reusing {len(stage1_data)} Stage 1 responses from retry")


def reuse_stage2_data(ctx: StageContext, stage2_data: list, metadata: dict) -> None:
    """
    Reuse Stage 2 data from a previous attempt (smart retry).

    Args:
        ctx: Stage context
        stage2_data: Previously collected Stage 2 rankings
        metadata: Stage 2 metadata (label_to_model, aggregate_rankings)
    """
    ctx.stage2_results = stage2_data
    ctx.label_to_model = metadata.get("label_to_model", {})
    ctx.aggregate_rankings = metadata.get("aggregate_rankings", [])
    ctx.stage2_duration_ms = 0  # No time spent
    storage.update_response_stage2(ctx.response_id, stage2_data, 0, ctx.metadata)
    logger.info(f"{ctx.log_prefix} Reusing Stage 2 rankings from retry")

