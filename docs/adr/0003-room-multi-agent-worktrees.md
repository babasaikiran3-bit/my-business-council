# ADR 0003 — Modo Room con turnos coordinados y trabajo paralelo en worktrees

- Estado: Propuesto
- Fecha: 2026-07-11
- Prerrequisito: ADR 0002 — Estabilización del baseline y runtime de agentes
- Relacionado: `docs/SSD.md`, ADR 0001

## Contexto

El modo Council actual resuelve una consulta mediante un pipeline cerrado:

1. investigación opcional;
2. respuestas independientes de los miembros;
3. ranking ciego entre pares;
4. síntesis final del chairman.

Ese flujo es apropiado para deliberar y producir una respuesta consolidada, pero no para una
conversación persistente. El usuario necesita un segundo modo, **Room**, donde varios agentes y
el usuario compartan una sala, lean lo aportado por los demás y construyan una conversación en
el tiempo.

La dificultad central no es transportar mensajes sino administrar **quién tiene la palabra**.
Un free-for-all genera respuestas simultáneas que no se leen entre sí, conversaciones infinitas,
monopolios de un agente y consumo impredecible. Un moderador LLM dedicado agregaría costo,
latencia y decisiones opacas.

Además, la sala debe poder evolucionar de conversación a ejecución: el usuario quiere asignar
tareas de código a distintos agentes y permitir que trabajen en paralelo. Ejecutarlos sobre el
mismo working tree produciría carreras, cambios mezclados y una superficie de recuperación
inaceptable. Git worktrees permite dar a cada tarea un filesystem y una rama separados, aunque
no constituye por sí solo una frontera completa de seguridad porque los worktrees comparten el
repositorio Git y los procesos conservan los permisos del usuario.

Por lo tanto hay dos problemas relacionados pero distintos:

- **coordinación conversacional**: miembros, turnos, rondas, contexto e interrupciones;
- **coordinación laboral**: tareas, autorización de escritura, worktrees, commits, revisión e
  integración.

## Decisión

Agregar un segundo tipo de conversación, sin reemplazar el Council existente:

```text
conversation.mode = "council" | "room"
```

- `council` conserva el pipeline Stage 0–3 actual.
- `room` utiliza un orquestador de rondas y participantes persistentes.
- Hablar en la sala y trabajar sobre código son capacidades separadas.
- Ningún agente obtiene escritura por participar, ser mencionado o sugerir una solución.
- Una tarea de código comienza únicamente después de una asignación explícita del usuario.

## 1. Modelo conversacional

### 1.1 Rondas

Cada mensaje del usuario abre una ronda. Al comenzar se toma un snapshot de los participantes
activos; incorporaciones o salidas posteriores no alteran silenciosamente esa lista.

El orden de palabra se calcula así:

```text
agentes mencionados por el usuario
→ handoff válido del hablante anterior
→ agentes restantes en orden rotativo
→ devolución de la palabra al usuario
```

Reglas:

1. `@agent` da prioridad a ese agente. Varias menciones respetan el orden del mensaje.
2. Sin menciones, el primer orador rota entre rondas para evitar un líder permanente.
3. Cada agente activo puede hablar como máximo una vez por ronda.
4. Cada respuesta ve el mensaje del usuario y todo lo ya dicho en la ronda.
5. Un agente puede hacer handoff a otro participante que todavía no habló.
6. Un handoff inválido, circular o dirigido a alguien que ya habló se ignora y continúa la cola.
7. Cuando todos respondieron o pasaron, la sala queda esperando al usuario.
8. No se inicia una nueva ronda de agentes de manera autónoma.

El backend, no un LLM, es el **controlador del micrófono**. La política debe ser determinista,
observable y reproducible.

### 1.2 Handoff y pass

Los proveedores devolverán, además del texto visible, control estructurado equivalente a:

```json
{
  "action": "reply | pass",
  "handoff_to": "codex | null"
}
```

El formato concreto puede implementarse con un sobre estructurado, tool call o un marcador que
el backend retire antes de persistir el mensaje. Nunca se confiará en el texto visible para
alterar directamente el estado sin validación.

`pass` cuenta como participación: un agente no está obligado a inventar una opinión cuando no
tiene nada sustancial que agregar. La UI lo representa de forma compacta y no como una respuesta
vacía.

### 1.3 Interrupción del usuario

El usuario siempre tiene prioridad semántica.

En v1, si escribe durante una respuesta:

1. se deja terminar al hablante actual;
2. se cancela la cola pendiente;
3. el nuevo mensaje abre otra ronda.

La cancelación dura de un subproceso en curso queda para una fase posterior, con un botón
explícito `Interrumpir ahora`. No se mezclan dos rondas activas en una misma sala.

### 1.4 Participantes y presencia

Cada participante tiene un estado conversacional:

- `active`: recibe un turno automático en cada ronda;
- `listening`: recibe contexto, pero solo habla ante mención explícita;
- `muted`: permanece visible, no recibe turnos ni menciones ejecutables;
- `left`: permanece en el historial, pero deja de recibir contexto nuevo.

Las transiciones son acciones persistidas y visibles en la línea de tiempo:

```text
Kimi se unió a la sala como listener.
Gemini fue silenciado.
DeepSeek salió de la sala.
```

La UI ofrecerá controles gráficos y podrá aceptar comandos equivalentes:

```text
/invite kimi
/invite grok --listening
/mute gemini
/unmute gemini
/remove deepseek
```

Los agentes pueden **sugerir** invitar, silenciar o retirar participantes, pero solo el usuario
puede confirmar cambios de membresía. Una frase generada por un modelo nunca ejecuta por sí sola
una mutación de la sala.

### 1.5 Entrada, salida y contexto

Un agente que entra no recibe ciegamente todo el historial. El backend construye un paquete de
contexto con:

- resumen acumulado de la sala;
- objetivo actual;
- participantes y estados;
- decisiones tomadas;
- desacuerdos y preguntas abiertas;
- últimos N mensajes completos;
- mensaje que originó su entrada, si corresponde.

Al reingresar se agrega un resumen de lo ocurrido durante su ausencia. Los mensajes previos no
se reescriben y conservan la identidad original del hablante.

El resumen es memoria derivada, no fuente de verdad. La fuente de verdad continúa siendo el log
ordenado de eventos y mensajes.

## 2. Trabajo de código desde la sala

### 2.1 Asignación explícita

Una tarea nace mediante una acción confirmada del usuario, por ejemplo:

```text
/assign @claude "Refactorizar el middleware de autenticación"
/assign @codex "Agregar migración y tests"
```

Una asignación contiene como mínimo:

```json
{
  "title": "Refactorizar middleware de autenticación",
  "assignee": "claude",
  "base_ref": "<session baseline>",
  "expected_paths": ["backend/auth/**"],
  "depends_on": [],
  "acceptance_criteria": [
    "los tests existentes pasan",
    "no cambia la API pública"
  ]
}
```

`expected_paths` es una declaración de intención y sirve para advertir solapamientos; no debe
convertirse inicialmente en un bloqueo rígido porque una tarea legítima puede descubrir que
necesita tocar otros archivos.

### 2.2 Estados laborales

La presencia conversacional y el estado laboral son dimensiones independientes. Un agente puede
estar `listening` y a la vez `working`.

```text
idle → assigned → working → review_ready → accepted
                         ├→ changes_requested → working
                         ├→ failed
                         └→ cancelled
```

Reglas de v1:

- máximo una tarea activa por agente;
- límite global de tareas concurrentes configurable;
- una tarea puede cancelarse sin retirar al agente de la sala;
- terminar de hablar no termina la tarea y terminar la tarea no concede otro turno;
- los eventos de trabajo aparecen en la sala, pero no consumen turnos conversacionales.

### 2.3 Un worktree por tarea

Cada tarea con escritura recibe:

- un worktree exclusivo;
- una rama exclusiva;
- `cwd` fijado al worktree;
- un identificador estable de room, task y agent.

Convención propuesta:

```text
branch:   council/<room-id>/<task-id>/<agent-id>
worktree: ~/.llm-council/worktrees/<repo-id>/<room-id>/<task-id>-<agent-id>
```

Los worktrees se ubican fuera del repositorio analizado para evitar nesting, indexación
accidental y contaminación del working tree principal.

El agente debe dejar uno o más commits autocontenidos. Al finalizar informa:

- resumen de la implementación;
- archivos modificados;
- commits producidos;
- verificaciones ejecutadas y resultados;
- riesgos, deuda y trabajo pendiente;
- diferencias respecto del alcance declarado.

No se considera `review_ready` una tarea con cambios sin commit, salvo fallo explícito que deba
preservarse para diagnóstico.

### 2.4 Solapamientos y dependencias

Antes de iniciar una tarea, el orquestador compara `expected_paths` con tareas activas y muestra
una advertencia cuando hay intersección. El usuario puede:

- mantener las tareas paralelas;
- serializarlas;
- redefinir el alcance;
- declarar una dependencia.

Una tarea dependiente no parte del baseline original: arranca cuando su dependencia fue aceptada
y utiliza la rama o commit aprobado como nueva base.

El sistema no promete ausencia de conflictos. Promete aislamiento del filesystem, trazabilidad
y un lugar controlado donde resolverlos.

### 2.5 Revisión e integración

En v1 no hay merge ni push automático.

El flujo es:

1. el agente deja commits en su rama;
2. la UI muestra diff, commits y verificaciones;
3. el usuario puede pedir revisión a otro agente;
4. el usuario acepta, pide cambios o cancela;
5. la integración requiere una aprobación explícita adicional.

Cuando hay múltiples ramas o conflictos, se crea un **worktree de integración** separado. Un
agente integrador puede combinar los commits, resolver conflictos y ejecutar la suite sin tocar
el working tree principal. El resultado se presenta nuevamente para aprobación.

La integración podrá usar merge o cherry-pick según el caso, pero nunca hará push remoto en v1.
Aceptar una tarea y aplicarla sobre la rama objetivo son acciones diferentes.

## 3. Repositorios sucios y baseline de sesión

Git worktree parte de un commit; no hereda modificaciones locales ni archivos sin seguimiento.
Crear ramas desde `HEAD` en un repo sucio haría que los agentes trabajen sobre una realidad
distinta de la que ve el usuario.

Por seguridad, v1 requiere una de estas condiciones antes de iniciar la primera tarea:

- working tree limpio; o
- checkpoint commit creado o seleccionado explícitamente por el usuario.

No se ejecutarán `stash`, commits en la rama del usuario ni limpiezas automáticas.

Una fase posterior podrá construir un **snapshot temporal** bajo una referencia interna sin
mover la rama del usuario. Esa opción deberá definir con precisión inclusión de archivos
untracked, respeto de `.gitignore`, secretos, submódulos y limpieza de refs. Hasta entonces, un
repo sucio bloquea la ejecución con escritura, pero no el chat read-only.

## 4. Seguridad y límites de autoridad

Un worktree es aislamiento operativo, no sandbox de seguridad. Todos comparten el mismo `.git`
y un proceso con permisos amplios podría acceder a otros paths del sistema.

Cada worker debe aplicar defensa en profundidad:

1. `cwd` fijado al worktree asignado.
2. Escritura deshabilitada hasta que exista una tarea autorizada.
3. Codex ejecutado con `workspace-write` dentro de su worktree.
4. Proveedores basados en Claude/Anthropic ejecutados con el mecanismo más restrictivo
   disponible; `--dangerously-skip-permissions` no se considera una frontera suficiente.
5. Prompt de sistema que prohíba operar sobre otros worktrees, la rama objetivo o remotos.
6. Denegación de push, force-push, reset destructivo, clean, rebase de ramas ajenas y borrado de
   worktrees mediante una capa de ejecución controlada cuando el transporte lo permita.
7. Timeout, cancelación y límites de concurrencia.
8. Registro de comandos, eventos, archivos tocados, commits y resultado de verificaciones.
9. Validación post-ejecución de que los cambios pertenecen al worktree y a la rama asignados.
10. Ningún secreto se incluye en resúmenes, prompts de handoff o eventos de UI.

Las capacidades se conceden por tarea, no por agente de manera permanente. Terminar, cancelar o
fallar una tarea revoca la autorización de escritura asociada.

## 5. Persistencia

El esquema conceptual incorpora:

```text
rooms
  conversation_id, round_number, rotating_cursor, summary, active_round_id

room_participants
  conversation_id, model_id, presence, joined_at, left_at

room_messages
  conversation_id, round_id, speaker_type, speaker_id, content, action, created_at

room_tasks
  id, conversation_id, assignee, title, status, base_ref, branch, worktree_path,
  expected_paths, acceptance_criteria, depends_on, result, created_at, updated_at

room_task_events
  task_id, sequence, type, payload, created_at
```

La implementación puede conservar JSON dentro de columnas SQLite para payloads variables, pero
los identificadores, estados, secuencias y relaciones importantes deben ser consultables y tener
restricciones de integridad.

La cola de turnos y las transiciones laborales deben persistirse antes de emitir sus eventos SSE,
para que una reconexión pueda reconstruir el estado sin inventarlo desde la UI.

## 6. API y eventos

La forma final se definirá durante implementación, pero el límite funcional será equivalente a:

```text
POST /api/conversations/{id}/room/messages
POST /api/conversations/{id}/room/participants
PATCH /api/conversations/{id}/room/participants/{model}
POST /api/conversations/{id}/room/tasks
POST /api/conversations/{id}/room/tasks/{task}/cancel
POST /api/conversations/{id}/room/tasks/{task}/review
POST /api/conversations/{id}/room/tasks/{task}/accept
POST /api/conversations/{id}/room/tasks/{task}/integrate
GET  /api/conversations/{id}/room/stream
```

Se reutiliza SSE para eventos unidireccionales. Los comandos del usuario siguen siendo HTTP
explícito; no se necesita WebSocket mientras el cliente no requiera un canal bidireccional
persistente.

Eventos adicionales al contrato actual:

```text
room.round.started | room.round.completed | room.round.cancelled
room.participant.joined | presence_changed | left
room.turn.started | passed | completed
room.task.assigned | started | progress | verification | review_ready
room.task.failed | cancelled | changes_requested | accepted | integrated
room.integration.conflict
```

Todo evento incluye ids de conversación, ronda o tarea, más un número de secuencia cuando
corresponda. La UI no debe inferir estados críticos únicamente del orden de llegada de texto.

## 7. Experiencia de usuario

La sala mostrará:

- participantes como chips con presencia y estado laboral;
- agente que tiene la palabra y cola pendiente;
- límites de ronda y botón para detenerla;
- tareas como paneles separados del chat;
- progreso resumido de tools y verificaciones;
- diff, commits y resultado de tests al terminar;
- advertencias de paths solapados, repo sucio y conflictos;
- acciones explícitas para revisar, aceptar e integrar.

Mensajes del sistema como ingresos, salidas y cambios de tarea viven en la línea de tiempo, pero
se distinguen visualmente de los mensajes humanos y de agentes.

## 8. Componentes

Se agregan dos límites principales:

- `RoomOrchestrator`: participantes, rondas, cola, handoff, pass, interrupción, contexto y SSE.
- `WorktreeManager`: baseline, ramas, worktrees, lifecycle, validaciones y limpieza.

El registro de modelos y `providers.py` continúan resolviendo transportes. La ejecución de una
tarea reutiliza `cwd` y streaming, pero recibe un contexto y permisos distintos de una respuesta
conversacional.

La persistencia no debe acoplar el Room a la representación Stage 1/2/3. Ambos modos comparten
conversaciones y proveedores, no su máquina de estados.

## 9. Fases

### Fase 1 — Sala conversacional

- `conversation.mode=room`;
- participantes y presencia;
- rondas secuenciales;
- menciones, rotación, handoff y pass;
- interrupción blanda;
- resumen y entrada tardía;
- streaming y persistencia, siempre read-only.

### Fase 2 — Tareas aisladas

- `/assign` y estados laborales;
- repos limpios o checkpoint explícito;
- un worktree y rama por tarea;
- ejecución paralela limitada;
- commits, progreso, diff y verificaciones;
- cancelación y limpieza;
- sin integración automática.

### Fase 3 — Revisión e integración

- revisión cruzada por agentes;
- aceptación y changes requested;
- dependencias entre tareas;
- worktree integrador;
- resolución de conflictos y aplicación aprobada sobre la rama objetivo.

### Backlog

- interrupción dura del proceso activo;
- snapshot temporal seguro de repos sucios;
- agentes que levantan la mano y compiten por el siguiente turno;
- moderador LLM opcional como política seleccionable, no predeterminada;
- push remoto con autorización separada y controles adicionales;
- aislamiento fuerte mediante contenedores o sandbox por worker.

## Consecuencias

### Positivas

- La conversación se vuelve acumulativa y legible en vez de una colección de respuestas
  simultáneas.
- La rotación, menciones y handoff combinan previsibilidad con dinámica natural.
- Los agentes pueden especializarse y atacar tareas independientes en paralelo.
- Los worktrees mantienen separados los cambios y protegen el working tree principal.
- La revisión humana permanece en los puntos irreversibles: escribir, aceptar, integrar y push.
- Se reutilizan proveedores, SSE, selección de repos y gran parte del runtime existente.

### Costos y riesgos

- Aparece una máquina de estados distribuida entre conversación, procesos, Git, SQLite y UI.
- Resumir contexto puede perder matices; enviar demasiado contexto aumenta costo y latencia.
- Trabajo paralelo no garantiza integración paralela ni ausencia de conflictos semánticos.
- Worktrees y ramas abandonados requieren garbage collection y recuperación tras crashes.
- CLIs con permisos amplios pueden escapar del aislamiento operativo si no se endurece la capa de
  ejecución.
- Tests ejecutados en paralelo pueden competir por puertos, bases, caches y servicios externos.
- La trazabilidad y la idempotencia son obligatorias para evitar tareas o integraciones duplicadas.

## Alternativas consideradas

- **Free-for-all simultáneo**: descartado como default; los agentes no leen aportes posteriores y
  el costo/convergencia son impredecibles.
- **Round-robin fijo eterno**: descartado como única política; es predecible pero ignora menciones,
  relevancia y continuidad del diálogo.
- **Moderador LLM obligatorio**: descartado inicialmente por costo, latencia y opacidad.
- **Agente actual elige libremente siempre al siguiente**: descartado; permite ciclos, camarillas
  y starvation. El handoff se acepta solo dentro de una cola validada.
- **Todos escriben sobre el working tree principal**: descartado por carreras y mezcla de cambios.
- **Una rama sin worktree por agente**: insuficiente para procesos concurrentes con archivos de
  trabajo reales.
- **Merge automático al finalizar**: descartado para v1; terminar código no equivale a aprobarlo.
- **Stash automático de cambios locales**: descartado; muta estado valioso del usuario y complica
  la recuperación.
- **Copias completas del repositorio**: aíslan mejor algunos efectos, pero multiplican espacio,
  tiempo y configuración; quedan como fallback para repos sin soporte de worktrees.

## Criterios de aceptación de la decisión

La propuesta se considera correctamente implementada cuando:

1. una room puede mantener participantes y varias rondas sin ejecutar Stage 1–3;
2. el orden es determinista, las menciones tienen prioridad y ningún agente habla dos veces por
   ronda;
3. entrar, escuchar, silenciar, salir y reingresar son persistentes y visibles;
4. el usuario puede interrumpir una cola sin corromper el historial;
5. ningún participante obtiene escritura sin una tarea autorizada;
6. dos tareas independientes pueden trabajar simultáneamente en worktrees distintos;
7. el working tree principal no cambia durante la ejecución de esas tareas;
8. cada resultado contiene commits, diff y verificaciones trazables;
9. aceptar no integra, e integrar requiere confirmación explícita;
10. un crash o reconexión permite recuperar el estado de la sala y las tareas sin duplicarlas.
