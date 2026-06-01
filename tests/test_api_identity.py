"""HTTP-layer tests for Phase 2 identity: providers, children, consents, OAuth callback."""

from urllib.parse import urlparse, parse_qs

from fastapi.testclient import TestClient

from backend.main import app
from backend.accounts import AccountStore, REQUIRED_CONSENTS


def _patch_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.main.accounts", AccountStore(str(tmp_path)))


def test_providers_disabled_by_default(tmp_path, monkeypatch):
    _patch_accounts(tmp_path, monkeypatch)
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    c = TestClient(app)
    assert c.get("/api/auth/providers").json() == {"kakao": False, "naver": False}


def test_children_crud_and_isolation(tmp_path, monkeypatch):
    _patch_accounts(tmp_path, monkeypatch)
    c1 = TestClient(app)
    r = c1.post("/api/children", json={"name": "아기", "birthdate": "2024-06-01"})
    assert r.status_code == 200
    child = r.json()
    assert child["age_days"] is not None
    assert [x["id"] for x in c1.get("/api/children").json()] == [child["id"]]
    # A separate client (fresh session) sees no children.
    c2 = TestClient(app)
    assert c2.get("/api/children").json() == []


def test_child_bad_birthdate_rejected(tmp_path, monkeypatch):
    _patch_accounts(tmp_path, monkeypatch)
    c = TestClient(app)
    assert c.post("/api/children", json={"name": "x", "birthdate": "nope"}).status_code == 400


def test_consents_endpoint(tmp_path, monkeypatch):
    _patch_accounts(tmp_path, monkeypatch)
    c = TestClient(app)
    assert c.get("/api/consents").json()["has_required"] is False
    r = c.post("/api/consents", json={"kinds": REQUIRED_CONSENTS, "version": "1.0"})
    assert r.json()["has_required"] is True


def test_login_404_when_provider_disabled(tmp_path, monkeypatch):
    _patch_accounts(tmp_path, monkeypatch)
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    c = TestClient(app)
    assert c.get("/api/auth/kakao/login", follow_redirects=False).status_code == 404


def test_me_anonymous(tmp_path, monkeypatch):
    _patch_accounts(tmp_path, monkeypatch)
    me = TestClient(app).get("/api/auth/me").json()
    assert me["authenticated"] is False and me["providers"] == []


def test_callback_links_identity_in_place(tmp_path, monkeypatch):
    _patch_accounts(tmp_path, monkeypatch)
    monkeypatch.setattr("backend.main.oauth.provider_enabled", lambda p: True)

    async def fake_exchange(provider, code, state, verifier=None):
        return "tok"

    async def fake_userinfo(provider, token):
        return {"provider_user_id": "K1", "display_name": "민지"}

    monkeypatch.setattr("backend.main.oauth.exchange_code", fake_exchange)
    monkeypatch.setattr("backend.main.oauth.fetch_userinfo", fake_userinfo)
    monkeypatch.setenv("KAKAO_REST_API_KEY", "k")
    monkeypatch.setenv("KAKAO_REDIRECT_URI", "https://app/cb")

    c = TestClient(app)
    login = c.get("/api/auth/kakao/login", follow_redirects=False)
    assert login.status_code == 302
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]

    cb = c.get(f"/api/auth/kakao/callback?code=abc&state={state}", follow_redirects=False)
    assert cb.status_code == 302 and "login=ok" in cb.headers["location"]

    me = c.get("/api/auth/me").json()
    assert me["authenticated"] is True
    assert me["display_name"] == "민지"
    assert me["providers"] == ["kakao"]


def test_callback_rejects_state_mismatch(tmp_path, monkeypatch):
    _patch_accounts(tmp_path, monkeypatch)
    monkeypatch.setattr("backend.main.oauth.provider_enabled", lambda p: True)
    monkeypatch.setenv("KAKAO_REST_API_KEY", "k")
    monkeypatch.setenv("KAKAO_REDIRECT_URI", "https://app/cb")
    c = TestClient(app)
    c.get("/api/auth/kakao/login", follow_redirects=False)  # sets a state cookie
    # Wrong state -> CSRF guard rejects to login=error, no identity linked.
    cb = c.get("/api/auth/kakao/callback?code=abc&state=WRONG", follow_redirects=False)
    assert cb.status_code == 302 and "login=error" in cb.headers["location"]
    assert c.get("/api/auth/me").json()["authenticated"] is False
