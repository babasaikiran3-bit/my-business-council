"""Tests for SSE streaming endpoint and streaming pipeline.

Covers:
- SSE endpoint integration (FastAPI TestClient)
- Event ordering and canonical shape validation
- Line-buffering resilience (SSE chunks split mid-event)
- Error handling (404 for unknown conversation)
- run_full_council_streaming with mocked agents and providers
- Graceful degradation when agents fail
"""

from __future__ import annotations

import asyncio
import codecs
import json
import os
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

# Ensure backend/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# SSE line-buffering helpers (per research brief: SSE chunks can split mid-event)
# ---------------------------------------------------------------------------

def _parse_sse_chunks(chunks: List[bytes]) -> List[Dict[str, Any]]:
    """Incrementally decode arbitrary byte chunks into SSE JSON events."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
    buffer = ""
    events: List[Dict[str, Any]] = []

    def parse_frame(frame: str) -> None:
        data_lines = [
            line[5:].lstrip()
            for line in frame.splitlines()
            if line.startswith("data:")
        ]
        if data_lines:
            events.append(json.loads("\n".join(data_lines)))

    for chunk in chunks:
        buffer += decoder.decode(chunk)
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            parse_frame(frame)

    buffer += decoder.decode(b"", final=True)
    if buffer.strip():
        parse_frame(buffer)
    return events


def _parse_sse_events(raw: bytes) -> List[Dict[str, Any]]:
    return _parse_sse_chunks([raw])


def _split_sse_chunks(raw: bytes, chunk_size: int = 64) -> List[bytes]:
    """Split raw SSE response into chunks to simulate network framing."""
    return [raw[i : i + chunk_size] for i in range(0, len(raw), chunk_size)]


# ---------------------------------------------------------------------------
# Known canonical event types (from research brief + council.py)
# ---------------------------------------------------------------------------

KNOWN_EVENT_TYPES = frozenset({
    "stage",        # stage start/done markers
    "agent",        # per-agent lifecycle: working, done, error
    "thought",      # agent reasoning text
    "tool",         # agent tool use
    "result",       # stage 1 result text per agent
    "research",     # stage 0 research brief
    "ranking",      # stage 2 aggregate rankings
    "final",        # stage 3 chairman synthesis
    "metadata",     # de-anonymization metadata
    "title",        # auto-generated conversation title
    "done",         # terminal event with full stages
    "fatal",        # unrecoverable error
})


# ---------------------------------------------------------------------------
# Mock agents (Stage 0 + Stage 1)
# ---------------------------------------------------------------------------

async def _mock_agent_stream_ok(model_id: str, prompt: str, emit, cwd=None) -> str:
    """Happy-path: emits working → thought → done, returns text."""
    emit({"type": "agent", "model": model_id, "status": "working"})
    emit({"type": "thought", "model": model_id, "text": f"Thinking as {model_id}..."})
    emit({"type": "agent", "model": model_id, "status": "done"})
    return f"Response from {model_id}"


async def _mock_agent_stream_fail(model_id: str, prompt: str, emit, cwd=None) -> Optional[str]:
    """Failure: emits working → error, returns None."""
    emit({"type": "agent", "model": model_id, "status": "working"})
    emit({"type": "agent", "model": model_id, "status": "error", "reason": "mock failure"})
    return None


# ---------------------------------------------------------------------------
# Mock providers (Stage 2 rankings + Stage 3 chairman)
# ---------------------------------------------------------------------------

async def _mock_query_model(
    model: str, messages: list, timeout: float = 300, cwd=None, allow_write: bool = False,
) -> Optional[Dict[str, Any]]:
    """Return synthetic responses matching the expected format for each stage."""
    prompt = ""
    for m in messages:
        content = m.get("content", "")
        if content:
            prompt = content
            break

    if "FINAL RANKING:" in prompt or "evaluate each response" in prompt.lower():
        # Stage 2 — ranking
        return {
            "content": (
                "Response A provides good detail.\n"
                "Response B is also strong.\n\n"
                "FINAL RANKING:\n"
                "1. Response A\n"
                "2. Response B"
            ),
            "reasoning_details": None,
        }

    if "Chairman" in prompt or "synthesize" in prompt.lower() or "STAGE 1" in prompt:
        # Stage 3 — chairman synthesis
        return {
            "content": f"Synthesized answer from {model} chairman.",
            "reasoning_details": None,
        }

    # Default (title generation, etc.)
    return {"content": "Short title", "reasoning_details": None}


async def _mock_query_models_parallel(
    models: list, messages: list, cwd=None,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Return a synthetic ranking result per model."""
    results = {}
    for m in models:
        results[m] = await _mock_query_model(m, messages, cwd=cwd)
    return results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(temp_db):
    """FastAPI TestClient with isolated DB via ``temp_db`` fixture."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def conv_id(client) -> str:
    """Create a fresh conversation and return its ID."""
    resp = client.post("/api/conversations", json={})
    assert resp.status_code == 200
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# SSE endpoint integration tests
# ---------------------------------------------------------------------------

class TestStreamEndpoint:
    """Integration tests for POST /api/conversations/{id}/message/stream."""

    def test_returns_sse_content_type(self, client, conv_id):
        """Streaming endpoint must return ``text/event-stream``."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "hello"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

    def test_404_for_unknown_conversation(self, client):
        """Streaming endpoint returns 404 when conversation does not exist."""
        resp = client.post(
            "/api/conversations/nonexistent-id/message/stream",
            json={"content": "hello"},
        )
        assert resp.status_code == 404

    def test_bad_repo_returns_400(self, client, conv_id):
        """Streaming endpoint returns 400 for a disallowed repo path."""
        resp = client.post(
            f"/api/conversations/{conv_id}/message/stream",
            json={"content": "hello", "repo_path": "/etc/passwd"},
        )
        assert resp.status_code == 400

    def test_emits_fatal_on_internal_error(self, client, conv_id):
        """When the streaming pipeline raises, a 'fatal' event is emitted."""
        with patch(
            "backend.main.run_full_council_streaming",
            side_effect=RuntimeError("simulated crash"),
        ):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "trigger crash"},
            )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.content)
        fatal = [e for e in events if e.get("type") == "fatal"]
        assert len(fatal) == 1
        assert "simulated crash" in fatal[0]["message"]


class TestStreamEventOrdering:
    """Verify that events are emitted in the correct sequence."""

    def test_stages_emitted_in_order(self, client, conv_id):
        """Events must follow: stage.0.start → stage.0.done → stage.1.start
        → stage.1.done → stage.2... → done."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test ordering", "research": False},
            )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.content)

        stage_transitions = []
        for e in events:
            if e.get("type") == "stage":
                stage_transitions.append((e.get("stage"), e.get("status")))

        assert stage_transitions[0] == (1, "start")
        assert stage_transitions[1] == (1, "done")
        assert stage_transitions[2] == (2, "start")
        assert stage_transitions[3] == (2, "done")
        assert stage_transitions[4] == (3, "start")
        assert stage_transitions[5] == (3, "done")

    def test_stage0_emitted_when_research_enabled(self, client, conv_id):
        """When research=True (default), stage 0 events are emitted."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test with research"},
            )
        events = _parse_sse_events(resp.content)
        stage0 = [e for e in events if e.get("type") == "stage" and e.get("stage") == 0]
        assert len(stage0) == 2  # start + done
        research_events = [e for e in events if e.get("type") == "research"]
        assert len(research_events) == 1

    def test_final_event_contains_all_stages(self, client, conv_id):
        """The terminal ``done`` event must carry stage1, stage2, stage3."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test final event"},
            )
        events = _parse_sse_events(resp.content)
        done = [e for e in events if e.get("type") == "done"]
        assert len(done) == 1
        assert "stage1" in done[0]
        assert "stage2" in done[0]
        assert "stage3" in done[0]
        assert "metadata" in done[0]

    def test_metadata_event_has_required_fields(self, client, conv_id):
        """Metadata event must carry label_to_model and aggregate_rankings."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test metadata"},
            )
        events = _parse_sse_events(resp.content)
        metadata_events = [e for e in events if e.get("type") == "metadata"]
        assert len(metadata_events) == 1
        meta = metadata_events[0]["metadata"]
        assert "label_to_model" in meta
        assert "aggregate_rankings" in meta


class TestStreamEventShapes:
    """Validate that individual events conform to their canonical shapes."""

    def test_agent_events_have_model_and_status(self, client, conv_id):
        """Every ``agent`` event must have 'model' and 'status' fields."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test agent events", "research": False},
            )
        events = _parse_sse_events(resp.content)
        agent_events = [e for e in events if e.get("type") == "agent"]
        assert len(agent_events) > 0
        for ae in agent_events:
            assert "model" in ae
            assert "status" in ae
            assert ae["status"] in ("working", "done", "error")

    def test_thought_events_have_model_and_text(self, client, conv_id):
        """Every ``thought`` event must have 'model' and 'text'."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test thoughts", "research": False},
            )
        events = _parse_sse_events(resp.content)
        thought_events = [e for e in events if e.get("type") == "thought"]
        assert len(thought_events) > 0
        for te in thought_events:
            assert "model" in te
            assert "text" in te

    def test_all_events_have_known_type(self, client, conv_id):
        """No event should have an unknown type."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test known types"},
            )
        events = _parse_sse_events(resp.content)
        for e in events:
            assert e.get("type") in KNOWN_EVENT_TYPES, (
                f"Unknown event type: {e.get('type')} in {json.dumps(e)[:120]}"
            )


class TestStage1PerAgentStreaming:
    """Stage 1 must emit working → thought(s) → done for each council member."""

    def test_each_member_emits_working_and_done(self, client, conv_id):
        """Each council member gets a working event followed by done/error."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test per-agent lifecycle", "research": False,
                      "members": ["claude", "codex", "gemini", "deepseek"]},
            )
        events = _parse_sse_events(resp.content)
        agent_events = [e for e in events if e.get("type") == "agent"]

        model_states: Dict[str, List[str]] = {}
        for ae in agent_events:
            model_states.setdefault(ae["model"], []).append(ae["status"])

        for model_id in ("claude", "codex", "gemini", "deepseek"):
            assert model_id in model_states, f"No agent events for {model_id}"
            assert "working" in model_states[model_id], f"{model_id} missing 'working'"
            assert "done" in model_states[model_id], f"{model_id} missing terminal event"

    def test_stage1_results_emitted_per_agent(self, client, conv_id):
        """Each successful agent should emit a 'result' event."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test results", "research": False,
                      "members": ["claude", "codex"]},
            )
        events = _parse_sse_events(resp.content)
        results = [e for e in events if e.get("type") == "result"]
        assert len(results) == 2
        models_with_results = {r["model"] for r in results}
        assert models_with_results == {"claude", "codex"}


class TestGracefulDegradation:
    """The council must continue when some agents fail."""

    def test_partial_failures_dont_block_stream(self, client, conv_id):
        """When some agents fail, the remaining agents still finish."""
        async def mixed_agents(model_id, prompt, emit, cwd=None):
            if model_id == "codex":
                return await _mock_agent_stream_fail(model_id, prompt, emit, cwd=cwd)
            return await _mock_agent_stream_ok(model_id, prompt, emit, cwd=cwd)

        with patch("backend.council.run_agent_stream", mixed_agents), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "test graceful", "research": False,
                      "members": ["claude", "codex", "gemini"]},
            )
        events = _parse_sse_events(resp.content)

        agent_events = [e for e in events if e.get("type") == "agent"]
        codex_statuses = [e["status"] for e in agent_events if e["model"] == "codex"]
        claude_statuses = [e["status"] for e in agent_events if e["model"] == "claude"]

        assert "error" in codex_statuses
        assert "done" in claude_statuses

        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1
        stage1 = done_events[0]["stage1"]
        stage1_models = {r["model"] for r in stage1}
        assert "claude" in stage1_models
        assert "codex" not in stage1_models

    def test_all_agents_fail_yields_error_response(self, client, conv_id):
        """When every agent fails, the stream emits a final error."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_fail), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "all fail", "research": False,
                      "members": ["claude", "codex"]},
            )
        events = _parse_sse_events(resp.content)
        final_events = [e for e in events if e.get("type") == "final"]
        assert len(final_events) == 1
        assert final_events[0]["model"] == "error"


# ---------------------------------------------------------------------------
# Line-buffering tests (SSE chunk splitting)
# ---------------------------------------------------------------------------

class TestLineBuffering:
    """SSE chunks can arrive in arbitrary byte boundaries — the parser must
    reassemble complete lines before decoding JSON."""

    def test_events_parse_from_whole_response(self, client, conv_id):
        """Complete SSE response parses correctly (baseline)."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "baseline", "research": False,
                      "members": ["claude"]},
            )
        events = _parse_sse_events(resp.content)
        assert len(events) > 0
        for e in events:
            assert isinstance(e, dict)
            assert "type" in e

    def test_events_parse_from_split_chunks(self, client, conv_id):
        """Incremental parsing survives arbitrary small network chunks."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "split test", "research": False,
                      "members": ["claude"]},
            )
        chunks = _split_sse_chunks(resp.content, chunk_size=32)
        events_from_split = _parse_sse_chunks(chunks)
        events_whole = _parse_sse_events(resp.content)
        assert len(events_from_split) == len(events_whole)
        assert events_from_split == events_whole

    def test_single_byte_chunks(self, client, conv_id):
        """Extreme case: 1-byte chunks still reassemble correctly."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "byte test", "research": False,
                      "members": ["claude"]},
            )
        events = _parse_sse_chunks(_split_sse_chunks(resp.content, chunk_size=1))
        assert len(events) > 0
        done = [e for e in events if e.get("type") == "done"]
        assert len(done) == 1

    def test_chunk_boundary_in_middle_of_json(self, client, conv_id):
        """A chunk boundary inside a JSON value must not corrupt parsing."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "mid-json split", "research": False,
                      "members": ["claude", "codex"]},
            )
        events = _parse_sse_chunks(_split_sse_chunks(resp.content, chunk_size=37))
        assert len(events) > 0
        for e in events:
            assert "type" in e

    def test_utf8_codepoint_split_across_chunks(self):
        """The incremental decoder preserves a multibyte character boundary."""
        raw = 'data: {"type":"thought","text":"café"}\n\n'.encode("utf-8")
        split = raw.index("é".encode("utf-8")) + 1
        events = _parse_sse_chunks([raw[:split], raw[split:]])
        assert events == [{"type": "thought", "text": "café"}]

    def test_malformed_json_is_not_silently_dropped(self):
        """Malformed server events must fail the test parser visibly."""
        with pytest.raises(json.JSONDecodeError):
            _parse_sse_chunks([b"data: {not-json}\n\n"])


# ---------------------------------------------------------------------------
# run_full_council_streaming pipeline tests (direct, no HTTP)
# ---------------------------------------------------------------------------

class TestStreamingPipeline:
    """Tests for ``run_full_council_streaming`` directly, bypassing HTTP."""

    @pytest.mark.asyncio
    async def test_emits_stage_markers(self):
        """Mocked pipeline must emit stage start/done for stages 0-3."""
        from backend.council import run_full_council_streaming

        events: List[Dict[str, Any]] = []

        def emit(e: Dict[str, Any]):
            events.append(e)

        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            await run_full_council_streaming(
                "test query", emit, members=["claude", "codex"],
                chairman="claude", research=True,
            )

        stages_seen = {e["stage"] for e in events if e.get("type") == "stage"}
        assert stages_seen == {0, 1, 2, 3}

    @pytest.mark.asyncio
    async def test_research_disabled_skips_stage0(self):
        """When research=False, stage 0 is not emitted."""
        from backend.council import run_full_council_streaming

        events: List[Dict[str, Any]] = []

        def emit(e: Dict[str, Any]):
            events.append(e)

        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            await run_full_council_streaming(
                "test query", emit, members=["claude"], chairman="claude",
                research=False,
            )

        stage0 = [e for e in events if e.get("type") == "stage" and e.get("stage") == 0]
        assert len(stage0) == 0
        stage1 = [e for e in events if e.get("type") == "stage" and e.get("stage") == 1]
        assert len(stage1) == 2

    @pytest.mark.asyncio
    async def test_aggregate_rankings_in_ranking_event(self):
        """The ranking event must carry aggregate_rankings list."""
        from backend.council import run_full_council_streaming

        events: List[Dict[str, Any]] = []

        def emit(e: Dict[str, Any]):
            events.append(e)

        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            await run_full_council_streaming(
                "test query", emit, members=["claude", "codex"],
                chairman="claude", research=False,
            )

        ranking_events = [e for e in events if e.get("type") == "ranking"]
        assert len(ranking_events) == 1
        assert "aggregate" in ranking_events[0]
        agg = ranking_events[0]["aggregate"]
        assert isinstance(agg, list)
        assert len(agg) == 2

    @pytest.mark.asyncio
    async def test_final_event_model_matches_chairman(self):
        """The final event's model should be the chairman."""
        from backend.council import run_full_council_streaming

        events: List[Dict[str, Any]] = []

        def emit(e: Dict[str, Any]):
            events.append(e)

        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            await run_full_council_streaming(
                "test query", emit, members=["claude", "codex"],
                chairman="claude", research=False,
            )

        final_events = [e for e in events if e.get("type") == "final"]
        assert len(final_events) == 1
        assert final_events[0]["model"] == "claude"

    @pytest.mark.asyncio
    async def test_done_event_includes_metadata(self):
        """The pipeline returns metadata later used by the endpoint's done event."""
        from backend.council import run_full_council_streaming

        events: List[Dict[str, Any]] = []

        def emit(e: Dict[str, Any]):
            events.append(e)

        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            stage1, stage2, stage3, metadata = await run_full_council_streaming(
                "test query", emit, members=["claude", "codex"],
                chairman="claude", research=False,
            )

        assert stage1
        assert stage2
        assert stage3["model"] == "claude"
        assert "label_to_model" in metadata
        assert len(metadata["label_to_model"]) == 2


# ---------------------------------------------------------------------------
# SSE endpoint: persistence after stream
# ---------------------------------------------------------------------------

class TestStreamPersistsMessage:
    """After the stream completes, the conversation must be updated."""

    def test_conversation_updated_after_stream(self, client, conv_id):
        """Stream completion persists user + assistant messages."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "persist me", "research": False,
                      "members": ["claude"]},
            )
        assert resp.status_code == 200

        conv = client.get(f"/api/conversations/{conv_id}").json()
        assert len(conv["messages"]) >= 2
        roles = [m["role"] for m in conv["messages"]]
        assert "user" in roles
        assert "assistant" in roles

    def test_title_generated_on_first_message(self, client, conv_id):
        """First message in a conversation triggers title generation."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "title me", "research": False,
                      "members": ["claude"]},
            )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.content)
        title_events = [e for e in events if e.get("type") == "title"]
        assert title_events == [{"type": "title", "title": "Short title"}]
        conversation = client.get(f"/api/conversations/{conv_id}").json()
        assert conversation["title"] == "Short title"


# ---------------------------------------------------------------------------
# Cache-control and connection headers
# ---------------------------------------------------------------------------

class TestStreamHeaders:
    """SSE responses must carry appropriate cache and connection headers."""

    def test_no_cache_header(self, client, conv_id):
        """SSE must set ``Cache-Control: no-cache``."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "headers test", "research": False,
                      "members": ["claude"]},
            )
        assert resp.status_code == 200
        assert "no-cache" in resp.headers.get("cache-control", "")

    def test_keep_alive_header(self, client, conv_id):
        """SSE should have ``Connection: keep-alive``."""
        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "keep-alive test", "research": False,
                      "members": ["claude"]},
            )
        assert resp.status_code == 200
        assert "keep-alive" in resp.headers.get("connection", "")


# ---------------------------------------------------------------------------
# Repo path validation in stream
# ---------------------------------------------------------------------------

class TestStreamRepoValidation:
    """Repo path must be validated before the stream opens."""

    def test_valid_repo_not_blocked(self, client, monkeypatch, tmp_path):
        """An allowed repo path should let the stream proceed."""
        import backend.repos as repos_mod

        monkeypatch.setattr(
            repos_mod, "list_repos",
            lambda: [{"path": str(tmp_path), "name": "test-repo"}],
        )
        monkeypatch.setattr(
            repos_mod, "is_allowed",
            lambda p: p == str(tmp_path),
        )

        conv_id = client.post("/api/conversations", json={}).json()["id"]

        with patch("backend.council.run_agent_stream", _mock_agent_stream_ok), \
             patch("backend.council.query_models_parallel", _mock_query_models_parallel), \
             patch("backend.council.query_model", _mock_query_model):
            resp = client.post(
                f"/api/conversations/{conv_id}/message/stream",
                json={"content": "valid repo", "repo_path": str(tmp_path),
                      "research": False, "members": ["claude"]},
            )
        assert resp.status_code == 200
