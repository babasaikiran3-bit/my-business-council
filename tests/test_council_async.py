"""Tests for async council functions — stage orchestration, anonymization, randomization."""

import pytest
from unittest.mock import patch, AsyncMock

from backend.council import (
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    run_full_council,
    generate_conversation_title,
)


MOCK_MODELS = ["model-a", "model-b", "model-c"]


@pytest.fixture(autouse=True)
def mock_council_models():
    with patch("backend.council.COUNCIL_MODELS", MOCK_MODELS), \
         patch("backend.council.CHAIRMAN_MODEL", "chairman-model"):
        yield


# ──────────────────────────────────────────────
# stage1_collect_responses
# ──────────────────────────────────────────────

class TestStage1:
    @pytest.mark.asyncio
    async def test_filters_out_none_responses(self):
        """Failed models (returning None) should be excluded from results."""
        async def mock_parallel(models, messages):
            return {
                "model-a": {"content": "Answer A"},
                "model-b": None,  # Failed
                "model-c": {"content": "Answer C"},
            }

        with patch("backend.council.query_models_parallel", side_effect=mock_parallel):
            results = await stage1_collect_responses("test question")

        assert len(results) == 2
        models = [r["model"] for r in results]
        assert "model-a" in models
        assert "model-c" in models
        assert "model-b" not in models

    @pytest.mark.asyncio
    async def test_all_models_fail_returns_empty(self):
        """If all models fail, should return empty list."""
        async def mock_parallel(models, messages):
            return {m: None for m in models}

        with patch("backend.council.query_models_parallel", side_effect=mock_parallel):
            results = await stage1_collect_responses("test question")

        assert results == []

    @pytest.mark.asyncio
    async def test_extracts_content_field(self):
        """Should extract 'content' from response dicts."""
        async def mock_parallel(models, messages):
            return {"model-a": {"content": "The answer is 42", "reasoning_details": "..."}}

        with patch("backend.council.COUNCIL_MODELS", ["model-a"]):
            with patch("backend.council.query_models_parallel", side_effect=mock_parallel):
                results = await stage1_collect_responses("what is the answer?")

        assert results[0]["response"] == "The answer is 42"


# ──────────────────────────────────────────────
# stage2_collect_rankings
# ──────────────────────────────────────────────

class TestStage2:
    @pytest.mark.asyncio
    async def test_label_to_model_mapping_is_bijective(self):
        """Every response label should map to exactly one model, and vice versa."""
        stage1_results = [
            {"model": "model-a", "response": "A's answer"},
            {"model": "model-b", "response": "B's answer"},
            {"model": "model-c", "response": "C's answer"},
        ]

        async def mock_parallel(models, messages):
            return {m: {"content": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"} for m in models}

        with patch("backend.council.query_models_parallel", side_effect=mock_parallel):
            _, label_to_model = await stage2_collect_rankings("test", stage1_results)

        # All 3 labels should exist
        assert len(label_to_model) == 3
        assert set(label_to_model.keys()) == {"Response A", "Response B", "Response C"}
        # All 3 models should be mapped
        assert set(label_to_model.values()) == {"model-a", "model-b", "model-c"}

    @pytest.mark.asyncio
    async def test_randomization_changes_label_assignment(self):
        """Over many runs, labels should NOT always map to the same models."""
        stage1_results = [
            {"model": "model-a", "response": "A's answer"},
            {"model": "model-b", "response": "B's answer"},
            {"model": "model-c", "response": "C's answer"},
        ]

        async def mock_parallel(models, messages):
            return {m: {"content": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"} for m in models}

        response_a_models = set()
        for _ in range(20):
            with patch("backend.council.query_models_parallel", side_effect=mock_parallel):
                _, label_to_model = await stage2_collect_rankings("test", stage1_results)
            response_a_models.add(label_to_model["Response A"])

        # With randomization, Response A should map to different models across runs
        # Probability of all 20 being the same model is (1/3)^19 ≈ 0%
        assert len(response_a_models) > 1, "Label assignment appears non-random"

    @pytest.mark.asyncio
    async def test_prompt_does_not_contain_model_names(self):
        """The ranking prompt sent to models should NOT contain model names."""
        stage1_results = [
            {"model": "openai/gpt-5.1", "response": "A's answer"},
            {"model": "google/gemini-3-pro", "response": "B's answer"},
        ]

        captured_messages = []

        async def mock_parallel(models, messages):
            captured_messages.append(messages)
            return {m: {"content": "FINAL RANKING:\n1. Response A\n2. Response B"} for m in models}

        with patch("backend.council.query_models_parallel", side_effect=mock_parallel):
            await stage2_collect_rankings("test", stage1_results)

        prompt_text = captured_messages[0][0]["content"]
        assert "openai/gpt-5.1" not in prompt_text
        assert "google/gemini-3-pro" not in prompt_text
        assert "Response A" in prompt_text
        assert "Response B" in prompt_text

    @pytest.mark.asyncio
    async def test_parsed_ranking_included_in_results(self):
        """Each stage2 result should include parsed_ranking field."""
        stage1_results = [
            {"model": "model-a", "response": "A's answer"},
            {"model": "model-b", "response": "B's answer"},
        ]

        async def mock_parallel(models, messages):
            return {m: {"content": "FINAL RANKING:\n1. Response B\n2. Response A"} for m in models}

        with patch("backend.council.query_models_parallel", side_effect=mock_parallel):
            results, _ = await stage2_collect_rankings("test", stage1_results)

        for r in results:
            assert "parsed_ranking" in r
            assert r["parsed_ranking"] == ["Response B", "Response A"]


# ──────────────────────────────────────────────
# stage3_synthesize_final
# ──────────────────────────────────────────────

class TestStage3:
    @pytest.mark.asyncio
    async def test_chairman_prompt_does_not_leak_evaluator_model_names(self):
        """Stage 3 prompt should use 'Evaluator N' not model names for stage2."""
        stage1_results = [
            {"model": "openai/gpt-5.1", "response": "Answer A"},
        ]
        stage2_results = [
            {"model": "google/gemini-3-pro", "ranking": "Response A is great.\nFINAL RANKING:\n1. Response A"},
            {"model": "anthropic/claude-4", "ranking": "Response A is fine.\nFINAL RANKING:\n1. Response A"},
        ]

        captured_messages = []

        async def mock_query(model, messages, timeout=120.0):
            captured_messages.append(messages)
            return {"content": "Synthesized answer"}

        with patch("backend.council.query_model", side_effect=mock_query):
            result = await stage3_synthesize_final("test", stage1_results, stage2_results)

        prompt = captured_messages[0][0]["content"]

        # Stage 2 evaluator model names should NOT appear
        assert "google/gemini-3-pro" not in prompt
        assert "anthropic/claude-4" not in prompt

        # Should use anonymous labels instead
        assert "Evaluator 1" in prompt
        assert "Evaluator 2" in prompt

    @pytest.mark.asyncio
    async def test_chairman_failure_returns_error(self):
        """If chairman model fails, should return error dict."""
        async def mock_query(model, messages, timeout=120.0):
            return None

        with patch("backend.council.query_model", side_effect=mock_query):
            result = await stage3_synthesize_final("test", [], [])

        assert "Error" in result["response"]

    @pytest.mark.asyncio
    async def test_chairman_success_returns_content(self):
        """Should return chairman's content on success."""
        async def mock_query(model, messages, timeout=120.0):
            return {"content": "The council concludes..."}

        with patch("backend.council.query_model", side_effect=mock_query):
            result = await stage3_synthesize_final("test", [], [])

        assert result["response"] == "The council concludes..."
        assert result["model"] == "chairman-model"


# ──────────────────────────────────────────────
# run_full_council
# ──────────────────────────────────────────────

class TestRunFullCouncil:
    @pytest.mark.asyncio
    async def test_all_models_fail_returns_error(self):
        """If all Stage 1 models fail, should return error."""
        async def mock_parallel(models, messages):
            return {m: None for m in models}

        with patch("backend.council.query_models_parallel", side_effect=mock_parallel):
            s1, s2, s3, meta = await run_full_council("test")

        assert s1 == []
        assert s2 == []
        assert s3["model"] == "error"
        assert meta == {}

    @pytest.mark.asyncio
    async def test_full_pipeline_returns_all_stages(self):
        """Successful run should return non-empty stage1, stage2, stage3, metadata."""
        call_count = [0]

        async def mock_parallel(models, messages):
            call_count[0] += 1
            if call_count[0] == 1:
                # Stage 1
                return {m: {"content": f"Answer from {m}"} for m in models}
            else:
                # Stage 2
                return {m: {"content": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"} for m in models}

        async def mock_query(model, messages, timeout=120.0):
            return {"content": "Final synthesis"}

        with patch("backend.council.query_models_parallel", side_effect=mock_parallel), \
             patch("backend.council.query_model", side_effect=mock_query):
            s1, s2, s3, meta = await run_full_council("test")

        assert len(s1) == 3
        assert len(s2) == 3
        assert s3["response"] == "Final synthesis"
        assert "label_to_model" in meta
        assert "aggregate_rankings" in meta

    @pytest.mark.asyncio
    async def test_metadata_contains_all_models(self):
        """Metadata label_to_model should contain all successful Stage 1 models."""
        async def mock_parallel(models, messages):
            return {m: {"content": f"Answer from {m}"} for m in models}

        async def mock_query(model, messages, timeout=120.0):
            return {"content": "Synthesis"}

        with patch("backend.council.query_models_parallel", side_effect=mock_parallel), \
             patch("backend.council.query_model", side_effect=mock_query):
            _, _, _, meta = await run_full_council("test")

        label_to_model = meta["label_to_model"]
        assert set(label_to_model.values()) == set(MOCK_MODELS)


# ──────────────────────────────────────────────
# generate_conversation_title
# ──────────────────────────────────────────────

class TestGenerateTitle:
    @pytest.mark.asyncio
    async def test_returns_title_from_model(self):
        async def mock_query(model, messages, timeout=120.0):
            return {"content": "Python Best Practices"}

        with patch("backend.council.query_model", side_effect=mock_query):
            title = await generate_conversation_title("How do I write clean Python?")

        assert title == "Python Best Practices"

    @pytest.mark.asyncio
    async def test_strips_quotes_from_title(self):
        async def mock_query(model, messages, timeout=120.0):
            return {"content": '"Python Best Practices"'}

        with patch("backend.council.query_model", side_effect=mock_query):
            title = await generate_conversation_title("test")

        assert title == "Python Best Practices"

    @pytest.mark.asyncio
    async def test_truncates_long_titles(self):
        async def mock_query(model, messages, timeout=120.0):
            return {"content": "A" * 100}  # 100 chars

        with patch("backend.council.query_model", side_effect=mock_query):
            title = await generate_conversation_title("test")

        assert len(title) <= 50
        assert title.endswith("...")

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        async def mock_query(model, messages, timeout=120.0):
            return None

        with patch("backend.council.query_model", side_effect=mock_query):
            title = await generate_conversation_title("test")

        assert title == "New Conversation"

    @pytest.mark.asyncio
    async def test_fallback_on_empty_content(self):
        async def mock_query(model, messages, timeout=120.0):
            return {"content": ""}

        with patch("backend.council.query_model", side_effect=mock_query):
            title = await generate_conversation_title("test")

        # Empty string stripped — should still return something
        assert isinstance(title, str)
