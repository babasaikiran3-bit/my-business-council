"""Tests for the deterministic, language-aware pediatric safety layer.

Run: `uv run --with pytest pytest tests/ -q` (from the project root).
These cover the consensus-plan P0 acceptance criteria: triage fires on Korean +
English red flags, is driven by TYPED age (not prompt strings), the newborn→infant
boundary is exact at 90 days, and the safety net is idempotent.
"""

from backend.safety import (
    age_band,
    mentions_fever,
    assess_emergency,
    apply_safety_net,
    has_emergency_callout,
    KO_DISCLAIMER,
)


# --- age_band boundaries ------------------------------------------------------
def test_age_band_boundaries():
    assert age_band(0) == "newborn"
    assert age_band(89) == "newborn"
    assert age_band(90) == "infant"        # exact newborn→infant boundary at 90 days
    assert age_band(364) == "infant"
    assert age_band(365) == "toddler"
    assert age_band(365 * 3 - 1) == "toddler"
    assert age_band(365 * 3) == "older"
    assert age_band(None) is None
    assert age_band(-5) is None


# --- fever detection: Korean, English, numeric, and negatives -----------------
def test_mentions_fever_korean():
    assert mentions_fever("아기가 열이 나요")
    assert mentions_fever("발열이 있어요")
    assert mentions_fever("체온이 38도예요")     # particle-attached Korean degrees
    assert mentions_fever("고열이 39도까지")


def test_mentions_fever_english_and_numeric():
    assert mentions_fever("my baby has a fever")
    assert mentions_fever("temperature of 38.1°C")
    assert mentions_fever("reads 100.6F")
    assert mentions_fever("38c right now")


def test_mentions_fever_negatives():
    assert not mentions_fever("toddler nap transition advice")
    assert not mentions_fever("수면 교육은 언제 시작하나요")
    assert not mentions_fever("체온이 정상이에요")    # neutral word, no high reading
    assert not mentions_fever("키가 38cm 자랐어요")   # 38cm must NOT read as 38°C
    assert not mentions_fever("37도, 정상입니다")     # below threshold
    assert not mentions_fever("88f 날씨")             # 88°F is not a fever threshold


# --- pre-pipeline triage ------------------------------------------------------
def test_triage_newborn_fever_fires_by_typed_age_not_string():
    # No English age label in the text at all — proves the typed-age contract.
    t = assess_emergency(age_days=40, query="아기 열이 38.5도예요")
    assert t is not None
    assert t["category"] == "newborn_fever"
    assert t["short_circuit"] is False
    assert any("119" in n for n in t["numbers"])


def test_triage_infant_fever_does_not_fire_newborn():
    # 100-day-old is "infant" — newborn rule must NOT fire.
    t = assess_emergency(age_days=100, query="아기 열이 38.5도예요")
    assert t is None


def test_triage_unknown_age_fever_does_not_fire_newborn():
    assert assess_emergency(age_days=None, query="열이 나요") is None


def test_triage_breathing_seizure_choking():
    assert assess_emergency(180, "아기가 호흡곤란이 있어요")["category"] == "breathing"
    assert assess_emergency(180, "입술이 파랗게 변했어요")["category"] == "breathing"
    assert assess_emergency(400, "아이가 경련을 해요")["category"] == "seizure_unresponsive"
    assert assess_emergency(400, "child is unresponsive")["category"] == "seizure_unresponsive"
    assert assess_emergency(400, "단추형 전지를 삼켰어요")["category"] == "choking_ingestion"


def test_triage_self_harm_and_abuse_short_circuit():
    sh = assess_emergency(4000, "아이가 자해를 했어요")
    assert sh["category"] == "self_harm" and sh["short_circuit"] is True
    assert any("1393" in n for n in sh["numbers"])
    ab = assess_emergency(2000, "child abuse 의심돼요")
    assert ab["category"] == "abuse" and ab["short_circuit"] is True


def test_triage_benign_returns_none():
    assert assess_emergency(730, "토들러 낮잠 전환은 어떻게 하나요") is None
    assert assess_emergency(200, "이유식 시작 시기") is None


# --- final-answer safety net + disclaimer -------------------------------------
def test_safety_net_prepends_korean_emergency_for_newborn_fever():
    out = apply_safety_net("일반적인 조언입니다.", age_days=30, query="열이 38.2도")
    assert out.startswith("> 응급:")
    assert KO_DISCLAIMER in out


def test_safety_net_is_idempotent_on_emergency_and_disclaimer():
    seeded = f"> 응급: 이미 있음\n\n본문\n\n{KO_DISCLAIMER}"
    out = apply_safety_net(seeded, age_days=30, query="38도 열")
    assert out.count("응급:") == 1
    assert out.count(KO_DISCLAIMER) == 1


def test_safety_net_no_emergency_for_non_newborn_but_disclaimer_added():
    out = apply_safety_net("가벼운 조언", age_days=730, query="미열이 있어요")
    assert not has_emergency_callout(out)
    assert out.endswith(KO_DISCLAIMER)


def test_safety_net_disclaimer_added_even_without_emergency():
    out = apply_safety_net("수면 교육 답변", age_days=500, query="수면 교육")
    assert KO_DISCLAIMER in out
