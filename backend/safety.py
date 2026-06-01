"""Deterministic, language-aware pediatric safety layer (P0).

This module is the product's safety spine. It is intentionally **independent of any
LLM** and **never parses the child's age from a prompt string** — age arrives as a
typed ``age_days`` value (the contract the consensus review made a blocker). Two jobs:

1. ``assess_emergency(age_days, query)`` — a fast, deterministic red-flag triage that
   runs BEFORE the ~30-60s council pipeline (and before any cache lookup). On a hit the
   API surfaces a Korean "지금 119에 전화하세요 / 응급실로 가세요" interstitial in <2s so a
   panicking parent is never made to wait on synthesis for a true emergency.
2. ``apply_safety_net(text, age_days, query)`` — guarantees the newborn-fever EMERGENCY
   callout is present in the final answer even if the model omits it, and appends a
   code-enforced Korean disclaimer (never left to the prompt).

Detection is bilingual (Korean primary, English fallback) and deliberately conservative:
we would rather miss a borderline phrasing than fire false emergencies on benign questions.
The categories covered are the universally-agreed pediatric red flags only.
"""

import re
from typing import Any, Dict, List, Optional

# --- Age bands (derived from typed age_days, KST-agnostic integer days) -------
NEWBORN_MAX_DAYS = 90          # < 3 months — the highest-consequence band
INFANT_MAX_DAYS = 365          # < 12 months
TODDLER_MAX_DAYS = 365 * 3     # < 3 years


def age_band(age_days: Optional[int]) -> Optional[str]:
    """Map typed age in days to a coarse band. None when age is unknown."""
    if age_days is None:
        return None
    if age_days < 0:
        return None
    if age_days < NEWBORN_MAX_DAYS:
        return "newborn"
    if age_days < INFANT_MAX_DAYS:
        return "infant"
    if age_days < TODDLER_MAX_DAYS:
        return "toddler"
    return "older"


# --- Fever detection (Korean + English + explicit temperature) ----------------
# Specific fever words only (NOT bare "열" — too many false substring hits like
# "열어"/"열심히" — and NOT bare "체온"/"temperature", which are neutral until paired
# with a high reading via the numeric check below).
_FEVER_TERMS = (
    # Korean
    "발열", "고열", "미열", "해열", "열이", "열나", "열 나", "열에",
    # English
    "fever", "febrile", "has a temperature", "high temperature", "running a temperature",
)

# Celsius written the Korean way ("38도", "38.5 도", "38도예요"); particle-tolerant (no \b).
_TEMP_C_KO_RE = re.compile(r"(\d{2,3}(?:\.\d)?)\s*도")
# Celsius latin ("38°C", "38 c"); \b keeps "38cm" from matching as 38°C.
_TEMP_C_RE = re.compile(r"(\d{2,3}(?:\.\d)?)\s*(?:°|℃)?\s*c\b", re.IGNORECASE)
# Fahrenheit ("100.4°F", "101 f").
_TEMP_F_RE = re.compile(r"(\d{2,3}(?:\.\d)?)\s*(?:°|℉)?\s*f\b", re.IGNORECASE)


def _temperature_is_febrile(q: str) -> bool:
    """True if an explicit temperature at or above the fever threshold appears."""
    for value_str in _TEMP_C_KO_RE.findall(q) + _TEMP_C_RE.findall(q):
        try:
            if float(value_str) >= 38.0:
                return True
        except ValueError:
            continue
    for value_str in _TEMP_F_RE.findall(q):
        try:
            if float(value_str) >= 100.4:
                return True
        except ValueError:
            continue
    return False


def mentions_fever(query: str) -> bool:
    """True if the text mentions fever (a specific KR/EN word, or a high temperature reading)."""
    if not query:
        return False
    q = query.lower()
    if any(term in q for term in _FEVER_TERMS):
        return True
    return _temperature_is_febrile(q)


# --- Red-flag categories ------------------------------------------------------
# Each category lists trigger phrases (Korean + English). Order matters: the first
# matching category wins. `short_circuit=True` means the pediatric council pipeline
# should NOT run (the situation is outside the product's scope — e.g. self-harm,
# abuse) and only the routing interstitial is appropriate.

_EMERGENCY_NUMBERS = {
    "119": "119 (응급실·구급차)",
    "1339": "1339 (질병관리청 상담콜센터)",
    "1393": "1393 (자살예방 상담전화)",
    "112": "112 (경찰)",
    "129": "129 (보건복지·아동학대 상담)",
}

_CATEGORIES: List[Dict[str, Any]] = [
    {
        "category": "breathing",
        "terms": (
            "호흡곤란", "숨을 못", "숨을 안", "숨이 가쁘", "숨쉬기", "청색증", "입술이 파",
            "입술이 새파", "얼굴이 파",
            "not breathing", "can't breathe", "cant breathe", "trouble breathing",
            "difficulty breathing", "struggling to breathe", "blue lips", "turning blue",
        ),
        "numbers": ["119"],
        "title_ko": "호흡 곤란은 응급 상황입니다",
        "message_ko": "아이가 숨쉬기 힘들어하거나 입술·얼굴이 파랗게 변하면 즉시 119에 전화하거나 응급실로 가세요. 기다리지 마세요.",
        "short_circuit": False,
    },
    {
        "category": "seizure_unresponsive",
        "terms": (
            "경련", "발작", "의식이 없", "의식 없", "의식저하", "반응이 없", "반응 없",
            "축 늘어", "늘어져", "깨어나지", "안 깨어",
            "seizure", "convulsion", "convulsing", "unresponsive", "won't wake",
            "wont wake", "limp", "unconscious", "passed out",
        ),
        "numbers": ["119"],
        "title_ko": "경련·의식저하는 응급 상황입니다",
        "message_ko": "아이가 경련을 하거나 의식이 흐리고 잘 깨어나지 않으면 즉시 119에 전화하세요. 응급실 평가가 필요합니다.",
        "short_circuit": False,
    },
    {
        "category": "choking_ingestion",
        "terms": (
            "삼켰", "삼킴", "목에 걸", "기도가 막", "이물질", "단추형 전지", "수은전지",
            "버튼 전지", "자석을 삼", "자석 삼",
            "choking", "swallowed", "button battery", "magnet", "something stuck in",
            "object in throat",
        ),
        "numbers": ["119"],
        "title_ko": "삼킴·기도막힘은 응급 상황입니다",
        "message_ko": "아이가 무언가에 목이 막혔거나 단추형 전지·자석 등을 삼킨 경우 즉시 119에 전화하세요. 단추형 전지·자석은 매우 위험합니다.",
        "short_circuit": False,
    },
    {
        "category": "self_harm",
        "terms": (
            "자살", "자해", "죽고 싶", "죽고싶", "목숨을 끊",
            "suicide", "suicidal", "self-harm", "self harm", "kill myself", "kill themselves",
            "hurt myself",
        ),
        "numbers": ["1393", "112"],
        "title_ko": "지금 바로 도움을 받으세요",
        "message_ko": "위급한 상황이라면 즉시 119 또는 112에 연락하세요. 자살예방 상담전화 1393에서 24시간 상담을 받을 수 있습니다. 혼자 견디지 마세요.",
        "short_circuit": True,
    },
    {
        "category": "abuse",
        "terms": (
            "아동학대", "학대", "때려서", "맞아서", "맞고",
            "child abuse", "being abused", "being hit", "beaten",
        ),
        "numbers": ["112", "129"],
        "title_ko": "아동 안전이 우선입니다",
        "message_ko": "아동이 위험에 처해 있다면 즉시 112에 신고하세요. 아동학대 신고·상담은 112 또는 129(보건복지상담)에서 받을 수 있습니다.",
        "short_circuit": True,
    },
]

# Korean newborn-fever interstitial — the single highest-consequence pediatric rule.
_NEWBORN_FEVER_TRIAGE: Dict[str, Any] = {
    "category": "newborn_fever",
    "numbers": ["119", "1339"],
    "title_ko": "생후 3개월 미만 아기의 발열은 응급 상황입니다",
    "message_ko": (
        "생후 3개월 미만 아기에게 열이 있으면 응급 상황입니다. 지금 바로 의사에게 연락하거나 "
        "가까운 응급실로 가세요 — 기다리지 마세요. 이 시기의 아기는 겉으로 괜찮아 보여도 빠르게 "
        "상태가 나빠질 수 있습니다."
    ),
    "short_circuit": False,
}


def assess_emergency(age_days: Optional[int], query: str) -> Optional[Dict[str, Any]]:
    """Deterministic pre-pipeline triage. Returns a triage dict on a red-flag hit, else None.

    The returned dict is JSON-serialisable for the SSE ``emergency`` event:
    ``{category, title_ko, message_ko, numbers: [display strings], short_circuit}``.
    """
    q = (query or "").lower()

    # Highest-consequence rule first: newborn (typed age) + fever.
    if age_band(age_days) == "newborn" and mentions_fever(query):
        return _format_triage(_NEWBORN_FEVER_TRIAGE)

    for cat in _CATEGORIES:
        if any(term.lower() in q for term in cat["terms"]):
            return _format_triage(cat)

    return None


def _format_triage(cat: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": cat["category"],
        "title_ko": cat["title_ko"],
        "message_ko": cat["message_ko"],
        "numbers": [_EMERGENCY_NUMBERS.get(n, n) for n in cat["numbers"]],
        "short_circuit": cat.get("short_circuit", False),
    }


# --- Final-answer safety net + disclaimer -------------------------------------
# NOTE: `\b` never fires after Hangul in Python/JS regex, so `> 응급:` went undetected
# and apply_safety_net could double-prepend the banner. Match a following separator
# (whitespace/colon, ASCII or full-width) instead — Hangul-safe and idempotent.
_EMERGENCY_BLOCKQUOTE_RE = re.compile(
    r"^\s*>?\s*\**\s*(?:EMERGENCY|응급)[\s:：]", re.IGNORECASE | re.MULTILINE
)

NEWBORN_FEVER_EMERGENCY_KO = (
    "> 응급: 생후 3개월 미만 아기의 발열은 응급 상황입니다. 지금 바로 의사에게 연락하거나 가까운 "
    "응급실로 가세요 — 기다리지 마세요. 이 시기의 아기는 겉으로 괜찮아 보여도 빠르게 나빠질 수 있습니다."
)

KO_DISCLAIMER = (
    "ℹ️ 이 답변은 신뢰할 수 있는 의료 출처를 바탕으로 한 일반적인 정보이며, 진단이나 전문적인 "
    "의료 상담을 대신하지 않습니다. 걱정되는 증상이 있으면 소아청소년과 의사나 의료진과 상담하세요."
)


def has_emergency_callout(text: str) -> bool:
    """True if the text already leads with an EMERGENCY / 응급 blockquote."""
    return bool(_EMERGENCY_BLOCKQUOTE_RE.search(text or ""))


def apply_safety_net(response_text: str, age_days: Optional[int], query: str) -> str:
    """Guarantee the newborn-fever emergency callout, then append the Korean disclaimer.

    Driven by the typed ``age_days`` (NOT prompt-string parsing). Idempotent: it will not
    duplicate an existing emergency callout or an existing disclaimer.
    """
    text = response_text or ""

    if age_band(age_days) == "newborn" and mentions_fever(query) and not has_emergency_callout(text):
        text = f"{NEWBORN_FEVER_EMERGENCY_KO}\n\n{text}"

    if KO_DISCLAIMER not in text:
        text = f"{text}\n\n{KO_DISCLAIMER}"

    return text
