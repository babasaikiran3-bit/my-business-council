# ADR 0001 — El chairman puede escribir el consenso en el repositorio analizado

- Estado: Aceptado
- Fecha: 2026-06-23
- Contexto previo: `docs/SSD.md` §8 (seguridad: read-only por defecto)

## Contexto

Hasta ahora el consejo era estrictamente **read-only** sobre el repo analizado:
- Stage 1 (miembros) exploran con `cwd=repo`; codex con `--sandbox read-only`, el resto
  (claude / anthropic_agent / gemini) corren con `--dangerously-skip-permissions` pero se
  les instruye no escribir.
- Stage 3 (chairman) corría **sin `cwd` y sin manos**: solo sintetizaba texto.

El usuario necesita que, cuando los 4 modelos llegan a un consenso, ese consenso quede
**documentado dentro del propio repositorio** (no solo en la UI/DB), para que viva con el
código y entre al control de versiones del proyecto analizado.

## Decisión

Habilitar escritura **acotada**, no un permiso general:

1. **Deliberar y documentar están separados.** El debate (Stages 1-3) es SIEMPRE read-only.
   La escritura es una **acción explícita posterior**: una vez que el consejo llegó al consenso,
   el usuario decide si lo persiste.
2. **Acción por botón, armada por checkbox.** En la UI hay un checkbox
   ("✍️ Permitir documentar el consenso en el repo", habilitado solo si hay repo) que **habilita
   un único botón "📝 Documentar lo decidido"**. El botón solo se activa si: checkbox marcado +
   repo seleccionado + existe un Stage 3 en el último turno + no fue ya documentado.
3. **Solo el chairman** escribe, y documenta el consenso **YA alcanzado** (no re-delibera):
   endpoint `POST /api/conversations/{id}/document-consensus` → `council.document_consensus`,
   que corre el chairman con `cwd=repo` + `allow_write=True`.
4. **Solo si hay repo** (`cwd`). Sin repo (Q&A general) el botón nunca se habilita; jamás se
   escribe en el directorio neutro `data/agent-cwd`.
5. **Ubicación convenida**: el chairman crea `docs/council/<slug>.md` dentro del repo, con la
   pregunta, el consenso, acuerdos, disensos y próximos pasos. Declara la ruta con una línea
   `CONSENSUS_FILE: ...` que el backend extrae, devuelve a la UI y persiste en
   `stage3`/`consensus_file` del mensaje (mostrado como banner verde).

### Mecánica

- `providers.query_model(..., allow_write: bool)`:
  - `cli_native` codex → `--sandbox workspace-write` (antes siempre `read-only`).
  - `cli_native` claude / `anthropic_agent` → ya podían escribir con
    `--dangerously-skip-permissions`; el control real es el prompt + pasar `cwd`.
  - `openai_api` (deepseek-flash) es ciego: ignora `allow_write` (no tiene tools). Si se elige
    un chairman de este tipo con `write_consensus`, no se creará archivo (degradación silenciosa).
- `council.stage3_synthesize_final(..., cwd, write_consensus)` arma el bloque de instrucción de
  escritura y corre el chairman con `cwd=repo` + `allow_write=True` solo cuando ambos están.

## Consecuencias

**Positivas**
- El consenso queda versionado junto al código del repo analizado.
- Cambio mínimo y reversible: desmarcar el checkbox restaura el comportamiento read-only.
- El blast radius está acotado a un solo agente, una sola etapa, una consulta puntual.

**Riesgos / residuales**
- Con `write_consensus=true` el chairman corre con escritura en TODO el `cwd`, no solo en
  `docs/council/`. Confiamos en la instrucción del prompt + en que es opt-in consciente; no hay
  enforcement técnico de "solo ese subdirectorio". Mitigación futura: worktree efímero o copiar
  el repo (ya estaba en el backlog del SSD §10) y commitear/diff de vuelta.
- El repo debería estar bajo git para poder revisar/revertir lo que escriba el chairman.
- codex en `workspace-write` puede tocar el árbol de trabajo; los demás CLIs también. Revisar el
  `git diff` después de una corrida con escritura es responsabilidad del usuario.

## Alternativas consideradas

- **Siempre activo (sin flag)**: descartado; escribir en el repo es difícil de revertir y no
  debería pasar sorpresivamente al seleccionar un repo.
- **El backend escribe el archivo** (en vez del agente): más seguro, pero pierde la gracia de que
  el modelo redacte y ubique el documento con criterio; se reconsiderará si el prompt-driven
  resulta poco fiable.
