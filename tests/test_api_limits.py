"""HTTP-layer tests for the cost/abuse floor (WS-4) + health/readiness (WS-6) + idempotency.

The pipeline (run_full_council) is monkeypatched so no LLM is called; the limit/validation
paths (422/413/403/401/429) short-circuit before the pipeline anyway.
"""

import backend.main as main
from fastapi.testclient import TestClient

from backend.main import app
from backend.accounts import AccountStore
from backend.storage_backend import JsonStorageBackend
from backend.quota import DailyQuota

CSRF = {"X-Requested-With": "parenting-roundtable"}


def _setup(tmp_path, monkeypatch, require_auth=False):
    monkeypatch.setattr(main, "store", JsonStorageBackend(str(tmp_path)))
    monkeypatch.setattr(main, "accounts", AccountStore(str(tmp_path)))
    monkeypatch.setattr(main, "quota", DailyQuota(str(tmp_path)))
    monkeypatch.setattr(main, "REQUIRE_AUTH", require_auth)
    main.limiter.reset()  # rate-limit counters are process-global; isolate each test


def _new_conv(client):
    return client.post("/api/conversations", json={}).json()["id"]


def test_oversized_content_returns_422(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    c = TestClient(app)
    cid = _new_conv(c)
    r = c.post(f"/api/conversations/{cid}/message", json={"content": "x" * 6000}, headers=CSRF)
    assert r.status_code == 422


def test_request_too_large_returns_413(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    c = TestClient(app)
    cid = _new_conv(c)
    # Body exceeds MAX_REQUEST_BYTES (200KB) -> size middleware 413s before routing/validation.
    r = c.post(f"/api/conversations/{cid}/message", json={"content": "x" * 200_001}, headers=CSRF)
    assert r.status_code == 413


def test_missing_csrf_header_returns_403(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    c = TestClient(app)
    cid = _new_conv(c)
    assert c.post(f"/api/conversations/{cid}/message", json={"content": "안녕"}).status_code == 403


def test_anonymous_message_401_when_auth_required(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, require_auth=True)
    c = TestClient(app)
    cid = _new_conv(c)
    r = c.post(f"/api/conversations/{cid}/message", json={"content": "안녕"}, headers=CSRF)
    assert r.status_code == 401


def test_rate_limit_429_after_threshold(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    c = TestClient(app)
    # Target a non-existent conversation: each call passes the limiter (increment) then 404s,
    # so the pipeline never runs. The 11th call within the window trips the 10/minute limit.
    responses = [
        c.post("/api/conversations/nope/message", json={"content": "hi"}, headers=CSRF)
        for _ in range(11)
    ]
    assert [r.status_code for r in responses[:10]] == [404] * 10
    assert responses[10].status_code == 429
    # 429 must carry Retry-After so clients know when to retry.
    assert "retry-after" in {k.lower() for k in responses[10].headers}


def test_health_and_ready(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main, "OPENROUTER_API_KEY", "test-key")
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    r = c.get("/ready")
    assert r.status_code == 200 and r.json()["ready"] is True


def test_ready_503_without_api_key(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main, "OPENROUTER_API_KEY", None)
    c = TestClient(app)
    r = c.get("/ready")
    assert r.status_code == 503 and r.json()["ready"] is False


def test_security_headers_present(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = TestClient(app).get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "X-Request-ID" in r.headers


def test_message_happy_path_and_idempotent_replay(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    calls = {"n": 0}
    s0 = {"evidence_brief": "e", "sources": []}
    s3 = {"model": "chair", "response": "최종 답변", "sources": []}

    async def fake_run(content, age_days):
        calls["n"] += 1
        return s0, [{"model": "m", "response": "r", "sources": []}], [], s3, {"label_to_model": {}}

    async def fake_title(q):
        return "제목"

    monkeypatch.setattr(main, "run_full_council", fake_run)
    monkeypatch.setattr(main, "generate_conversation_title", fake_title)

    c = TestClient(app)
    cid = _new_conv(c)
    body = {"content": "토들러 수면 질문", "age_days": 730, "idempotency_key": "key-1"}
    r1 = c.post(f"/api/conversations/{cid}/message", json=body, headers=CSRF)
    assert r1.status_code == 200 and r1.json()["stage3"]["response"] == "최종 답변"

    # Same idempotency key -> replayed from storage, pipeline NOT run again.
    r2 = c.post(f"/api/conversations/{cid}/message", json=body, headers=CSRF)
    assert r2.status_code == 200 and r2.json().get("replayed") is True
    assert calls["n"] == 1
