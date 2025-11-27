"""Tests for council.py module."""

import pytest
from backend.council import (
    parse_ranking_from_text,
    calculate_aggregate_rankings,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
)


class TestParseRanking:
    """Test ranking text parsing."""

    def test_parse_standard_format(self, sample_ranking_text):
        """Test parsing of standard FINAL RANKING format."""
        result = parse_ranking_from_text(sample_ranking_text)
        assert result == ["Response C", "Response A", "Response B"]

    def test_parse_without_final_ranking_header(self):
        """Test parsing when FINAL RANKING header is missing."""
        text = "Response A is best. Response B is second. Response C is third."
        result = parse_ranking_from_text(text)
        # Should still extract Response labels in order they appear
        assert "Response A" in result
        assert "Response B" in result
        assert "Response C" in result

    def test_parse_numbered_list_without_spacing(self):
        """Test parsing numbered list with various spacing."""
        text = """FINAL RANKING:
1.Response A
2.Response B
3.Response C"""
        result = parse_ranking_from_text(text)
        assert result == ["Response A", "Response B", "Response C"]

    def test_parse_empty_text(self):
        """Test parsing empty text."""
        result = parse_ranking_from_text("")
        assert result == []

    def test_parse_malformed_ranking(self):
        """Test parsing with malformed ranking section."""
        text = """FINAL RANKING:
Some text here
Response C mentioned
And Response A too"""
        result = parse_ranking_from_text(text)
        # Should extract in order of appearance
        assert "Response C" in result
        assert "Response A" in result


class TestAggregateRankings:
    """Test aggregate ranking calculation."""

    def test_calculate_aggregate_basic(self):
        """Test basic aggregate ranking calculation."""
        stage2_results = [
            {
                "model": "model1",
                "ranking": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"
            },
            {
                "model": "model2",
                "ranking": "FINAL RANKING:\n1. Response B\n2. Response A\n3. Response C"
            },
        ]
        label_to_model = {
            "Response A": "openai/gpt-5.1",
            "Response B": "anthropic/claude-sonnet-4.5",
            "Response C": "google/gemini-3-pro-preview"
        }

        result = calculate_aggregate_rankings(stage2_results, label_to_model)

        # Response A: positions [1, 2] -> avg 1.5
        # Response B: positions [2, 1] -> avg 1.5
        # Response C: positions [3, 3] -> avg 3.0
        assert len(result) == 3
        assert result[0]["average_rank"] == 1.5
        assert result[0]["rankings_count"] == 2
        assert result[-1]["average_rank"] == 3.0

    def test_calculate_aggregate_empty_rankings(self):
        """Test with empty rankings list."""
        result = calculate_aggregate_rankings([], {})
        assert result == []

    def test_calculate_aggregate_consensus(self):
        """Test when all models agree on ranking."""
        stage2_results = [
            {"model": "m1", "ranking": "FINAL RANKING:\n1. Response A\n2. Response B"},
            {"model": "m2", "ranking": "FINAL RANKING:\n1. Response A\n2. Response B"},
            {"model": "m3", "ranking": "FINAL RANKING:\n1. Response A\n2. Response B"},
        ]
        label_to_model = {
            "Response A": "model_a",
            "Response B": "model_b"
        }

        result = calculate_aggregate_rankings(stage2_results, label_to_model)

        assert result[0]["model"] == "model_a"
        assert result[0]["average_rank"] == 1.0
        assert result[1]["model"] == "model_b"
        assert result[1]["average_rank"] == 2.0


class TestStage1:
    """Test Stage 1 response collection."""

    @pytest.mark.asyncio
    async def test_stage1_basic(self, monkeypatch):
        """Test basic Stage 1 functionality."""
        # Mock the query_models_parallel function
        async def mock_query(*args, **kwargs):
            return {
                "model1": {"content": "Response 1"},
                "model2": {"content": "Response 2"},
            }

        monkeypatch.setattr("backend.council.query_models_parallel", mock_query)

        result = await stage1_collect_responses("Test question")
        assert len(result) == 2
        assert all("model" in r and "response" in r for r in result)

    @pytest.mark.asyncio
    async def test_stage1_filters_failed_responses(self, monkeypatch):
        """Test that Stage 1 filters out None responses."""
        async def mock_query(*args, **kwargs):
            return {
                "model1": {"content": "Response 1"},
                "model2": None,  # Failed response
                "model3": {"content": "Response 3"},
            }

        monkeypatch.setattr("backend.council.query_models_parallel", mock_query)

        result = await stage1_collect_responses("Test question")
        assert len(result) == 2
        assert all(r is not None for r in result)


class TestStage2:
    """Test Stage 2 ranking collection."""

    @pytest.mark.asyncio
    async def test_stage2_anonymization(self, monkeypatch, sample_stage1_results):
        """Test that Stage 2 properly anonymizes responses."""
        ranking_response = "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"

        async def mock_query(*args, **kwargs):
            # Verify that the prompt contains "Response A" style labels
            prompt = args[1][0]["content"]
            assert "Response A:" in prompt
            assert "Response B:" in prompt
            assert "Response C:" in prompt
            # Verify original model names are NOT in the prompt
            assert "openai/gpt-5.1" not in prompt

            return {
                "model1": {"content": ranking_response},
                "model2": {"content": ranking_response},
            }

        monkeypatch.setattr("backend.council.query_models_parallel", mock_query)

        rankings, label_to_model = await stage2_collect_rankings(
            "Test question",
            sample_stage1_results
        )

        # Check label mapping was created
        assert len(label_to_model) == 3
        assert "Response A" in label_to_model
        assert label_to_model["Response A"] == "openai/gpt-5.1"

    @pytest.mark.asyncio
    async def test_stage2_parsing(self, monkeypatch, sample_stage1_results):
        """Test that Stage 2 parses rankings correctly."""
        ranking_response = "FINAL RANKING:\n1. Response C\n2. Response A\n3. Response B"

        async def mock_query(*args, **kwargs):
            return {
                "model1": {"content": ranking_response},
            }

        monkeypatch.setattr("backend.council.query_models_parallel", mock_query)

        rankings, _ = await stage2_collect_rankings(
            "Test question",
            sample_stage1_results
        )

        assert len(rankings) == 1
        assert rankings[0]["parsed_ranking"] == ["Response C", "Response A", "Response B"]


class TestStage3:
    """Test Stage 3 final synthesis."""

    @pytest.mark.asyncio
    async def test_stage3_synthesis(self, monkeypatch, sample_stage1_results):
        """Test that Stage 3 synthesizes properly."""
        final_response = "This is the chairman's final synthesized answer."

        async def mock_query(*args, **kwargs):
            return {"content": final_response}

        monkeypatch.setattr("backend.council.query_model", mock_query)

        stage2_results = [
            {
                "model": "model1",
                "ranking": "FINAL RANKING:\n1. Response A",
                "parsed_ranking": ["Response A"]
            }
        ]

        result = await stage3_synthesize_final(
            "Test question",
            sample_stage1_results,
            stage2_results
        )

        assert result["response"] == final_response
        assert "model" in result

    @pytest.mark.asyncio
    async def test_stage3_handles_failure(self, monkeypatch, sample_stage1_results):
        """Test that Stage 3 handles chairman failure gracefully."""
        async def mock_query(*args, **kwargs):
            return None  # Simulate failure

        monkeypatch.setattr("backend.council.query_model", mock_query)

        result = await stage3_synthesize_final(
            "Test question",
            sample_stage1_results,
            []
        )

        assert "error" in result["response"].lower() or result["model"] == "error"
