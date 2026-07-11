"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio

from . import storage
from . import repos as repos_mod
from . import council_config
from .council import (
    run_full_council, run_full_council_streaming, generate_conversation_title,
    generate_consensus_doc,
)

app = FastAPI(title="LLM Council API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    pass


class SendMessageRequest(BaseModel):
    content: str
    repo_path: Optional[str] = None
    members: Optional[List[str]] = None
    chairman: Optional[str] = None
    research: bool = True  # Stage 0: ronda de búsqueda de info actual antes de deliberar


class DocumentConsensusRequest(BaseModel):
    repo_path: Optional[str] = None  # opcional: por defecto usa el repo atado a la conversación
    chairman: Optional[str] = None


class CouncilConfigRequest(BaseModel):
    members: List[str]
    chairman: str


class ConversationMetadata(BaseModel):
    id: str
    created_at: str
    title: str
    message_count: int
    repo_path: Optional[str] = None


class Conversation(BaseModel):
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]
    repo_path: Optional[str] = None


@app.get("/")
async def root():
    return {"status": "ok", "service": "LLM Council API"}


# --- Repos y configuración del consejo --------------------------------------

@app.get("/api/repos")
async def get_repos():
    """Repos autodetectados para el selector."""
    return {"repos": repos_mod.list_repos()}


@app.get("/api/models")
async def get_models():
    """Universo de modelos + salud + activos. Nunca expone keys."""
    return council_config.list_models()


@app.put("/api/council/config")
async def put_council_config(request: CouncilConfigRequest):
    """Activa/desactiva miembros y elige chairman. Persiste en data/council_config.json."""
    try:
        validated = council_config.validate_config(
            {"members": request.members, "chairman": request.chairman})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    saved = council_config.save_config(validated)
    return saved


# --- Conversaciones ---------------------------------------------------------

@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    conversation_id = str(uuid.uuid4())
    return storage.create_conversation(conversation_id)


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _resolve_cwd(repo_path: Optional[str]) -> Optional[str]:
    """Valida repo_path (anti traversal). Devuelve cwd o None (Q&A sin repo)."""
    if not repo_path:
        return None
    if not repos_mod.is_allowed(repo_path):
        raise HTTPException(status_code=400, detail=f"Repo no permitido: {repo_path}")
    import os
    return os.path.realpath(os.path.expanduser(repo_path))


def _build_history(conversation: Dict[str, Any]) -> List[Dict[str, str]]:
    """Turnos previos [{q, a}] a partir de los mensajes ya guardados (sin el actual)."""
    history: List[Dict[str, str]] = []
    last_user = ""
    for msg in conversation.get("messages", []):
        if msg.get("role") == "user":
            last_user = msg.get("content", "")
        elif msg.get("role") == "assistant":
            answer = (msg.get("stage3") or {}).get("response", "")
            history.append({"q": last_user, "a": answer})
    return history


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Borra una conversación entera."""
    if not storage.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """Modo batch: corre el consejo y devuelve las 3 etapas completas."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    cwd = _resolve_cwd(request.repo_path)
    if cwd:
        storage.set_conversation_repo(conversation_id, cwd)  # atar el repo a la conversación
    is_first_message = len(conversation["messages"]) == 0
    history = _build_history(conversation)
    storage.add_user_message(conversation_id, request.content)
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    stage1, stage2, stage3, metadata = await run_full_council(
        request.content, cwd=cwd, members=request.members, chairman=request.chairman,
        history=history, research=request.research)

    storage.add_assistant_message(conversation_id, stage1, stage2, stage3, metadata=metadata)
    return {"stage1": stage1, "stage2": stage2, "stage3": stage3, "metadata": metadata}


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """Modo streaming: emite eventos canónicos en vivo (SSE)."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    cwd = _resolve_cwd(request.repo_path)  # valida antes de abrir el stream
    if cwd:
        storage.set_conversation_repo(conversation_id, cwd)  # atar el repo a la conversación
    is_first_message = len(conversation["messages"]) == 0
    history = _build_history(conversation)

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        def emit(event: Dict[str, Any]):
            queue.put_nowait(event)

        async def run():
            try:
                storage.add_user_message(conversation_id, request.content)
                title_task = None
                if is_first_message:
                    title_task = asyncio.create_task(
                        generate_conversation_title(request.content))

                stage1, stage2, stage3, metadata = await run_full_council_streaming(
                    request.content, emit, cwd=cwd,
                    members=request.members, chairman=request.chairman,
                    history=history, research=request.research)

                # metadata para de-anonimizar Stage 2 en el cliente
                emit({"type": "metadata", "metadata": metadata})

                storage.add_assistant_message(conversation_id, stage1, stage2, stage3, metadata=metadata)

                if title_task:
                    title = await title_task
                    storage.update_conversation_title(conversation_id, title)
                    emit({"type": "title", "title": title})

                emit({"type": "done",
                      "stage1": stage1, "stage2": stage2, "stage3": stage3,
                      "metadata": metadata})
            except Exception as e:
                emit({"type": "fatal", "message": str(e)})
            finally:
                queue.put_nowait(None)  # sentinel de cierre

        task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def _last_consensus_msg(conversation: Dict[str, Any]):
    """Último mensaje del asistente con un Stage 3 (el consenso a documentar)."""
    return next((m for m in reversed(conversation["messages"])
                 if m.get("role") == "assistant" and m.get("stage3")), None)


def _query_for(conversation: Dict[str, Any], msg) -> str:
    """Pregunta del usuario que originó ese mensaje de consenso."""
    idx = conversation["messages"].index(msg)
    return next((conversation["messages"][i]["content"]
                 for i in range(idx - 1, -1, -1)
                 if conversation["messages"][i].get("role") == "user"), "")


def _safe_consensus_target(cwd: str, path: Optional[str]) -> tuple:
    """Fuerza el destino a docs/council/<basename>.md dentro del repo (anti traversal)."""
    import os
    base = os.path.basename(path or "") or "consensus.md"
    if not base.endswith(".md"):
        base += ".md"
    target = os.path.join(cwd, "docs", "council", base)
    return target, os.path.relpath(target, cwd)


@app.post("/api/conversations/{conversation_id}/document-consensus")
async def document_consensus_preview(conversation_id: str, request: DocumentConsensusRequest):
    """PREVIEW: el chairman genera (NO escribe) el documento de consenso para revisar."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    repo_path = conversation.get("repo_path") or request.repo_path
    cwd = _resolve_cwd(repo_path)
    if not cwd:
        raise HTTPException(status_code=400, detail="Se requiere un repo para documentar el consenso")

    last = _last_consensus_msg(conversation)
    if last is None:
        raise HTTPException(status_code=400, detail="No hay un consenso (Stage 3) para documentar")

    user_query = _query_for(conversation, last)
    result = await generate_consensus_doc(
        user_query, last.get("stage1") or [], last.get("stage2") or [], last["stage3"],
        chairman=request.chairman)

    if not result.get("content"):
        raise HTTPException(status_code=502, detail="El chairman no devolvió un documento.")

    _, rel = _safe_consensus_target(cwd, result.get("path"))
    # Guardar el borrador pendiente atado al mensaje (para aprobar/descartar después).
    last["pending_consensus"] = {"path": rel, "content": result["content"]}
    storage.save_conversation(conversation)

    return {"path": rel, "content": result["content"], "model": result.get("model"),
            "repo_path": cwd}


@app.post("/api/conversations/{conversation_id}/document-consensus/approve")
async def document_consensus_approve(conversation_id: str, request: DocumentConsensusRequest):
    """APROBAR: el backend escribe el documento pendiente en docs/council/ del repo."""
    import os
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    repo_path = conversation.get("repo_path") or request.repo_path
    cwd = _resolve_cwd(repo_path)
    if not cwd:
        raise HTTPException(status_code=400, detail="Se requiere un repo válido")

    last = _last_consensus_msg(conversation)
    pending = last.get("pending_consensus") if last else None
    if not pending:
        raise HTTPException(status_code=400, detail="No hay un documento pendiente de aprobar")

    target, rel = _safe_consensus_target(cwd, pending.get("path"))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w") as f:
        f.write(pending["content"])

    last["consensus_file"] = rel
    last.pop("pending_consensus", None)
    storage.save_conversation(conversation)
    return {"consensus_file": rel}


@app.post("/api/conversations/{conversation_id}/document-consensus/discard")
async def document_consensus_discard(conversation_id: str):
    """DESCARTAR: tira el borrador pendiente sin escribir nada."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    last = _last_consensus_msg(conversation)
    if last and last.pop("pending_consensus", None) is not None:
        storage.save_conversation(conversation)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
