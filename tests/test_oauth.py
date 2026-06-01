"""Tests for the OAuth provider module (parsers, PKCE, authorize URL, mocked exchange)."""

import asyncio
import base64
import hashlib

import backend.oauth as oauth


def test_pkce_challenge_matches_verifier():
    p = oauth.make_pkce()
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(p["verifier"].encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert p["challenge"] == expected


def test_userinfo_parsers():
    k = oauth._parse_kakao({"id": 777, "kakao_account": {"profile": {"nickname": "민지"}}})
    assert k == {"provider_user_id": "777", "display_name": "민지"}
    n = oauth._parse_naver({"response": {"id": "N9", "nickname": "현우", "name": "김현우"}})
    assert n == {"provider_user_id": "N9", "display_name": "현우"}


def test_provider_enabled_env(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    monkeypatch.delenv("KAKAO_REDIRECT_URI", raising=False)
    assert oauth.provider_enabled("kakao") is False
    monkeypatch.setenv("KAKAO_REST_API_KEY", "key")
    monkeypatch.setenv("KAKAO_REDIRECT_URI", "https://app/callback")
    assert oauth.provider_enabled("kakao") is True


def test_build_authorize_url(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "key123")
    monkeypatch.setenv("KAKAO_REDIRECT_URI", "https://app/cb")
    url = oauth.build_authorize_url("kakao", "st8", "chal")
    assert "client_id=key123" in url
    assert "state=st8" in url
    assert "code_challenge=chal" in url
    assert "code_challenge_method=S256" in url


def test_exchange_and_userinfo_mocked(monkeypatch):
    class _Resp:
        def __init__(self, data):
            self._d = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._d

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **k):
            return _Resp({"access_token": "tok"})

        async def get(self, url, **k):
            return _Resp({"id": 5, "properties": {"nickname": "윤서"}})

    monkeypatch.setattr(oauth.httpx, "AsyncClient", _Client)
    monkeypatch.setenv("KAKAO_REST_API_KEY", "k")
    monkeypatch.setenv("KAKAO_REDIRECT_URI", "https://app/cb")

    assert asyncio.run(oauth.exchange_code("kakao", "code", "state", "verifier")) == "tok"
    assert asyncio.run(oauth.fetch_userinfo("kakao", "tok")) == {
        "provider_user_id": "5",
        "display_name": "윤서",
    }
