"""Minimal OAuth authorization server for the council MCP endpoint.

claude.ai custom connectors require OAuth - they attempt Dynamic Client
Registration against the server and refuse to connect without it. A URL secret
alone is not enough.

This is a single-operator authorization server. Clients register themselves via
DCR; the human is authenticated by one shared passphrase on a consent page. That
passphrase is the only thing standing between the open internet and four billing
accounts, so COUNCIL_PASSPHRASE must be set and long.

ponytail: all state is in-memory and capped. Tokens are lost on redeploy, which
means reconnecting the connector - acceptable for one operator, and far simpler
than a token table. Move to pg if this ever serves more than one person.
"""

import secrets
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

CODE_TTL = 300           # 5 minutes, per OAuth guidance
ACCESS_TTL = 30 * 86400  # 30 days - a shorter window just means more reconnects
_MAX = 64                # cap every store; this serves one person


def _cap(store: Dict[str, Any]) -> None:
    while len(store) > _MAX:
        store.pop(next(iter(store)))


class PassphraseAuthProvider(OAuthAuthorizationServerProvider):
    """OAuth AS where the human gate is one shared passphrase."""

    def __init__(self, passphrase: str, public_url: str) -> None:
        if not passphrase:
            raise RuntimeError(
                "COUNCIL_PASSPHRASE is not set. Refusing to start an OAuth server "
                "that would let anyone who finds the URL spend your API credit."
            )
        self.passphrase = passphrase
        self.public_url = public_url.rstrip("/")
        self.clients: Dict[str, OAuthClientInformationFull] = {}
        self.codes: Dict[str, AuthorizationCode] = {}
        self.tokens: Dict[str, AccessToken] = {}
        self.refresh: Dict[str, RefreshToken] = {}
        self.pending: Dict[str, Dict[str, Any]] = {}

    # --- client registration (DCR) ---

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.clients[client_info.client_id] = client_info
        _cap(self.clients)

    # --- authorization ---

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Park the request and send the human to the consent page."""
        rid = secrets.token_urlsafe(24)
        self.pending[rid] = {"client_id": client.client_id, "params": params}
        _cap(self.pending)
        return f"{self.public_url}/consent?{urlencode({'rid': rid})}"

    def complete(self, rid: str) -> Optional[str]:
        """Passphrase accepted - mint a code and return the client redirect."""
        req = self.pending.pop(rid, None)
        if req is None:
            return None
        params: AuthorizationParams = req["params"]
        code = AuthorizationCode(
            code=secrets.token_urlsafe(32),
            scopes=params.scopes or [],
            expires_at=time.time() + CODE_TTL,
            client_id=req["client_id"],
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        self.codes[code.code] = code
        _cap(self.codes)
        return construct_redirect_uri(
            str(params.redirect_uri), code=code.code, state=params.state
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> Optional[AuthorizationCode]:
        code = self.codes.get(authorization_code)
        if code is None or code.client_id != client.client_id:
            return None
        if code.expires_at < time.time():
            self.codes.pop(authorization_code, None)
            return None
        return code

    # --- token issuance ---

    def _issue(self, client_id: str, scopes: List[str], resource: Any) -> OAuthToken:
        access = AccessToken(
            token=secrets.token_urlsafe(32),
            client_id=client_id,
            scopes=scopes,
            expires_at=int(time.time() + ACCESS_TTL),
            resource=resource,
        )
        refresh = RefreshToken(
            token=secrets.token_urlsafe(32),
            client_id=client_id,
            scopes=scopes,
            expires_at=None,
        )
        self.tokens[access.token] = access
        self.refresh[refresh.token] = refresh
        _cap(self.tokens)
        _cap(self.refresh)
        return OAuthToken(
            access_token=access.token,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            refresh_token=refresh.token,
            scope=" ".join(scopes) if scopes else None,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self.codes.pop(authorization_code.code, None)  # single use
        return self._issue(
            client.client_id, authorization_code.scopes, authorization_code.resource
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> Optional[RefreshToken]:
        tok = self.refresh.get(refresh_token)
        return tok if tok and tok.client_id == client.client_id else None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: List[str],
    ) -> OAuthToken:
        self.refresh.pop(refresh_token.token, None)  # rotate
        return self._issue(client.client_id, scopes or refresh_token.scopes, None)

    async def exchange_identity_assertion(self, client, params) -> OAuthToken:
        raise NotImplementedError("Identity assertion is not supported.")

    # --- token use / revocation ---

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        tok = self.tokens.get(token)
        if tok is None:
            return None
        if tok.expires_at and tok.expires_at < time.time():
            self.tokens.pop(token, None)
            return None
        return tok

    async def revoke_token(self, token: Any) -> None:
        self.tokens.pop(getattr(token, "token", ""), None)
        self.refresh.pop(getattr(token, "token", ""), None)


_PAGE = """<!doctype html><meta charset=utf-8>
<title>LLM Council - connect</title>
<style>
 body{font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6;
      display:grid;place-items:center;height:100vh;margin:0}
 form{background:#171a21;padding:2rem;border-radius:12px;width:min(92vw,26rem)}
 h1{font-size:1.1rem;margin:0 0 .4rem} p{color:#9aa0aa;font-size:.85rem;margin:0 0 1.2rem}
 input{width:100%;padding:.7rem;border-radius:8px;border:1px solid #2b303a;
       background:#0f1115;color:inherit;box-sizing:border-box}
 button{width:100%;padding:.7rem;margin-top:.8rem;border:0;border-radius:8px;
        background:#4a90e2;color:#fff;font-weight:600;cursor:pointer}
 .err{color:#ff6b6b;font-size:.85rem;margin-top:.6rem}
</style>
<form method=post action="/consent">
  <h1>Connect to your LLM Council</h1>
  <p>Enter the passphrase to authorise this client.</p>
  <input type=hidden name=rid value="__RID__">
  <input type=password name=passphrase placeholder="Passphrase" autofocus required>
  <button type=submit>Authorise</button>
  __ERROR__
</form>"""


def _page(rid: str, error: str = "") -> str:
    return _PAGE.replace("__RID__", rid).replace("__ERROR__", error)


def register_routes(mcp: Any, provider: PassphraseAuthProvider) -> None:
    """Attach the consent page to the MCP server's Starlette app."""

    @mcp.custom_route("/consent", methods=["GET"])
    async def consent_form(request: Request) -> HTMLResponse:
        rid = request.query_params.get("rid", "")
        if rid not in provider.pending:
            return HTMLResponse(
                "<p>This authorisation link has expired. Start the connection again.</p>",
                status_code=400,
            )
        return HTMLResponse(_page(rid))

    @mcp.custom_route("/consent", methods=["POST"])
    async def consent_submit(request: Request):
        form = await request.form()
        rid = str(form.get("rid", ""))
        supplied = str(form.get("passphrase", ""))

        if not secrets.compare_digest(supplied, provider.passphrase):
            # Do not consume the pending request - let them retype.
            if rid in provider.pending:
                return HTMLResponse(
                    _page(rid, '<div class="err">Incorrect passphrase.</div>'),
                    status_code=401,
                )
            return HTMLResponse("<p>This authorisation link has expired.</p>", status_code=400)

        target = provider.complete(rid)
        if target is None:
            return HTMLResponse("<p>This authorisation link has expired.</p>", status_code=400)
        return RedirectResponse(target, status_code=302)
