"""End-to-end (mocked) tests of run_full_council across the three pilot scenarios.

Uses the client-prefixed content shape the backend actually receives
("Child age: ... . Question: ...", ChatInterface.jsx) — not a bare query.
"""

import backend.council as council
from backend.safety import KO_DISCLAIMER

_RANKING = "평가\n\nFINAL RANKING:\n1. Response A\n2. Response B\n3. Response C"


def _install_mocks(monkeypatch, one_model_none=False):
    annotations = [{"type": "url_citation", "url_citation": {"url": "https://who.int/a", "title": "WHO"}}]

    async def fake_query_model(model, messages, **kw):
        if kw.get("web_search"):  # Stage 0 researcher
            return {"content": "근거 요약", "reasoning_details": None, "annotations": annotations}
        if model == "google/gemini-2.5-flash":  # title
            return {"content": "제목", "reasoning_details": None, "annotations": None}
        return {"content": "최종 합의 답변입니다.", "reasoning_details": None, "annotations": None}  # chairman

    async def fake_parallel(models, messages, **kw):
        is_ranking = "FINAL RANKING" in messages[-1]["content"]
        out = {}
        for i, m in enumerate(models):
            if one_model_none and i == 1 and not is_ranking:
                out[m] = None
            else:
                content = _RANKING if is_ranking else f"패널 답변 {i}"
                out[m] = {"content": content, "reasoning_details": None, "annotations": None}
        return out

    monkeypatch.setattr(council, "query_model", fake_query_model)
    monkeypatch.setattr(council, "query_models_parallel", fake_parallel)


async def test_run_full_council_benign(monkeypatch):
    _install_mocks(monkeypatch)
    s0, s1, s2, s3, meta = await council.run_full_council(
        "Child age: 유아 (1–3세). Question: 낮잠 전환은 어떻게 하나요", 730
    )
    assert "> 응급:" not in s3["response"]
    assert KO_DISCLAIMER in s3["response"]
    assert len(s1) == len(council.COUNCIL_MODELS) and len(s2) == len(council.COUNCIL_MODELS)
    assert "aggregate_rankings" in meta and "label_to_model" in meta
    assert s0["sources"] == [{"url": "https://who.int/a", "title": "WHO"}]


async def test_run_full_council_newborn_fever_emergency(monkeypatch):
    _install_mocks(monkeypatch)
    _, _, _, s3, _ = await council.run_full_council(
        "Child age: 신생아 (0–3개월). Question: 아기 열이 38.5도예요", 40
    )
    assert s3["response"].count("응급:") == 1  # exactly one emergency callout


async def test_run_full_council_graceful_degradation(monkeypatch):
    _install_mocks(monkeypatch, one_model_none=True)
    _, s1, _, s3, _ = await council.run_full_council(
        "Child age: 영아 (3–12개월). Question: 이유식 시작", 200
    )
    assert len(s1) == len(council.COUNCIL_MODELS) - 1  # the failed model is skipped
    assert s3["response"]  # still synthesizes a final answer
