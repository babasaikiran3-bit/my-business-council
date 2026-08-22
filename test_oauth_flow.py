"""Walk the full OAuth flow against a locally running council server.

Run the server first:
  MCP_TRANSPORT=streamable-http PORT=8099 PUBLIC_URL=http://127.0.0.1:8099 \
  COUNCIL_PASSPHRASE=localtestphrase uv run python -m backend.mcp_server

Then: uv run --system-certs python test_oauth_flow.py
Makes no model calls.
"""

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import httpx

BASE = "http://127.0.0.1:8099"
PASSPHRASE = "localtestphrase"
REDIRECT = "http://localhost:9999/callback"


def main() -> None:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")

    with httpx.Client(follow_redirects=False, timeout=20.0) as c:
        reg = c.post(f"{BASE}/register", json={
            "client_name": "flow-test",
            "redirect_uris": [REDIRECT],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        })
        assert reg.status_code in (200, 201), f"DCR failed: {reg.status_code} {reg.text[:200]}"
        client = reg.json()
        print("ok  dynamic client registration ->", client["client_id"][:12] + "...")

        auth = c.get(f"{BASE}/authorize", params={
            "response_type": "code",
            "client_id": client["client_id"],
            "redirect_uri": REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "teststate",
        })
        assert auth.status_code in (302, 307), f"authorize: {auth.status_code} {auth.text[:200]}"
        rid = parse_qs(urlparse(auth.headers["location"]).query)["rid"][0]
        print("ok  /authorize redirected to consent")

        assert c.get(f"{BASE}/consent", params={"rid": rid}).status_code == 200
        print("ok  consent page renders")

        bad = c.post(f"{BASE}/consent", data={"rid": rid, "passphrase": "wrong"})
        assert bad.status_code == 401, f"wrong passphrase should 401, got {bad.status_code}"
        print("ok  wrong passphrase rejected (401)")

        good = c.post(f"{BASE}/consent", data={"rid": rid, "passphrase": PASSPHRASE})
        assert good.status_code == 302, f"consent: {good.status_code} {good.text[:200]}"
        q = parse_qs(urlparse(good.headers["location"]).query)
        assert q["state"][0] == "teststate", "state must round-trip"
        code = q["code"][0]
        print("ok  passphrase accepted, code issued, state preserved")

        tok = c.post(f"{BASE}/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": client["client_id"],
            "client_secret": client.get("client_secret", ""),
            "code_verifier": verifier,
        })
        assert tok.status_code == 200, f"token: {tok.status_code} {tok.text[:300]}"
        access = tok.json()["access_token"]
        print("ok  code exchanged for access token")

        reuse = c.post(f"{BASE}/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": client["client_id"],
            "client_secret": client.get("client_secret", ""), "code_verifier": verifier,
        })
        assert reuse.status_code >= 400, "authorization code must be single-use"
        print("ok  code replay rejected")

        r = c.post(f"{BASE}/mcp",
            headers={
                "Authorization": f"Bearer {access}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "flow-test", "version": "1"},
            }})
        assert r.status_code == 200, f"authenticated initialize failed: {r.status_code} {r.text[:200]}"
        print("ok  authenticated MCP initialize accepted")

    print("\nPASSED")


if __name__ == "__main__":
    main()
