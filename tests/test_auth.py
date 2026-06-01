"""Tests for the session-secret fail-fast and environment-driven cookie flags (WS-1)."""

import pytest
from fastapi import Response

from backend import auth


def test_sign_verify_roundtrip_and_tamper():
    token = auth._sign("user123")
    assert auth._verify(token) == "user123"
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert auth._verify(tampered) is None
    assert auth._verify("garbage-no-dot") is None
    assert auth._verify(None) is None


def test_verify_payload_rejects_bad_signature_and_garbage():
    signed = auth.sign_payload({"a": 1})
    assert auth.verify_payload(signed) == {"a": 1}
    assert auth.verify_payload(signed[:-1] + "x") is None
    assert auth.verify_payload("not-a-token") is None


def test_load_session_secret_valid_passthrough():
    good = "x" * 40
    assert auth._load_session_secret(good, is_production=True) == good
    assert auth._load_session_secret(good, is_production=False) == good


def test_load_session_secret_production_fails_fast():
    with pytest.raises(SystemExit):
        auth._load_session_secret(None, is_production=True)
    with pytest.raises(SystemExit):
        auth._load_session_secret("", is_production=True)
    with pytest.raises(SystemExit):
        auth._load_session_secret("dev-insecure-secret-change-me", is_production=True)
    with pytest.raises(SystemExit):
        auth._load_session_secret("too-short", is_production=True)


def test_load_session_secret_dev_falls_back_to_ephemeral():
    s = auth._load_session_secret(None, is_production=False)
    assert isinstance(s, str) and len(s) >= 32
    # Each dev fallback is unique (ephemeral, not a fixed placeholder).
    assert s != auth._load_session_secret(None, is_production=False)


def test_cookie_flags_production(monkeypatch):
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    assert auth.cookie_security_kwargs() == {"httponly": True, "secure": True, "samesite": "none"}


def test_cookie_flags_dev(monkeypatch):
    monkeypatch.setattr(auth, "IS_PRODUCTION", False)
    flags = auth.cookie_security_kwargs()
    assert flags["samesite"] == "lax" and flags["secure"] is False and flags["httponly"] is True


def test_set_session_cookie_production_header(monkeypatch):
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    r = Response()
    auth.set_session_cookie(r, "u1")
    set_cookie = r.headers["set-cookie"].lower()
    assert "secure" in set_cookie
    assert "samesite=none" in set_cookie
    assert "httponly" in set_cookie
