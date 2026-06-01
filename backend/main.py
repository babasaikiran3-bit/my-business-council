"""FastAPI backend for Parenting Roundtable."""

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
import asyncio
import secrets

from .storage_backend import store
from .accounts import accounts, age_days_from_birthdate, ALL_CONSENTS, REQUIRED_CONSENTS
from . import oauth
from . import auth
from .auth import get_current_user
from .council import run_full_council, generate_conversation_title, stage0_research, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from .safety import assess_emergency, KO_DISCLAIMER

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
OAUTH_COOKIE = "pr_oauth"

app = FastAPI(title="Parenting Roundtable API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    # Typed child age in days — drives the deterministic safety triage/backstop.
    # Optional for backward compatibility; the keyword red-flags fire regardless,
    # and the newborn-fever rule needs this typed value (never the prompt string).
    age_days: Optional[int] = None
    # When set, age_days is derived server-side from this saved child's birthdate.
    child_profile_id: Optional[str] = None


def _resolve_age_days(user_id: str, request: "SendMessageRequest") -> Optional[int]:
    """Prefer a saved child profile's birthdate-derived age; fall back to the typed age."""
    if request.child_profile_id:
        child = accounts.get_child(user_id, request.child_profile_id)
        if child:
            derived = age_days_from_birthdate(child["birthdate"])
            if derived is not None:
                return derived
    return request.age_days


def _emergency_stage3(triage: Dict[str, Any]) -> Dict[str, Any]:
    """Build a synthetic Stage 3 carrying the deterministic Korean emergency interstitial."""
    numbers = " · ".join(triage.get("numbers", []))
    body = f"> 응급: {triage['message_ko']}"
    if numbers:
        body += f"\n\n**지금 연락하세요:** {numbers}"
    body += f"\n\n{KO_DISCLAIMER}"
    return {"model": "safety-triage", "response": body, "sources": [], "emergency": triage}


_EMPTY_STAGE0 = {"evidence_brief": "", "sources": []}


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Parenting Roundtable API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(user_id: str = Depends(get_current_user)):
    """List the current user's conversations (metadata only)."""
    return store.list_conversations(user_id)


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(
    request: CreateConversationRequest,
    user_id: str = Depends(get_current_user),
):
    """Create a new conversation owned by the current user."""
    return store.create_conversation(user_id)


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    """Get one of the current user's conversations with all its messages."""
    conversation = store.get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


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
async def auth_providers():
    """Which OAuth providers are configured (so the UI shows only working buttons)."""
    return {p: oauth.provider_enabled(p) for p in oauth.PROVIDERS}


@app.get("/api/auth/{provider}/login")
async def auth_login(provider: str, user_id: str = Depends(get_current_user)):
    """Start the OAuth dance: set a short-lived signed state+PKCE cookie, then redirect."""
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
    redirect.set_cookie(OAUTH_COOKIE, auth.sign_payload(payload), max_age=600, httponly=True, samesite="lax")
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
    fail.delete_cookie(OAUTH_COOKIE, samesite="lax")
    if not saved or saved.get("provider") != provider or not state or saved.get("state") != state:
        return fail  # state/CSRF mismatch
    token = await oauth.exchange_code(provider, code, state, saved.get("verifier"))
    if not token:
        return fail
    info = await oauth.fetch_userinfo(provider, token)
    if not info:
        return fail
    resolved = accounts.link_identity(user_id, provider, info["provider_user_id"], info.get("display_name"))
    ok = RedirectResponse(f"{FRONTEND_URL}/?login=ok", status_code=302)
    auth.set_session_cookie(ok, resolved)
    ok.delete_cookie(OAUTH_COOKIE, samesite="lax")
    return ok


@app.get("/api/auth/me")
async def auth_me(user_id: str = Depends(get_current_user)):
    account = accounts.get_account(user_id)
    return {
        "user_id": user_id,
        "authenticated": accounts.is_authenticated(user_id),
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
async def create_child(payload: ChildCreate, user_id: str = Depends(get_current_user)):
    try:
        child = accounts.add_child(user_id, payload.name, payload.birthdate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _child_with_age(child)


@app.delete("/api/children/{child_id}")
async def delete_child(child_id: str, user_id: str = Depends(get_current_user)):
    if not accounts.delete_child(user_id, child_id):
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
async def record_consents(payload: ConsentRequest, user_id: str = Depends(get_current_user)):
    consents = accounts.record_consents(user_id, payload.kinds, payload.version)
    return {"consents": consents, "has_required": accounts.has_required_consents(user_id)}


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Send a message and run the staged council process.
    Returns the complete response with all stages.
    """
    # Ownership-scoped lookup: a user can only act on their own conversation.
    conversation = store.get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    age_days = _resolve_age_days(user_id, request)
    store.append_user_message(user_id, conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        store.update_title(user_id, conversation_id, title)

    # Pre-pipeline safety triage (deterministic, fast). Non-medical red flags
    # (self-harm, abuse) short-circuit the pediatric pipeline entirely.
    triage = assess_emergency(age_days, request.content)
    if triage and triage.get("short_circuit"):
        stage3_result = _emergency_stage3(triage)
        store.append_assistant_message(user_id, conversation_id, _EMPTY_STAGE0, [], [], stage3_result)
        return {
            "stage0": _EMPTY_STAGE0, "stage1": [], "stage2": [],
            "stage3": stage3_result, "emergency": triage, "metadata": {}
        }

    # Run the staged council process (Stage 0 research first)
    stage0_result, stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content,
        age_days
    )

    store.append_assistant_message(
        user_id, conversation_id,
        stage0_result, stage1_results, stage2_results, stage3_result
    )

    # Return the complete response with metadata (+ any medical emergency interstitial)
    return {
        "stage0": stage0_result,
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "emergency": triage,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(
    conversation_id: str,
    request: SendMessageRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Send a message and stream the staged council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Ownership-scoped lookup: a user can only act on their own conversation.
    conversation = store.get_conversation(user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0
    age_days = _resolve_age_days(user_id, request)

    async def event_generator():
        try:
            # Add user message
            store.append_user_message(user_id, conversation_id, request.content)

            # Pre-pipeline safety triage — emit the emergency interstitial FIRST so a
            # panicking parent sees "지금 119에 전화하세요 / 응급실로" in <2s, not after ~30-60s.
            triage = assess_emergency(age_days, request.content)
            if triage:
                yield f"data: {json.dumps({'type': 'emergency', 'data': triage})}\n\n"
            if triage and triage.get('short_circuit'):
                # Non-medical red flag (self-harm/abuse): do NOT run the pediatric pipeline.
                stage3_result = _emergency_stage3(triage)
                store.append_assistant_message(user_id, conversation_id, _EMPTY_STAGE0, [], [], stage3_result)
                yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                return

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 0: Build the shared evidence base via web search
            yield f"data: {json.dumps({'type': 'stage0_start'})}\n\n"
            stage0_result = await stage0_research(request.content)
            yield f"data: {json.dumps({'type': 'stage0_complete', 'data': stage0_result})}\n\n"

            # Stage 1: Collect responses grounded in the evidence base
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content, stage0_result)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results, stage0_result, age_days)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                store.update_title(user_id, conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            store.append_assistant_message(
                user_id,
                conversation_id,
                stage0_result,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
