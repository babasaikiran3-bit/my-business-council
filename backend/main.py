"""FastAPI backend for Parenting Roundtable."""

import asyncio
import json
import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import auth, oauth
from .accounts import ALL_CONSENTS, REQUIRED_CONSENTS, accounts, age_days_from_birthdate
from .auth import get_current_user
from .config import (
    CORS_ORIGINS,
    CSRF_HEADER,
    CSRF_HEADER_VALUE,
    FRONTEND_URL,
    IS_PRODUCTION,
    MAX_MESSAGE_CHARS,
    MAX_REQUEST_BYTES,
    OPENROUTER_API_KEY,
    PIPELINE_TIMEOUT,
    RATE_LIMIT_AUTH,
    RATE_LIMIT_MESSAGES,
    STAGE0_TIMEOUT,
    STAGE1_TIMEOUT,
    STAGE2_TIMEOUT,
    STAGE3_TIMEOUT,
    TITLE_TIMEOUT,
    DATA_DIR,
    validate_runtime_config,
)
from .council import (
    calculate_aggregate_rankings,
    generate_conversation_title,
    run_full_council,
    stage0_research,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
)
from .logging_config import configure_logging, trace_id_var
from .quota import quota
from .safety import KO_DISCLAIMER, assess_emergency
from .storage_backend import StorageCorruptionError, store

configure_logging()
logger = logging.getLogger("parenting_roundtable.main")

OAUTH_COOKIE = "pr_oauth"

# In production every message maps to a real (logged-in) account, so a single user can't
# bypass the daily quota by dropping their cookie to mint a fresh anon id. Overridable for
# local dev / tests where OAuth providers aren't configured.
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH_FOR_MESSAGES", "true" if IS_PRODUCTION else "false").lower() in (
    "1", "true", "yes",
)

# User-facing, non-leaky messages (never expose str(exception) to the client).
GENERIC_ERROR_KO = "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
INCOMPLETE_KO = "답변 생성이 중간에 중단되었어요. 잠시 후 다시 시도해 주세요."


def _validate_frontend_url() -> None:
    """In production the OAuth post-login redirect target must be an allowlisted https origin."""
    if not IS_PRODUCTION:
        return
    parsed = urlparse(FRONTEND_URL)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.scheme != "https" or origin not in CORS_ORIGINS:
        raise SystemExit(
            f"FRONTEND_URL ({FRONTEND_URL!r}) must be an https origin present in CORS_ORIGINS in production"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_config()
    _validate_frontend_url()
    for provider in oauth.PROVIDERS:
        if oauth.provider_enabled(provider):
            cfg = oauth.provider_config(provider)
            redirect_uri = os.getenv(cfg["redirect_uri_env"], "")
            if IS_PRODUCTION and not redirect_uri.startswith("https://"):
                raise SystemExit(f"{provider} redirect_uri must be https in production")
            logger.info("oauth provider enabled", extra={"provider": provider, "redirect_uri": redirect_uri})
    logger.info("startup", extra={"environment": "production" if IS_PRODUCTION else "dev",
                                  "data_dir": os.path.abspath(DATA_DIR), "require_auth": REQUIRE_AUTH})
    yield
    logger.info("draining")  # graceful shutdown: in-flight SSE generators persist on close


app = FastAPI(title="Parenting Roundtable API", lifespan=lifespan)


# --- Rate limiting (slowapi; in-memory, single-worker — daily quota is the hard ceiling) ---
def _rate_key(request: Request) -> str:
    """Key limits on the signed user_id when present, else the client IP (pre-mint/anon)."""
    uid = auth._verify(request.cookies.get(auth.COOKIE_NAME))
    return uid or get_remote_address(request)


# headers_enabled=True so the 429 carries Retry-After (+ X-RateLimit-*) for clients.
limiter = Limiter(key_func=_rate_key, headers_enabled=True)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(StorageCorruptionError)
async def _storage_corruption_handler(request: Request, exc: StorageCorruptionError):
    logger.error("storage corruption", extra={"path": str(exc)})
    return JSONResponse(status_code=500, content={"detail": GENERIC_ERROR_KO})


# --- CORS (env-driven, credentialed; explicit headers because '*' is invalid with creds) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With", "X-Request-ID"],
)


@app.middleware("http")
async def trace_size_and_security_headers(request: Request, call_next):
    # Trace id: propagate an inbound X-Request-ID or mint one; echo it back.
    trace = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = trace_id_var.set(trace)
    try:
        # Best-effort size cap: trusts the Content-Length header (a chunked client could
        # understate it). Sufficient for a trusted pilot; the Pydantic max_length on message
        # content is the authoritative guard for the hot path.
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Request too large"})
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
    finally:
        trace_id_var.reset(token)


# --- Shared dependencies -----------------------------------------------------
def require_csrf(request: Request) -> None:
    """Reject state-changing requests lacking the SPA's custom header (CSRF defense)."""
    if request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF header")


def require_authenticated_user(user_id: str = Depends(get_current_user)) -> str:
    """Like get_current_user, but 401s anonymous callers when REQUIRE_AUTH is on (production)."""
    if REQUIRE_AUTH and not accounts.is_authenticated(user_id):
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    # Typed child age in days — drives the deterministic safety triage/backstop.
    age_days: Optional[int] = Field(None, ge=0, le=12000)
    # When set, age_days is derived server-side from this saved child's birthdate.
    child_profile_id: Optional[str] = None
    # Client-generated per-send UUID: a repeat with the same key replays the stored
    # answer instead of re-running ~8 paid LLM calls (double-charge / double-submit guard).
    idempotency_key: Optional[str] = None


def _resolve_age_days(user_id: str, payload: "SendMessageRequest") -> Optional[int]:
    """Prefer a saved child profile's birthdate-derived age; fall back to the typed age."""
    if payload.child_profile_id:
        child = accounts.get_child(user_id, payload.child_profile_id)
        if child:
            derived = age_days_from_birthdate(child["birthdate"])
            if derived is not None:
                return derived
    return payload.age_days


def _emergency_stage3(triage: Dict[str, Any]) -> Dict[str, Any]:
    """Build a synthetic Stage 3 carrying the deterministic Korean emergency interstitial."""
    numbers = " · ".join(triage.get("numbers", []))
    body = f"> 응급: {triage['message_ko']}"
    if numbers:
        body += f"\n\n**지금 연락하세요:** {numbers}"
    body += f"\n\n{KO_DISCLAIMER}"
    return {"model": "safety-triage", "response": body, "sources": [], "emergency": triage}


_EMPTY_STAGE0 = {"evidence_brief": "", "sources": []}


def _find_assistant_by_idempotency(conversation: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    for msg in reversed(conversation.get("messages", [])):
        if msg.get("role") == "assistant" and msg.get("idempotency_key") == key:
            return msg
    return None


async def _persist_partial(
    user_id: str, conversation_id: str,
    stage0: Optional[Dict[str, Any]], stage1: Optional[List[Dict[str, Any]]],
    stage2: Optional[List[Dict[str, Any]]], idempotency_key: Optional[str] = None,
) -> None:
    """Persist whatever stages completed plus an 'incomplete' note, marked short_circuit.

    On reload the parent keeps the Stage 0/1 they already saw via SSE; the empty later
    stages are skipped (no broken empty panels) because the message is short_circuit.
    """
    note = {"model": "incomplete", "response": INCOMPLETE_KO, "sources": []}
    await store.append_assistant_message(
        user_id, conversation_id,
        stage0 or _EMPTY_STAGE0, stage1 or [], stage2 or [], note,
        short_circuit=True, idempotency_key=idempotency_key,
    )


def _data_dir_writable() -> bool:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        probe = os.path.join(DATA_DIR, f".readyprobe.{uuid.uuid4().hex}")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


class ConversationMetadata(BaseModel):
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


# --- Health / readiness ------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ok", "service": "Parenting Roundtable API"}


@app.get("/health")
async def health():
    """Liveness: always 200 if the process is up (PaaS health target)."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness: 200 only if the key is present, the secret is valid, and DATA_DIR is
    writable (directly verifies the WS-3 persistent-disk requirement). Makes NO LLM call."""
    checks = {
        "api_key": bool(OPENROUTER_API_KEY),
        "session_secret": bool(auth.SESSION_SECRET),
        "data_dir_writable": _data_dir_writable(),
    }
    ok = all(checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"ready": ok, "checks": checks})


# --- Conversations -----------------------------------------------------------
@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(user_id: str = Depends(get_current_user)):
    return store.list_conversations(user_id)


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(
    request: CreateConversationRequest,
    user_id: str = Depends(get_current_user),
):
    return store.create_conversation(user_id)


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    conversation = store.get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    if not await store.delete_conversation(user_id, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Identity: OAuth login (Kakao primary, Naver ready), session, profiles, consent
# ---------------------------------------------------------------------------
class ChildCreate(BaseModel):
    name: str
    birthdate: str  # YYYY-MM-DD


class ConsentRequest(BaseModel):
    kinds: List[str]
    version: str = "1.0"


def _child_with_age(child: Dict[str, Any]) -> Dict[str, Any]:
    return {**child, "age_days": age_days_from_birthdate(child["birthdate"])}


@app.get("/api/auth/providers")
@limiter.limit(RATE_LIMIT_AUTH)
async def auth_providers(request: Request, response: Response):
    return {p: oauth.provider_enabled(p) for p in oauth.PROVIDERS}


@app.get("/api/auth/{provider}/login")
@limiter.limit(RATE_LIMIT_AUTH)
async def auth_login(
    provider: str, request: Request, response: Response, user_id: str = Depends(get_current_user)
):
    if not oauth.provider_enabled(provider):
        raise HTTPException(status_code=404, detail="Provider not configured")
    cfg = oauth.provider_config(provider)
    state = secrets.token_urlsafe(24)
    payload = {"provider": provider, "state": state}
    code_challenge = None
    if cfg["pkce"]:
        pkce = oauth.make_pkce()
        payload["verifier"] = pkce["verifier"]
        code_challenge = pkce["challenge"]
    redirect = RedirectResponse(oauth.build_authorize_url(provider, state, code_challenge), status_code=302)
    auth.set_session_cookie(redirect, user_id)  # carry the current (anon) session forward
    redirect.set_cookie(OAUTH_COOKIE, auth.sign_payload(payload), max_age=600, **auth.cookie_security_kwargs())
    return redirect


@app.get("/api/auth/{provider}/callback")
async def auth_callback(
    provider: str,
    request: Request,
    code: str = "",
    state: str = "",
    user_id: str = Depends(get_current_user),
):
    """Finish OAuth: verify state (CSRF), exchange code, link identity in place, set session."""
    saved = auth.verify_payload(request.cookies.get(OAUTH_COOKIE))
    fail = RedirectResponse(f"{FRONTEND_URL}/?login=error", status_code=302)
    fail.delete_cookie(OAUTH_COOKIE, **auth.cookie_clear_kwargs())
    if not saved or saved.get("provider") != provider or not state or not secrets.compare_digest(
        str(saved.get("state", "")), state
    ):
        return fail  # state/CSRF mismatch
    token = await oauth.exchange_code(provider, code, state, saved.get("verifier"))
    if not token:
        return fail
    info = await oauth.fetch_userinfo(provider, token)
    if not info:
        return fail
    resolved = await accounts.link_identity(user_id, provider, info["provider_user_id"], info.get("display_name"))
    ok = RedirectResponse(f"{FRONTEND_URL}/?login=ok", status_code=302)
    auth.set_session_cookie(ok, resolved)
    ok.delete_cookie(OAUTH_COOKIE, **auth.cookie_clear_kwargs())
    return ok


@app.get("/api/auth/me")
async def auth_me(user_id: str = Depends(get_current_user)):
    if not accounts.is_authenticated(user_id):
        # Don't leak account/consent shape to an anonymous session.
        return {"user_id": user_id, "authenticated": False}
    account = accounts.get_account(user_id)
    return {
        "user_id": user_id,
        "authenticated": True,
        "display_name": account.get("display_name") if account else None,
        "providers": [p["provider"] for p in account.get("providers", [])] if account else [],
        "has_required_consents": accounts.has_required_consents(user_id),
    }


@app.post("/api/auth/logout")
async def auth_logout(response: Response):
    auth.clear_session_cookie(response)
    return {"status": "ok"}


@app.get("/api/children")
async def list_children(user_id: str = Depends(get_current_user)):
    return [_child_with_age(c) for c in accounts.list_children(user_id)]


@app.post("/api/children")
async def create_child(
    payload: ChildCreate,
    user_id: str = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    try:
        child = await accounts.add_child(user_id, payload.name, payload.birthdate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _child_with_age(child)


@app.delete("/api/children/{child_id}")
async def delete_child(
    child_id: str,
    user_id: str = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    if not await accounts.delete_child(user_id, child_id):
        raise HTTPException(status_code=404, detail="Child not found")
    return {"status": "ok"}


@app.get("/api/consents")
async def get_consents(user_id: str = Depends(get_current_user)):
    return {
        "consents": accounts.get_consents(user_id),
        "required": REQUIRED_CONSENTS,
        "all": ALL_CONSENTS,
        "has_required": accounts.has_required_consents(user_id),
    }


@app.post("/api/consents")
async def record_consents(
    payload: ConsentRequest,
    user_id: str = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    consents = await accounts.record_consents(user_id, payload.kinds, payload.version)
    return {"consents": consents, "has_required": accounts.has_required_consents(user_id)}


# --- The council pipeline ----------------------------------------------------
@app.post("/api/conversations/{conversation_id}/message")
@limiter.limit(RATE_LIMIT_MESSAGES)
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    request: Request,
    response: Response,
    user_id: str = Depends(require_authenticated_user),
    _: None = Depends(require_csrf),
):
    """Send a message and run the staged council process (non-streaming)."""
    conversation = store.get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    replay = _find_assistant_by_idempotency(conversation, payload.idempotency_key)
    if replay:
        return {
            "stage0": replay.get("stage0"), "stage1": replay.get("stage1"),
            "stage2": replay.get("stage2"), "stage3": replay.get("stage3"),
            "emergency": None, "metadata": {}, "replayed": True,
        }

    # Quota is reserved BEFORE the pipeline and intentionally NOT refunded on failure —
    # this prevents a retry-storm from amplifying paid calls past the daily ceiling.
    if not await quota.check_and_increment(user_id):
        raise HTTPException(
            status_code=429, detail="하루 질문 한도를 초과했어요. 내일 다시 시도해 주세요.",
            headers={"Retry-After": "86400"},
        )

    is_first_message = len(conversation["messages"]) == 0
    age_days = _resolve_age_days(user_id, payload)
    await store.append_user_message(user_id, conversation_id, payload.content)

    if is_first_message:
        try:
            title = await asyncio.wait_for(generate_conversation_title(payload.content), timeout=TITLE_TIMEOUT)
        except asyncio.TimeoutError:
            title = payload.content[:47]
        await store.update_title(user_id, conversation_id, title)

    # Pre-pipeline safety triage (deterministic, fast).
    triage = assess_emergency(age_days, payload.content)
    if triage and triage.get("short_circuit"):
        stage3_result = _emergency_stage3(triage)
        await store.append_assistant_message(
            user_id, conversation_id, _EMPTY_STAGE0, [], [], stage3_result,
            short_circuit=True, idempotency_key=payload.idempotency_key,
        )
        return {"stage0": _EMPTY_STAGE0, "stage1": [], "stage2": [],
                "stage3": stage3_result, "emergency": triage, "metadata": {}}

    try:
        stage0_result, stage1_results, stage2_results, stage3_result, metadata = await asyncio.wait_for(
            run_full_council(payload.content, age_days), timeout=PIPELINE_TIMEOUT
        )
    except Exception as e:  # noqa: BLE001 - timeout or any failure: persist partial, never leak
        logger.exception("council pipeline failed", extra={"conversation_id": conversation_id})
        await _persist_partial(user_id, conversation_id, None, None, None, payload.idempotency_key)
        raise HTTPException(status_code=500, detail=GENERIC_ERROR_KO) from e

    await store.append_assistant_message(
        user_id, conversation_id, stage0_result, stage1_results, stage2_results, stage3_result,
        idempotency_key=payload.idempotency_key,
    )
    return {"stage0": stage0_result, "stage1": stage1_results, "stage2": stage2_results,
            "stage3": stage3_result, "emergency": triage, "metadata": metadata}


@app.post("/api/conversations/{conversation_id}/message/stream")
@limiter.limit(RATE_LIMIT_MESSAGES)
async def send_message_stream(
    conversation_id: str,
    payload: SendMessageRequest,
    request: Request,
    response: Response,
    user_id: str = Depends(require_authenticated_user),
    _: None = Depends(require_csrf),
):
    """Send a message and stream the staged council process as Server-Sent Events."""
    conversation = store.get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    replay = _find_assistant_by_idempotency(conversation, payload.idempotency_key)
    is_first_message = len(conversation["messages"]) == 0
    age_days = _resolve_age_days(user_id, payload)

    async def event_generator():
        # Idempotent replay: re-emit the stored answer without re-running paid calls.
        if replay:
            if replay.get("stage0"):
                yield f"data: {json.dumps({'type': 'stage0_complete', 'data': replay['stage0']})}\n\n"
            if replay.get("stage3"):
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': replay['stage3']})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'replayed': True})}\n\n"
            return

        partial: Dict[str, Any] = {"stage0": None, "stage1": None, "stage2": None}
        saved = {"done": False}

        async def save_partial():
            if saved["done"]:
                return
            saved["done"] = True
            try:
                await _persist_partial(
                    user_id, conversation_id, partial["stage0"], partial["stage1"],
                    partial["stage2"], payload.idempotency_key,
                )
            except Exception:  # noqa: BLE001 - best effort on disconnect/cancel
                logger.exception("partial persist failed", extra={"conversation_id": conversation_id})

        try:
            if not await quota.check_and_increment(user_id):
                yield f"data: {json.dumps({'type': 'error', 'message': '하루 질문 한도를 초과했어요. 내일 다시 시도해 주세요.'})}\n\n"
                return

            await store.append_user_message(user_id, conversation_id, payload.content)

            triage = assess_emergency(age_days, payload.content)
            if triage:
                yield f"data: {json.dumps({'type': 'emergency', 'data': triage})}\n\n"
            if triage and triage.get("short_circuit"):
                stage3_result = _emergency_stage3(triage)
                await store.append_assistant_message(
                    user_id, conversation_id, _EMPTY_STAGE0, [], [], stage3_result,
                    short_circuit=True, idempotency_key=payload.idempotency_key,
                )
                saved["done"] = True
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                return

            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(payload.content))

            yield f"data: {json.dumps({'type': 'stage0_start'})}\n\n"
            partial["stage0"] = await asyncio.wait_for(stage0_research(payload.content), timeout=STAGE0_TIMEOUT)
            yield f"data: {json.dumps({'type': 'stage0_complete', 'data': partial['stage0']})}\n\n"

            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            partial["stage1"] = await asyncio.wait_for(
                stage1_collect_responses(payload.content, partial["stage0"]), timeout=STAGE1_TIMEOUT
            )
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': partial['stage1']})}\n\n"

            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            partial["stage2"], label_to_model = await asyncio.wait_for(
                stage2_collect_rankings(payload.content, partial["stage1"]), timeout=STAGE2_TIMEOUT
            )
            aggregate_rankings = calculate_aggregate_rankings(partial["stage2"], label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': partial['stage2'], 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await asyncio.wait_for(
                stage3_synthesize_final(payload.content, partial["stage1"], partial["stage2"], partial["stage0"], age_days),
                timeout=STAGE3_TIMEOUT,
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            if title_task:
                try:
                    title = await asyncio.wait_for(title_task, timeout=TITLE_TIMEOUT)
                except asyncio.TimeoutError:
                    title = payload.content[:47]
                await store.update_title(user_id, conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            await store.append_assistant_message(
                user_id, conversation_id, partial["stage0"], partial["stage1"],
                partial["stage2"], stage3_result, idempotency_key=payload.idempotency_key,
            )
            saved["done"] = True
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except (asyncio.CancelledError, GeneratorExit):
            # Client disconnected: stop burning paid calls, persist what we have.
            await save_partial()
            raise
        except Exception:  # noqa: BLE001 - never leak str(e); persist partial
            logger.exception("stream pipeline failed", extra={"conversation_id": conversation_id})
            await save_partial()
            yield f"data: {json.dumps({'type': 'error', 'message': GENERIC_ERROR_KO})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
