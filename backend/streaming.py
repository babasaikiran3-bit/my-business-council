"""Streaming en vivo de Stage 1: lanza cada agente y emite eventos canónicos.

Normaliza los formatos de evento de cada CLI a un esquema único (ver SSD §6.3):
  - claude / anthropic_agent (DeepSeek/GLM/...) → `--output-format stream-json` (Claude Code)
  - codex                                       → `--json` (+ `-o` para texto final robusto)
  - gemini (agy)                                → sin stream: emite working → result

El callback `emit(event: dict)` lo provee el llamador (main.py lo conecta a una Queue/SSE).
Cada `run_agent_stream` devuelve el texto final del agente (para armar stage1_results).
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

Emit = Callable[[Dict[str, Any]], None]

# Tools → ícono (el frontend también mapea; esto es por si se quiere texto).
_TOOL_ARG = {
    "Read": "file_path", "Write": "file_path", "Edit": "file_path",
    "Grep": "pattern", "Glob": "pattern", "Bash": "command",
}


def _short(s: Any, n: int = 120) -> str:
    s = str(s).replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


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


async def _stream_subprocess(argv, parser, model_id, emit, env=None, cwd=None,
                             final_file: Optional[str] = None) -> Optional[str]:
    """Lanza un subproceso, lee stdout línea a línea, parsea y emite. Devuelve texto final."""
    run_env = {**os.environ, **env} if env else None
    final_text: Optional[str] = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or AGENT_CWD,
            env=run_env,
        )
        try:
            while True:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=CLI_TIMEOUT)
                if not line:
                    break
                raw = line.decode(errors="replace").strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                evts, maybe_final = parser(obj, model_id)
                for e in evts:
                    emit(e)
                if maybe_final is not None:
                    final_text = maybe_final
            await asyncio.wait_for(proc.wait(), timeout=30)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
    except Exception as e:
        emit({"type": "agent", "model": model_id, "status": "error", "reason": str(e)})
        return None

    if final_file:
        try:
            with open(final_file) as f:
                txt = f.read().strip()
                if txt:
                    final_text = txt
        except OSError:
            pass

    return final_text


async def run_agent_stream(model_id: str, prompt: str, emit: Emit,
                           cwd: Optional[str] = None) -> Optional[str]:
    """Corre un miembro del consejo emitiendo su progreso en vivo. Devuelve su texto final."""
    spec = REGISTRY.get(model_id)
    if spec is None:
        emit({"type": "agent", "model": model_id, "status": "error", "reason": "modelo desconocido"})
        return None

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
                content = await _stream_subprocess(
                    [binary, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
                     "--json", "-o", path, prompt],
                    parse_codex_event, model_id, emit, cwd=cwd, final_file=path)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
            emit({"type": "agent", "model": model_id, "status": "done"})
            return content

        # --- Claude y anthropic_agent (DeepSeek/GLM/...): stream-json ---
        binary = resolve_bin("claude")
        env = None
        if transport == "anthropic_agent":
            env = anthropic_agent_env(spec)
            if env is None:
                emit({"type": "agent", "model": model_id, "status": "error",
                      "reason": f"falta {spec.get('key_file')}"})
                return None
        content = await _stream_subprocess(
            [binary, "--dangerously-skip-permissions", "-p", "--verbose",
             "--output-format", "stream-json", prompt],
            parse_claude_event, model_id, emit, env=env, cwd=cwd)
        emit({"type": "agent", "model": model_id, "status": "done"})
        return content

    except Exception as e:
        emit({"type": "agent", "model": model_id, "status": "error", "reason": str(e)})
        return None
