"""HTTP-layer tests for anonymous-session identity + tenancy enforcement.

These exercise the FastAPI dependency wiring (cookie issuance, per-user isolation)
without invoking the LLM pipeline. Uses a temp storage dir via monkeypatch.
"""

from fastapi.testclient import TestClient

from backend.main import app
from backend.storage_backend import JsonStorageBackend


def test_anon_session_issued_and_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.main.store", JsonStorageBackend(str(tmp_path)))

    # Client 1 creates a conversation — server issues an anonymous session cookie.
    c1 = TestClient(app)
    r = c1.post("/api/conversations", json={})
    assert r.status_code == 200
    cid = r.json()["id"]
    assert "pr_uid" in r.cookies  # signed anonymous identity issued

    # Client 1 sees its own conversation.
    listed = c1.get("/api/conversations").json()
    assert [x["id"] for x in listed] == [cid]
    assert c1.get(f"/api/conversations/{cid}").status_code == 200

    # A separate client (fresh cookie jar) cannot see or fetch it.
    c2 = TestClient(app)
    assert c2.get("/api/conversations").json() == []
    assert c2.get(f"/api/conversations/{cid}").status_code == 404


def test_session_persists_across_requests(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.main.store", JsonStorageBackend(str(tmp_path)))
    client = TestClient(app)
    first = client.post("/api/conversations", json={}).json()["id"]
    second = client.post("/api/conversations", json={}).json()["id"]
    # Same cookie jar → same user → both conversations visible.
    ids = {x["id"] for x in client.get("/api/conversations").json()}
    assert ids == {first, second}
