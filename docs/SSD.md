# SSD — Council Chat: sala web de debate sobre repositorios

**Documento de Diseño de Software (Software Design Specification)**
Proyecto: `llm-council` (fork local, adaptado a suscripciones)
Autor: Claude (delegación MVP+ADR) · Revisor: Andrés
Fecha: 2026-06-23 · Estado: **propuesto, listo para implementar de un tiro**

---

## 1. Objetivo

Transformar el LLM Council en una **sala de chat web** donde el usuario:

1. **Selecciona un repositorio** (autodetectado o por path manual) desde la propia web.
2. **Hace preguntas / abre debates** sobre ese repo.
3. **Ve en vivo lo que hace cada modelo** mientras explora el repo (qué archivos lee,
   qué tools usa, su razonamiento), no solo el resultado final.

Los 4 miembros del consejo son agentes con ojos y manos (Read/Grep/Glob/Bash) que
exploran el repo por su cuenta, fijan postura, se rankean a ciegas entre pares y un
chairman sintetiza.

### No-objetivos (fuera de alcance v1)

- Edición/escritura del repo por los agentes (modo **read-only**, ver §8).
- Autenticación / multiusuario (uso personal, localhost).
- Persistir el stream de eventos en disco (es efímero; se persiste solo el resultado).
- Soporte de repos remotos sin clonar (se asume path local; clonar es manual).

---

## 2. Contexto y estado actual

Ya implementado y verificado en sesiones previas:

- **`backend/providers.py`** — dispatcher de proveedores por suscripción/API:
  - `claude` → `claude -p` (suscripción Max)
  - `codex` → `codex exec` (suscripción ChatGPT, gpt-5.5)
  - `gemini` → `agy -p` (suscripción Google, Gemini 3.5 Pro)
  - `deepseek` → `claude-ds -p` (Claude Code apuntado a DeepSeek; **ojos y manos**)
  - `deepseek-flash` → API REST (solo títulos)
  - `query_model(model, messages, cwd)` y `query_models_parallel(models, messages, cwd)`
    ya aceptan `cwd` para apuntar los agentes a un repo.
- **`backend/council.py`** — `run_full_council(query, cwd)` propaga `cwd` a stage 1.
- **`backend/main.py`** — FastAPI en `:8001`, POST `/api/conversations/{id}/message` (batch).
- **`frontend/`** — React + Vite en `:5173`: chat, sidebar de conversaciones, Stage1/2/3.
- **`debate.py`** — CLI de debate sobre repo (se mantiene como herramienta auxiliar).

Lo que falta es lo de este SSD: selector de repo en la web + streaming en vivo.

---

## 3. Capacidades de streaming por agente (hecho técnico que condiciona el diseño)

| Agente | Flag de streaming | Eventos en vivo |
|---|---|---|
| claude | `--output-format stream-json --verbose` | ✅ texto + tool_use + tool_result |
| deepseek (claude-ds) | idem (es Claude Code) | ✅ idem |
| codex | `--json` (JSONL a stdout) + `-o` para texto final | ✅ eventos propios |
| gemini (agy) | — (solo `--print`, texto final) | ❌ solo "trabajando" → resultado |

**Consecuencia de diseño:** el panel en vivo muestra 3 de 4 agentes con detalle fino;
Gemini muestra estado `working` hasta que entrega su resultado. Se documenta en la UI.

---

## 4. Decisiones de arquitectura (ADRs embebidos)

### ADR-01 — Transporte de tiempo real: **SSE**, no WebSocket
El flujo es unidireccional (servidor → navegador). SSE es más simple, reconecta solo,
y FastAPI lo soporta con `StreamingResponse`. WebSocket sería over-engineering.
**Decidido: SSE.**

### ADR-02 — Normalización de eventos a un esquema único
Cada CLI emite un formato distinto. Se define un **evento canónico** (§6.3) y un parser
por proveedor que traduce su JSONL a ese esquema. El frontend solo conoce el canónico.
**Decidido: capa de normalización en `backend/streaming.py`.**

### ADR-03 — Autodetección de repos
Se escanean, en busca de carpetas con `.git/`: `~`, `~/GitHub`, `/mnt/Datos` (1 nivel de
profundidad cada una). Además se permite **path manual** en un input. Lista combinada,
ordenada por nombre, deduplicada. Configurable vía env `COUNCIL_REPO_ROOTS` (CSV).
**Decidido.**

### ADR-04 — Modo read-only por defecto
El consejo **debate**, no modifica. Codex corre `--sandbox read-only`. Claude/DeepSeek/
Gemini reciben en el prompt la instrucción explícita de **no escribir/editar/ejecutar
comandos mutantes**. Riesgo residual (skip-permissions podría escribir) documentado en §8;
mitigación dura opcional en backlog (worktree efímero). **Decidido: read-only por prompt + codex sandbox.**

### ADR-05 — Streaming real solo en Stage 1
Stage 1 (exploración del repo) es donde está la acción observable. Stage 2 (ranking) y
Stage 3 (síntesis) trabajan sobre texto ya producido; se muestran como pasos con spinner
y luego su resultado, sin streaming fino de tools. **Decidido.**

### ADR-06 — Concurrencia y aislamiento de procesos
Los 4 agentes de Stage 1 corren en paralelo (`asyncio.gather`). Cada uno es un subproceso
con su stdout en pipe, leído línea a línea de forma asíncrona. Un fallo de un agente no
tumba el debate (degradación elegante, ya presente). **Decidido.**

### ADR-07 — Sin cambios de stack
Se mantiene FastAPI + React/Vite. No se introducen frameworks nuevos. **Decidido.**

### ADR-08 — Registro de modelos data-driven (extensibilidad)
Sumar un modelo al consejo NO debe requerir tocar lógica. Se define un **registro**
declarativo (`backend/models_registry.py`) donde cada miembro es una entrada con su
transporte y parámetros. Tres clases de transporte:

| Clase | Cómo corre | Ojos y manos | Uso |
|---|---|---|---|
| `cli_native` | binario agéntico propio (`claude`, `codex`, `agy`) | ✅ | suscripciones flat |
| `anthropic_agent` | Claude Code apuntado a un endpoint Anthropic-compatible (env `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_MODEL`) | ✅ | DeepSeek (claude-ds), GLM y cualquier modelo de aiapi.world |
| `openai_api` | POST REST OpenAI-compatible | ❌ (ciego) | títulos, Q&A rápido sin repo |

Agregar GLM 5.2 (o Kimi, Qwen, MiniMax, Grok...) = **una entrada `anthropic_agent`**
apuntando a aiapi.world con el `model` deseado. El dispatcher de `providers.py` se
reescribe para leer del registro en vez de tener ramas `if model == ...` hardcodeadas.
**Decidido.**

### ADR-09 — aiapi.world como fuente de modelos "extra"; suscripciones se conservan
Estrategia **híbrida**:
- Miembros por **suscripción** (claude/codex/gemini) y **DeepSeek** se mantienen
  (costo marginal cero / muy bajo, ya configurados).
- **aiapi.world** se usa para **sumar variedad** que no se tiene por suscripción
  (GLM 5.2, Kimi, Grok, etc.). Paga por token pero ~50% más barato que oficial, una
  sola key, y vía su endpoint Anthropic todos pueden tener ojos y manos.
- Datos del proveedor (verbatim, confirmados 2026-06-23):
  - OpenAI-compatible: base `https://aiapi.world/v1`, header `Authorization: Bearer sk-...`
  - Anthropic-compatible (Claude Code): `ANTHROPIC_BASE_URL=https://aiapi.world` (sin `/v1`),
    `ANTHROPIC_AUTH_TOKEN=sk-...`
  - Key del usuario en archivo local `~/.aiapi_key` (chmod 600), fuera del repo y del
    historial de shell (mismo patrón que `~/.deepseek_key`).
**Decidido.**

---

### ADR-10 — Panel de configuración del consejo en la web
El registro de modelos (§7bis) es el **universo** de modelos posibles. Qué subconjunto
participa se guarda en una **config persistida** (`data/council_config.json`):
```json
{ "members": ["claude","codex","gemini","deepseek","glm"], "chairman": "claude" }
```
La web muestra **todos** los modelos del registro con su **estado de salud** (¿binario
presente? ¿key_file presente?), permite **activar/desactivar** cada uno con un toggle,
elegir el **chairman**, y persiste con un PUT. Un modelo sin credenciales se ve pero
aparece deshabilitado ("falta ~/.aiapi_key"). **Nunca se exponen las keys**, solo un bool
`available`. Cambios aplican a la próxima pregunta (sin reiniciar). **Decidido.**

Fuera de v1 (backlog): agregar modelos *nuevos* desde la web (input de `model id` de
aiapi que cree una entrada `anthropic_agent` al vuelo). v1 togglea lo que está en el registro.

## 5. Arquitectura de componentes

```
┌─────────────── Frontend (React/Vite :5173) ───────────────┐
│ RepoSelector  ── GET /api/repos                            │
│ CouncilConfig ── GET /api/models · PUT /api/council/config │
│ ChatInterface ── POST /api/conversations/{id}/message/stream (SSE)
│ LiveProgress  ── consume eventos SSE (canónicos)           │
│ Stage1/2/3    ── render de resultados (ya existe)          │
└───────────────────────────────────────────────────────────┘
                         │  HTTP + SSE
┌─────────────── Backend (FastAPI :8001) ───────────────────┐
│ routes:                                                    │
│   GET  /api/repos                  → lista repos detectados│
│   POST /api/conversations/{id}/message/stream → SSE        │
│   (se conserva el endpoint batch existente)                │
│ council.py    → run_full_council_streaming(query, cwd, emit)│
│ providers.py  → *_stream() por agente (emiten eventos)     │
│ streaming.py  → parsers por proveedor → evento canónico    │
│ repos.py      → autodetección de repositorios              │
└───────────────────────────────────────────────────────────┘
       │ subprocess (stream-json / --json / --print)
   claude · codex · agy(gemini) · claude-ds(deepseek)
```

---

## 6. Contratos de API

### 6.1 `GET /api/repos`
Devuelve repos detectados para el dropdown.
```json
{
  "repos": [
    {"name": "modar-erp", "path": "/home/andres/GitHub/modar-erp"},
    {"name": "Claude-office", "path": "/home/andres/Claude-office"},
    {"name": "trading-bot", "path": "/mnt/Datos/trading-bot"}
  ]
}
```

### 6.1b `GET /api/models`
Universo de modelos del registro + salud + si están activos. Para el panel de config.
```json
{
  "chairman": "claude",
  "models": [
    {"id":"claude","transport":"cli_native","available":true,"active":true,"reason":null},
    {"id":"codex","transport":"cli_native","available":true,"active":true,"reason":null},
    {"id":"glm","transport":"anthropic_agent","model":"glm-5.2","available":false,"active":false,"reason":"falta ~/.aiapi_key"},
    {"id":"deepseek-flash","transport":"openai_api","available":true,"active":false,"reason":"solo títulos"}
  ]
}
```
`available` = binario o key_file presente (chequeo de existencia, sin ping a la red).

### 6.1c `PUT /api/council/config`
```json
{ "members": ["claude","codex","gemini","deepseek","glm"], "chairman": "claude" }
```
Valida: cada id existe en el registro y está `available`; chairman ∈ members. Persiste en
`data/council_config.json`. Responde la config aplicada.

### 6.2 `POST /api/conversations/{id}/message/stream`
Body:
```json
{ "content": "¿la arquitectura de auth escala?", "repo_path": "/home/andres/GitHub/modar-erp" }
```
Validaciones: `repo_path` debe existir, ser directorio y estar bajo un root permitido
(anti path-traversal). Responde `text/event-stream`.

### 6.3 Evento canónico (SSE `data:` JSON)
```ts
type CouncilEvent =
  | { type: "stage";   stage: 1|2|3; status: "start"|"done" }
  | { type: "agent";   model: string; status: "working"|"done"|"error" }
  | { type: "tool";    model: string; tool: string; detail: string }   // "Read", "auth/mw.ts"
  | { type: "thought"; model: string; text: string }                    // delta de texto
  | { type: "result";  model: string; stage: 1; text: string }          // postura final del agente
  | { type: "ranking"; aggregate: Array<{model:string;average_rank:number;rankings_count:number}> }
  | { type: "final";   model: string; text: string }                    // síntesis del chairman
  | { type: "done" }
  | { type: "fatal";   message: string }
```
El stream cierra tras `{"type":"done"}`. Errores no fatales van como `agent:error`.

---

## 7. Plan de implementación (un solo tiro, en este orden)

1. **`backend/models_registry.py`** — el dict `REGISTRY` + `COUNCIL_MEMBERS`/`CHAIRMAN`/
   `TITLE_MODEL` (§7bis). `config.py` pasa a re-exportar de acá.
2. **`backend/repos.py`** — autodetección (`list_repos()`), validación de path (`is_allowed(path)`).
3. **`backend/providers.py`** — reescribir el dispatcher para leer del `REGISTRY` (una sola
   función por clase de transporte: `cli_native`, `anthropic_agent`, `openai_api`), en vez
   de ramas `if model == ...`. Conserva el modo batch + agrega variantes `*_stream`.
4. **`backend/streaming.py`** — parsers: `parse_claude_event(line)`, `parse_codex_event(line)`
   → `CouncilEvent`; helper `run_agent_stream(model, prompt, cwd, emit)` que lanza el
   subproceso con el flag de streaming correcto y emite eventos canónicos por cada línea.
   Gemini: emite `working` al inicio y `result` al final (sin tools). `anthropic_agent`
   (DeepSeek/GLM/aiapi) usa el mismo parser de claude (es Claude Code).
4. **`backend/council.py`** — `run_full_council_streaming(query, cwd, emit)`: Stage 1 con
   streaming real (emit por agente), Stage 2/3 con eventos `stage`/`result`/`ranking`/`final`.
5. **`backend/council_config.py`** — `load_config()`/`save_config()` sobre
   `data/council_config.json`; `health(model)` (existe binario/key_file → `available`,`reason`);
   `list_models()` (registro + salud + activo). El consejo lee `members`/`chairman` de acá.
6. **`backend/main.py`** — endpoints `GET /api/repos`, `GET /api/models`,
   `PUT /api/council/config`, y el POST `/stream` (SSE via `StreamingResponse`, generador
   async alimentado por una `asyncio.Queue` que `emit` llena).
7. **`frontend/src/api.js`** — `fetchRepos()`, `fetchModels()`, `saveCouncilConfig()`,
   `streamMessage()` (EventSource/fetch-stream).
8. **`frontend/src/components/RepoSelector.jsx`** (+ css) — dropdown + input manual.
9. **`frontend/src/components/CouncilConfig.jsx`** (+ css) — panel/modal: lista de modelos
   con toggle activar/desactivar, badge de salud (✓ / ✗ falta key), selector de chairman,
   botón guardar (PUT).
10. **`frontend/src/components/LiveProgress.jsx`** (+ css) — panel en vivo por agente con
    íconos por tool (🔍 grep, 📖 read, 🔧 bash, 💡 thought, ✅ done, ⏳ working).
11. **`frontend/src/App.jsx` / `ChatInterface.jsx`** — integrar selector de repo + panel de
    config (estado `currentRepo` en localStorage), enviar `repo_path`, consumir el stream,
    renderizar progreso y las 3 etapas.
12. **Prueba e2e** — levantar app, abrir config (ver salud de modelos, togglear), seleccionar
    `~/llm-council` (meta), preguntar algo, confirmar: repos listados, progreso en vivo de
    los agentes, Gemini "working"→result, ranking y síntesis finales. Documentar resultado.

---

## 7bis. Extensibilidad: registro de modelos (`backend/models_registry.py`)

Forma declarativa final. Sumar/quitar miembros = editar este dict.

```python
# claude-ds y GLM/aiapi comparten el patrón anthropic_agent; solo cambia base/model/token.
AIAPI_BASE = "https://aiapi.world"          # endpoint Anthropic-compatible (sin /v1)
AIAPI_KEY_FILE = "~/.aiapi_key"

REGISTRY = {
    # --- por suscripción (CLI nativo, flat) ---
    "claude":   {"transport": "cli_native", "bin": "claude"},
    "codex":    {"transport": "cli_native", "bin": "codex"},
    "gemini":   {"transport": "cli_native", "bin": "agy"},

    # --- DeepSeek como agente Claude Code (ya andando) ---
    "deepseek": {"transport": "anthropic_agent",
                 "base": "https://api.deepseek.com/anthropic",
                 "key_file": "~/.deepseek_key", "model": "deepseek-v4-pro",
                 "config_dir": "~/.claude-ds"},

    # --- modelos extra vía aiapi.world (una key, ojos y manos) ---
    "glm":      {"transport": "anthropic_agent", "base": AIAPI_BASE,
                 "key_file": AIAPI_KEY_FILE, "model": "glm-5.2",
                 "config_dir": "~/.claude-aiapi"},
    "kimi":     {"transport": "anthropic_agent", "base": AIAPI_BASE,
                 "key_file": AIAPI_KEY_FILE, "model": "kimi-k2.7-code",
                 "config_dir": "~/.claude-aiapi"},
    "grok":     {"transport": "anthropic_agent", "base": AIAPI_BASE,
                 "key_file": AIAPI_KEY_FILE, "model": "grok-4",
                 "config_dir": "~/.claude-aiapi"},

    # --- ciego, solo títulos (OpenAI-compatible) ---
    "deepseek-flash": {"transport": "openai_api",
                       "base": "https://api.deepseek.com/v1",
                       "key_file": "~/.deepseek_key", "model": "deepseek-v4-flash"},
}

COUNCIL_MEMBERS = ["claude", "codex", "gemini", "deepseek", "glm"]  # configurable
CHAIRMAN = "claude"
TITLE_MODEL = "deepseek-flash"
```

Notas:
- Cada `config_dir` distinto evita que las sesiones/credenciales de Claude Code se pisen
  entre proveedores (DeepSeek y aiapi usan dirs separados).
- Los `model` ids de aiapi (`glm-5.2`, `kimi-k2.7-code`, `grok-4`...) se confirman contra
  `https://aiapi.world/docs/models` / pricing antes de fijarlos (catálogo dinámico).

## 7ter. Inputs requeridos del usuario (no decidibles por Claude)

Dos cosas que el oneshot necesita y que **no puedo inventar**; el resto queda decidido:

1. **API key de aiapi.world** → guardarla en `~/.aiapi_key` (`chmod 600`). Sin esto, los
   miembros vía aiapi (`glm`, etc.) quedan deshabilitados pero el consejo igual corre con
   los de suscripción + DeepSeek.
2. **Qué modelos sumar al consejo** (`COUNCIL_MEMBERS`). Default propuesto:
   `claude + codex + gemini + deepseek + glm` (5 miembros). Si no se indica otra cosa,
   se implementa ese default.

## 8. Seguridad y riesgos

- **Path traversal** → `repo_path` validado contra roots permitidos y `os.path.realpath`.
- **Escritura accidental** (ADR-04): los agentes corren con skip-permissions y *podrían*
  escribir pese a la instrucción read-only. Mitigación v1: prompt explícito + codex sandbox
  read-only. Mitigación dura (backlog): correr cada agente en un `git worktree` efímero o
  copia, y descartar. **Riesgo aceptado para v1 sobre repos propios del usuario.**
- **Repos enormes** → los agentes pueden tardar/gastar tokens explorando. Mitigación: el
  prompt los guía a mapear primero y leer selectivo; timeout por agente (300s) ya existe.
- **DeepSeek = único costo real** (API barata); el resto es suscripción.

---

## 9. Criterios de aceptación

- [ ] La web lista repos de `~`, `~/GitHub`, `/mnt/Datos` y acepta path manual.
- [ ] El panel de config muestra todos los modelos del registro con su salud, permite
      activar/desactivar y elegir chairman, y persiste en `data/council_config.json`.
- [ ] Un modelo sin credenciales aparece deshabilitado con el motivo, no rompe nada.
- [ ] Al preguntar, los 4 agentes corren **dentro del repo elegido** (`cwd` correcto).
- [ ] El panel muestra en vivo tools/pensamiento de claude, codex y deepseek.
- [ ] Gemini muestra `⏳ working` y luego su postura.
- [ ] Se renderizan las 3 etapas + ranking agregado + síntesis del chairman.
- [ ] Un agente que falla no tumba el debate.
- [ ] El endpoint batch anterior sigue funcionando (no regresión).

---

## 10. Backlog (post-v1, no implementar ahora)

- Aislamiento por `git worktree` efímero (read-only duro).
- Persistir transcript de eventos para "replay" del debate.
- Clonar repos remotos desde la UI (pegar URL de GitHub).
- Agregar modelos *nuevos* desde la UI (input de `model id` de aiapi → crea entrada al vuelo).
- Health check con ping real a cada proveedor (v1 solo chequea existencia de binario/key).
- Anonimizar también Stage 3 (evitar autosesgo del chairman).
