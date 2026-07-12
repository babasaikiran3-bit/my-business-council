"""Dispatcher de proveedores data-driven (modo batch).

Lee del REGISTRY (models_registry) y enruta cada modelo a su transporte. Mantiene la
firma pública `query_model` / `query_models_parallel`. El streaming en vivo de Stage 1
vive en streaming.py; acá queda el modo batch (Stage 2/3, títulos, y debate.py CLI).
"""

import os
import shutil
import asyncio
import tempfile
from typing import List, Dict, Any, Optional

import httpx

from .models_registry import REGISTRY
from .config import AGENT_CWD  # absoluto, pathlib-based (ver backend/paths.py)


# --- Resolución de binarios -------------------------------------------------

def resolve_bin(name: str) -> str:
    """Encuentra un binario en PATH; si no, prueba ~/.local/bin; si no, confía en PATH."""
    found = shutil.which(name)
    if found:
        return found
    fallback = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.exists(fallback):
        return fallback
    return name


# Directorio de trabajo neutro para Q&A sin repo (evita que los agentes escaneen).
os.makedirs(AGENT_CWD, exist_ok=True)

CLI_TIMEOUT = 300.0
API_TIMEOUT = 120.0


def messages_to_prompt(messages: List[Dict[str, str]]) -> str:
    """Aplana mensajes a un único prompt de texto para los CLIs."""
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            parts.append(f"[Instrucciones del sistema]\n{content}")
        elif role == "assistant":
            parts.append(f"[Respuesta previa]\n{content}")
        else:
            parts.append(content)
    return "\n\n".join(parts)


def read_key(key_file: str) -> Optional[str]:
    try:
        with open(os.path.expanduser(key_file)) as f:
            return f.read().strip()
    except OSError:
        return None


def anthropic_agent_env(spec: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Construye el env para correr Claude Code apuntado a un endpoint Anthropic-compat."""
    key = read_key(spec["key_file"])
    if not key:
        return None
    model = spec["model"]
    small = spec.get("small_model", model)
    return {
        "CLAUDE_CONFIG_DIR": os.path.expanduser(spec["config_dir"]),
        "ANTHROPIC_BASE_URL": spec["base"],
        "ANTHROPIC_API_KEY": key,
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_SMALL_FAST_MODEL": small,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": small,
        "CLAUDE_CODE_SUBAGENT_MODEL": small,
        "CLAUDE_CODE_EFFORT_LEVEL": "max",
    }


# --- Ejecución de CLIs ------------------------------------------------------

async def _run_cli(argv: List[str], read_file: Optional[str] = None,
                   timeout: float = CLI_TIMEOUT,
                   env: Optional[Dict[str, str]] = None,
                   cwd: Optional[str] = None) -> Optional[str]:
    """Ejecuta un CLI agéntico async. Lee de read_file si se indica, si no de stdout."""
    run_env = {**os.environ, **env} if env else None
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or AGENT_CWD,
            env=run_env,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        print(f"Error ejecutando {argv[0]}: {e}")
        return None

    if proc.returncode != 0:
        print(f"{argv[0]} salió con código {proc.returncode}: "
              f"{err.decode(errors='replace')[:300]}")

    if read_file:
        try:
            with open(read_file) as f:
                return (f.read().strip() or None)
        except OSError:
            return None

    return out.decode(errors="replace").strip() or None


async def _query_cli_native(spec: Dict[str, Any], prompt: str,
                            cwd: Optional[str] = None,
                            allow_write: bool = False) -> Optional[str]:
    """claude / codex / agy en modo print, salida final limpia.

    allow_write: si True, habilita escritura en el cwd (sandbox workspace-write en codex;
    claude/agy ya pueden escribir con --dangerously-skip-permissions).
    """
    bin_name = spec["bin"]
    binary = resolve_bin(bin_name)

    if bin_name == "codex":
        sandbox = "workspace-write" if allow_write else "read-only"
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="codex-", dir=AGENT_CWD)
        os.close(fd)
        try:
            return await _run_cli(
                [binary, "exec", "--skip-git-repo-check",
                 "--sandbox", sandbox, "-o", path, prompt],
                read_file=path, cwd=cwd,
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    if bin_name == "claude":
        return await _run_cli(
            [binary, "--dangerously-skip-permissions", "-p", prompt], cwd=cwd)

    # agy (gemini)
    return await _run_cli(
        [binary, "--dangerously-skip-permissions", "-p", prompt], cwd=cwd)


async def _query_anthropic_agent(spec: Dict[str, Any], prompt: str,
                                 cwd: Optional[str] = None,
                                 allow_write: bool = False) -> Optional[str]:
    """Claude Code apuntado a un backend Anthropic-compat (DeepSeek/GLM/aiapi...)."""
    env = anthropic_agent_env(spec)
    if env is None:
        print(f"Falta {spec.get('key_file')} para {spec.get('label')}")
        return None
    binary = resolve_bin("claude")
    return await _run_cli(
        [binary, "--dangerously-skip-permissions", "-p",
         "--output-format", "text", prompt],
        env=env, cwd=cwd,
    )


async def _query_openai_api(spec: Dict[str, Any], prompt: str) -> Optional[str]:
    """POST REST OpenAI-compatible (ciego, sin tools)."""
    key = read_key(spec["key_file"])
    if not key:
        print(f"Falta {spec.get('key_file')} para {spec.get('label')}")
        return None
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": spec["model"],
               "messages": [{"role": "user", "content": prompt}], "stream": False}
    url = spec["base"].rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"].get("content")
    except Exception as e:
        print(f"Error consultando {spec.get('label')}: {e}")
        return None


# --- API pública ------------------------------------------------------------

async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = CLI_TIMEOUT,
    cwd: Optional[str] = None,
    allow_write: bool = False,
) -> Optional[Dict[str, Any]]:
    """Enruta un id de modelo a su transporte. Devuelve {'content', ...} o None.

    allow_write habilita escritura en el cwd (solo aplica a transportes con manos:
    cli_native y anthropic_agent; openai_api es ciego y lo ignora).
    """
    spec = REGISTRY.get(model)
    if spec is None:
        print(f"Modelo desconocido: {model}")
        return None

    prompt = messages_to_prompt(messages)
    transport = spec["transport"]

    if transport == "cli_native":
        content = await _query_cli_native(spec, prompt, cwd=cwd, allow_write=allow_write)
    elif transport == "anthropic_agent":
        content = await _query_anthropic_agent(spec, prompt, cwd=cwd, allow_write=allow_write)
    elif transport == "openai_api":
        content = await _query_openai_api(spec, prompt)
    else:
        print(f"Transporte desconocido: {transport}")
        return None

    if content is None:
        return None
    return {"content": content, "reasoning_details": None}


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    cwd: Optional[str] = None,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Consulta varios modelos en paralelo. Mapea id -> respuesta (o None)."""
    tasks = [query_model(model, messages, cwd=cwd) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}
