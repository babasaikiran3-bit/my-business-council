"""Streaming en vivo de Stage 1: lanza cada agente y emite eventos canónicos.

Normaliza los formatos de evento de cada CLI a un esquema único (ver SSD §6.3):
  - claude / anthropic_agent (DeepSeek/GLM/...) → `--output-format stream-json` (Claude Code)
  - codex                                       → `--json` (+ `-o` para texto final robusto)
  - gemini (agy)                                → sin stream: emite working → result

El callback `emit(event: dict)` lo provee el llamador (main.py lo conecta a una Queue/SSE).
Cada `run_agent_stream` devuelve el texto final del agente (para armar stage1_results).

El ciclo de vida del subproceso se delegó en WorkerExecutor (ADR 0002 §3).  Esta capa
solo resuelve transporte, arma argumentos y traduce resultados a los mismos eventos SSE
que el frontend ya consume.
"""

import os
import json
import asyncio
import tempfile
from typing import Optional, Callable, Dict, Any, List, Tuple

from .models_registry import REGISTRY
from .providers import (
    resolve_bin, anthropic_agent_env, _query_cli_native, AGENT_CWD, CLI_TIMEOUT,
)
from .worker_executor import (
    WorkerExecutor, WorkerOutcome, WorkerResult, CancellationToken,
)

Emit = Callable[[Dict[str, Any]], None]

# Tools → ícono (el frontend también mapea; esto es por si se quiere texto).
_TOOL_ARG = {
    "Read": "file_path", "Write": "file_path", "Edit": "file_path",
    "Grep": "pattern", "Glob": "pattern", "Bash": "command",
}


def _short(s: Any, n: int = 120) -> str:
    s = str(s).replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Parsers de eventos (sin cambios — contrato estable)
# ---------------------------------------------------------------------------

def parse_claude_event(obj: Dict[str, Any], model_id: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Evento de Claude Code (stream-json) → (eventos canónicos, texto_final|None)."""
    events: List[Dict[str, Any]] = []
    final: Optional[str] = None
    etype = obj.get("type")

    if etype == "assistant":
        for block in obj.get("message", {}).get("content", []) or []:
            btype = block.get("type")
            if btype == "text":
                text = (block.get("text") or "").strip()
                if text:
                    events.append({"type": "thought", "model": model_id, "text": _short(text, 200)})
            elif btype == "tool_use":
                name = block.get("name", "tool")
                inp = block.get("input", {}) or {}
                arg_key = _TOOL_ARG.get(name)
                detail = inp.get(arg_key) if arg_key else next(
                    (v for v in inp.values() if isinstance(v, str)), "")
                events.append({"type": "tool", "model": model_id,
                               "tool": name, "detail": _short(detail)})
    elif etype == "result":
        final = obj.get("result")

    return events, final


def parse_codex_event(obj: Dict[str, Any], model_id: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Evento de codex exec --json → (eventos canónicos, texto_final|None). Best-effort."""
    events: List[Dict[str, Any]] = []
    final: Optional[str] = None

    item = obj.get("item") or obj.get("msg") or {}
    itype = item.get("type") or obj.get("type", "")

    if "command" in item:
        events.append({"type": "tool", "model": model_id,
                       "tool": "Bash", "detail": _short(item.get("command"))})
    elif itype in ("file_change", "patch", "edit"):
        path = item.get("path") or item.get("file") or ""
        events.append({"type": "tool", "model": model_id, "tool": "Edit", "detail": _short(path)})
    elif itype in ("reasoning",) and item.get("text"):
        events.append({"type": "thought", "model": model_id, "text": _short(item.get("text"), 200)})
    elif itype in ("agent_message", "assistant_message") and item.get("text"):
        final = item.get("text")
    elif itype.startswith("mcp") or "tool" in itype:
        events.append({"type": "tool", "model": model_id,
                       "tool": "MCP", "detail": _short(item.get("name", ""))})

    return events, final


# ---------------------------------------------------------------------------
# Helpers para armar y despachar executors
# ---------------------------------------------------------------------------

def _emit_error(emit: Emit, model_id: str, reason: str) -> None:
    """Emite un evento de error de agente (preserva semántica SSE existente)."""
    emit({"type": "agent", "model": model_id, "status": "error", "reason": reason})


async def _run_executor(
    executor: WorkerExecutor, emit: Emit, model_id: str
) -> Optional[str]:
    """Ejecuta un WorkerExecutor y traduce su WorkerResult al contrato previo.

    Emite exactamente un evento terminal de agente (``done`` o ``error``)
    según el ``WorkerOutcome``, preservando los shapes de evento que el
    frontend ya consume.
    """
    result = await executor.run(emit)

    if result.outcome == WorkerOutcome.COMPLETED:
        emit({"type": "agent", "model": model_id, "status": "done"})
    elif result.outcome == WorkerOutcome.FAILED:
        reason = result.error_message or f"exit code {result.returncode}"
        emit({"type": "agent", "model": model_id, "status": "error", "reason": reason})
    elif result.outcome == WorkerOutcome.TIMED_OUT:
        emit({"type": "agent", "model": model_id, "status": "error", "reason": "timeout"})
    elif result.outcome == WorkerOutcome.CANCELLED:
        emit({"type": "agent", "model": model_id, "status": "error", "reason": "cancelled"})

    return result.final_text


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

async def run_agent_stream(model_id: str, prompt: str, emit: Emit,
                           cwd: Optional[str] = None) -> Optional[str]:
    """Corre un miembro del consejo emitiendo su progreso en vivo. Devuelve su texto final."""
    spec = REGISTRY.get(model_id)
    if spec is None:
        _emit_error(emit, model_id, "modelo desconocido")
        return None

    # Default to the neutral agent directory so the subprocess doesn't
    # inherit the backend cwd (restores pre-WorkerExecutor behaviour).
    if cwd is None:
        cwd = AGENT_CWD

    emit({"type": "agent", "model": model_id, "status": "working"})
    transport = spec["transport"]
    bin_name = spec.get("bin")

    try:
        # --- Gemini (agy): sin streaming de eventos → batch ---
        if transport == "cli_native" and bin_name == "agy":
            content = await _query_cli_native(spec, prompt, cwd=cwd)
            emit({"type": "agent", "model": model_id, "status": "done"})
            return content

        # --- Codex: --json en vivo + -o para el texto final robusto ---
        if transport == "cli_native" and bin_name == "codex":
            binary = resolve_bin("codex")
            fd, path = tempfile.mkstemp(suffix=".txt", prefix="codex-", dir=AGENT_CWD)
            os.close(fd)
            try:
                executor = WorkerExecutor(
                    [binary, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
                     "--json", "-o", path, prompt],
                    parse_codex_event, model_id,
                    cwd=cwd, inactivity_timeout=CLI_TIMEOUT, final_file=path)
                content = await _run_executor(executor, emit, model_id)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
            return content

        # --- Claude y anthropic_agent (DeepSeek/GLM/...): stream-json ---
        binary = resolve_bin("claude")
        env = None
        if transport == "anthropic_agent":
            env = anthropic_agent_env(spec)
            if env is None:
                _emit_error(emit, model_id, f"falta {spec.get('key_file')}")
                return None
        executor = WorkerExecutor(
            [binary, "--dangerously-skip-permissions", "-p", "--verbose",
             "--output-format", "stream-json", prompt],
            parse_claude_event, model_id,
            env=env, cwd=cwd, inactivity_timeout=CLI_TIMEOUT)
        content = await _run_executor(executor, emit, model_id)
        return content

    except Exception as e:
        _emit_error(emit, model_id, str(e))
        return None
