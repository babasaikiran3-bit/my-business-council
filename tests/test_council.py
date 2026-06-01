"""Mocked unit tests for the council pipeline core (no live API).

query_model / query_models_parallel are monkeypatched to deterministic dicts so every
stage, the load-bearing FINAL RANKING parser, the aggregate math, and the safety-net
idempotency are covered without network calls.
"""

import backend.council as council
from backend.safety import KO_DISCLAIMER


def _resp(content, annotations=None):
    return {"content": content, "reasoning_details": None, "annotations": annotations}


# --- timeout budget arithmetic (WS-4.6) --------------------------------------
def test_timeout_budget_under_pipeline_cap():
    from backend import config
    per_stage = (
        config.STAGE0_TIMEOUT + config.STAGE1_TIMEOUT + config.STAGE2_TIMEOUT + config.STAGE3_TIMEOUT
    )
    assert per_stage < config.PIPELINE_TIMEOUT  # per-stage caps fire first, pipeline is the backstop


# --- _format_sources_list ----------------------------------------------------
def test_format_sources_list_empty_and_nonempty():
    assert "no sources" in council._format_sources_list([])
    out = council._format_sources_list([{"url": "https://who.int/a", "title": "WHO"}])
    assert "WHO" in out and "https://who.int/a" in out


# --- Stage 0 -----------------------------------------------------------------
async def test_stage0_dedupes_and_allowlists_sources(monkeypatch):
    annotations = [
        {"type": "url_citation", "url_citation": {"url": "https://who.int/a", "title": "WHO A"}},
        {"type": "url_citation", "url_citation": {"url": "https://who.int/a", "title": "dup"}},
        {"type": "url_citation", "url_citation": {"url": "https://blog.naver.com/x", "title": "blog"}},
        {"type": "url_citation", "url_citation": {"url": "https://kdca.go.kr/b", "title": "KDCA"}},
    ]

    async def fake_qm(model, messages, **kw):
        assert kw.get("web_search") is True
        return _resp("근거 요약", annotations)

    monkeypatch.setattr(council, "query_model", fake_qm)
    out = await council.stage0_research("질문")
    assert out["evidence_brief"] == "근거 요약"
    assert [s["url"] for s in out["sources"]] == ["https://who.int/a", "https://kdca.go.kr/b"]


async def test_stage0_returns_empty_on_failure(monkeypatch):
    async def fake_qm(model, messages, **kw):
        return None

    monkeypatch.setattr(council, "query_model", fake_qm)
    assert await council.stage0_research("q") == {"evidence_brief": "", "sources": []}


# --- Stage 1 -----------------------------------------------------------------
async def test_stage1_includes_only_successful_models(monkeypatch):
    async def fake_parallel(models, messages, **kw):
        return {models[0]: _resp("ans0"), models[1]: None, models[2]: _resp("ans2")}

    monkeypatch.setattr(council, "query_models_parallel", fake_parallel)
    stage0 = {"evidence_brief": "e", "sources": [{"url": "https://who.int/a", "title": "WHO"}]}
    res = await council.stage1_collect_responses("q", stage0)
    assert len(res) == 2
    assert council.COUNCIL_MODELS[1] not in [r["model"] for r in res]
    assert all(r["sources"] == stage0["sources"] for r in res)


async def test_stage1_empty_when_all_fail(monkeypatch):
    async def fake_parallel(models, messages, **kw):
        return {m: None for m in models}

    monkeypatch.setattr(council, "query_models_parallel", fake_parallel)
    assert await council.stage1_collect_responses("q", {"evidence_brief": "", "sources": []}) == []


async def test_stage1_grounded_message_carries_evidence(monkeypatch):
    captured = {}

    async def fake_parallel(models, messages, **kw):
        captured["content"] = messages[-1]["content"]
        return {models[0]: _resp("a")}

    monkeypatch.setattr(council, "query_models_parallel", fake_parallel)
    stage0 = {"evidence_brief": "중요한 근거", "sources": [{"url": "https://who.int/a", "title": "WHO"}]}
    await council.stage1_collect_responses("질문X", stage0)
    assert "중요한 근거" in captured["content"] and "질문X" in captured["content"]


# --- Stage 2 + ranking parser ------------------------------------------------
async def test_stage2_parses_and_maps_labels(monkeypatch):
    text = "평가...\n\nFINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"

    async def fake_parallel(models, messages, **kw):
        return {m: _resp(text) for m in models}

    monkeypatch.setattr(council, "query_models_parallel", fake_parallel)
    stage1 = [{"model": m, "response": "r", "sources": []} for m in council.COUNCIL_MODELS]
    results, label_to_model = await council.stage2_collect_rankings("q", stage1)
    assert len(results) == len(council.COUNCIL_MODELS)
    assert label_to_model["Response A"] == council.COUNCIL_MODELS[0]
    assert results[0]["parsed_ranking"] == ["Response A", "Response B", "Response C"]


def test_parse_ranking_happy_path():
    t = "blah\nFINAL RANKING:\n1. Response B\n2. Response A"
    assert council.parse_ranking_from_text(t) == ["Response B", "Response A"]


def test_parse_ranking_missing_header_fallback():
    t = "I prefer Response C, then Response A, then Response B"
    assert council.parse_ranking_from_text(t) == ["Response C", "Response A", "Response B"]


def test_parse_ranking_unnumbered_in_section_fallback():
    t = "FINAL RANKING:\nResponse A is best\nResponse B second"
    assert council.parse_ranking_from_text(t) == ["Response A", "Response B"]


def test_parse_ranking_no_matches_returns_empty():
    assert council.parse_ranking_from_text("no ranking content at all") == []


# --- aggregate math ----------------------------------------------------------
def test_aggregate_rankings_math_and_order():
    label_to_model = {"Response A": "m1", "Response B": "m2", "Response C": "m3"}
    s2 = [
        {"model": "m1", "ranking": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"},
        {"model": "m2", "ranking": "FINAL RANKING:\n1. Response B\n2. Response A\n3. Response C"},
    ]
    agg = council.calculate_aggregate_rankings(s2, label_to_model)
    by = {a["model"]: a for a in agg}
    assert by["m1"]["average_rank"] == 1.5
    assert by["m3"]["average_rank"] == 3.0
    assert agg[-1]["model"] == "m3"  # worst is last
    assert by["m1"]["rankings_count"] == 2


def test_aggregate_handles_unparseable_rankings():
    assert council.calculate_aggregate_rankings(
        [{"model": "m1", "ranking": "no ranking here"}], {"Response A": "m1"}
    ) == []


# --- Stage 3 + safety net ----------------------------------------------------
async def test_stage3_applies_emergency_for_newborn_fever(monkeypatch):
    async def fake_qm(model, messages, **kw):
        return _resp("일반적인 조언입니다.")

    monkeypatch.setattr(council, "query_model", fake_qm)
    stage0 = {"evidence_brief": "e", "sources": [{"url": "https://who.int/a", "title": "WHO"}]}
    stage1 = [{"model": "m", "response": "r", "sources": stage0["sources"]}]
    out = await council.stage3_synthesize_final(
        "Child age: 신생아 (0–3개월). Question: 아기 열이 38.5도예요", stage1, [], stage0, age_days=40
    )
    assert out["response"].count("응급:") == 1
    assert out["sources"] == stage0["sources"]


async def test_stage3_idempotent_when_model_already_has_emergency(monkeypatch):
    async def fake_qm(model, messages, **kw):
        return _resp("> 응급: 이미 응급 안내가 있습니다\n\n본문 내용")

    monkeypatch.setattr(council, "query_model", fake_qm)
    out = await council.stage3_synthesize_final(
        "Child age: 신생아. Question: 38도 열", [{"model": "m", "response": "r", "sources": []}],
        [], {"evidence_brief": "", "sources": []}, age_days=40,
    )
    assert out["response"].count("응급:") == 1  # NOT doubled (Hangul-safe regex)


async def test_stage3_no_emergency_for_benign_but_disclaimer_added(monkeypatch):
    async def fake_qm(model, messages, **kw):
        return _resp("낮잠 전환 조언입니다.")

    monkeypatch.setattr(council, "query_model", fake_qm)
    out = await council.stage3_synthesize_final(
        "Child age: 유아 (1–3세). Question: 낮잠 전환", [{"model": "m", "response": "r", "sources": []}],
        [], {"evidence_brief": "", "sources": []}, age_days=730,
    )
    assert "> 응급:" not in out["response"]
    assert KO_DISCLAIMER in out["response"]


async def test_stage3_consolidates_sources_deduped(monkeypatch):
    async def fake_qm(model, messages, **kw):
        return _resp("답변")

    monkeypatch.setattr(council, "query_model", fake_qm)
    stage0 = {"evidence_brief": "e", "sources": [{"url": "https://who.int/a", "title": "WHO"}]}
    stage1 = [{"model": "m", "response": "r", "sources": [
        {"url": "https://who.int/a", "title": "WHO"}, {"url": "https://cdc.gov/b", "title": "CDC"},
    ]}]
    out = await council.stage3_synthesize_final("q", stage1, [], stage0, age_days=None)
    assert [s["url"] for s in out["sources"]] == ["https://who.int/a", "https://cdc.gov/b"]


async def test_stage3_fallback_on_model_failure(monkeypatch):
    async def fake_qm(model, messages, **kw):
        return None

    monkeypatch.setattr(council, "query_model", fake_qm)
    out = await council.stage3_synthesize_final(
        "q", [{"model": "m", "response": "r", "sources": []}], [], {"evidence_brief": "", "sources": []},
        age_days=None,
    )
    assert out["model"] == council.CHAIRMAN_MODEL and "Error" in out["response"]


# --- title generation --------------------------------------------------------
async def test_generate_title_fallback_on_failure(monkeypatch):
    async def fake_qm(model, messages, **kw):
        return None

    monkeypatch.setattr(council, "query_model", fake_qm)
    assert await council.generate_conversation_title("q") == "New Conversation"


async def test_generate_title_strips_quotes(monkeypatch):
    async def fake_qm(model, messages, **kw):
        return _resp('"신생아 발열 질문"')

    monkeypatch.setattr(council, "query_model", fake_qm)
    assert await council.generate_conversation_title("q") == "신생아 발열 질문"
