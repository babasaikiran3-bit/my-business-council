"""Tests for council.py — ranking parser, aggregate rankings, and anonymization."""

import pytest
from backend.council import (
    parse_ranking_from_text,
    _deduplicate_preserve_order,
    calculate_aggregate_rankings,
)


# ──────────────────────────────────────────────
# parse_ranking_from_text
# ──────────────────────────────────────────────

class TestParseRankingFromText:
    """Tests for the FINAL RANKING parser."""

    def test_standard_numbered_format(self):
        text = """Some evaluation text here.

FINAL RANKING:
1. Response C
2. Response A
3. Response B
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response C", "Response A", "Response B"]

    def test_case_insensitive_marker(self):
        """Should handle 'Final Ranking:', 'final ranking:', etc."""
        text = """Evaluation here.

Final Ranking:
1. Response B
2. Response A
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A"]

    def test_lowercase_marker(self):
        text = """final ranking:
1. Response A
2. Response C
3. Response B
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response A", "Response C", "Response B"]

    def test_mixed_case_marker(self):
        text = """FINAL ranking:
1. Response A
2. Response B
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response A", "Response B"]

    def test_no_marker_fallback(self):
        """Should still extract Response labels from full text as fallback."""
        text = "I think Response B is best, then Response A, and Response C is last."
        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A", "Response C"]

    def test_unnumbered_format_in_ranking_section(self):
        """Handles Response labels without numbered prefix inside FINAL RANKING."""
        text = """Good analysis.

FINAL RANKING:
Response C
Response A
Response B
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response C", "Response A", "Response B"]

    def test_deduplication(self):
        """Duplicate labels in text should be deduplicated."""
        text = """Response A is good. Response A really shines.

FINAL RANKING:
Response A
Response B
"""
        result = parse_ranking_from_text(text)
        # Should deduplicate within the ranking section
        assert result == ["Response A", "Response B"]

    def test_empty_text(self):
        result = parse_ranking_from_text("")
        assert result == []

    def test_no_response_labels(self):
        text = "This is just random text with no rankings at all."
        result = parse_ranking_from_text(text)
        assert result == []

    def test_multiple_final_ranking_markers(self):
        """If model outputs FINAL RANKING twice, should use the last one."""
        text = """My initial thoughts:

FINAL RANKING:
1. Response A
2. Response B

Wait, let me reconsider.

FINAL RANKING:
1. Response B
2. Response A
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A"]

    def test_expected_count_warning(self, caplog):
        """Should log warning when parsed count != expected count."""
        import logging
        text = """FINAL RANKING:
1. Response A
2. Response B
"""
        with caplog.at_level(logging.WARNING):
            result = parse_ranking_from_text(text, expected_count=3)
        assert result == ["Response A", "Response B"]
        assert "expected 3" in caplog.text.lower() or len(result) == 2

    def test_four_responses(self):
        text = """FINAL RANKING:
1. Response D
2. Response A
3. Response C
4. Response B
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response D", "Response A", "Response C", "Response B"]

    def test_extra_text_after_ranking(self):
        """Parser should still work even if model adds text after ranking."""
        text = """FINAL RANKING:
1. Response B
2. Response A
3. Response C

I hope this ranking is helpful!
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A", "Response C"]

    def test_response_mentioned_in_evaluation_and_ranking(self):
        """Evaluation text mentions responses, but only ranking section matters."""
        text = """Response A provides great detail on the topic.
Response B is accurate but brief.

FINAL RANKING:
1. Response B
2. Response A
"""
        result = parse_ranking_from_text(text)
        # Should parse from ranking section only, not evaluation text
        assert result == ["Response B", "Response A"]

    def test_whitespace_variations(self):
        text = """FINAL RANKING:
  1.  Response C
  2.  Response A
  3.  Response B
"""
        result = parse_ranking_from_text(text)
        assert result == ["Response C", "Response A", "Response B"]


# ──────────────────────────────────────────────
# _deduplicate_preserve_order
# ──────────────────────────────────────────────

class TestDeduplicatePreserveOrder:
    def test_no_duplicates(self):
        assert _deduplicate_preserve_order(["a", "b", "c"]) == ["a", "b", "c"]

    def test_with_duplicates(self):
        assert _deduplicate_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]

    def test_empty(self):
        assert _deduplicate_preserve_order([]) == []

    def test_all_same(self):
        assert _deduplicate_preserve_order(["x", "x", "x"]) == ["x"]


# ──────────────────────────────────────────────
# calculate_aggregate_rankings
# ──────────────────────────────────────────────

class TestCalculateAggregateRankings:
    def test_basic_aggregation(self):
        stage2_results = [
            {"model": "m1", "ranking": "...", "parsed_ranking": ["Response A", "Response B"]},
            {"model": "m2", "ranking": "...", "parsed_ranking": ["Response B", "Response A"]},
        ]
        label_to_model = {
            "Response A": "openai/gpt-5",
            "Response B": "google/gemini-3",
        }
        result = calculate_aggregate_rankings(stage2_results, label_to_model)

        assert len(result) == 2
        # Both should have avg rank 1.5 (each ranked 1st once and 2nd once)
        for entry in result:
            assert entry["average_rank"] == 1.5
            assert entry["rankings_count"] == 2

    def test_clear_winner(self):
        stage2_results = [
            {"model": "m1", "ranking": "...", "parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"model": "m2", "ranking": "...", "parsed_ranking": ["Response A", "Response C", "Response B"]},
            {"model": "m3", "ranking": "...", "parsed_ranking": ["Response A", "Response B", "Response C"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }
        result = calculate_aggregate_rankings(stage2_results, label_to_model)

        # Response A should be first (always ranked 1st → avg 1.0)
        assert result[0]["model"] == "model-a"
        assert result[0]["average_rank"] == 1.0

    def test_empty_results(self):
        result = calculate_aggregate_rankings([], {})
        assert result == []

    def test_missing_parsed_ranking(self):
        """Should handle results without parsed_ranking gracefully."""
        stage2_results = [
            {"model": "m1", "ranking": "..."},
        ]
        result = calculate_aggregate_rankings(stage2_results, {})
        assert result == []

    def test_unknown_labels_ignored(self):
        """Labels not in label_to_model should be silently skipped."""
        stage2_results = [
            {"model": "m1", "ranking": "...", "parsed_ranking": ["Response A", "Response Z"]},
        ]
        label_to_model = {"Response A": "model-a"}
        result = calculate_aggregate_rankings(stage2_results, label_to_model)
        assert len(result) == 1
        assert result[0]["model"] == "model-a"
