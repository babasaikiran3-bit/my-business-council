# ADR 0002 — Estabilizar el baseline y el runtime antes de implementar Room

- Estado: Propuesto
- Fecha: 2026-07-11
- Precede a: ADR 0003 — Modo Room con turnos coordinados y trabajo paralelo en worktrees
- Relacionado: `docs/SSD.md`, ADR 0001

## Contexto

El proyecto dejó de ser la aplicación mínima basada en OpenRouter que describe el commit actual
de `master`. El working tree contiene una evolución sustancial:

- proveedores CLI y API declarativos;
- investigación previa a la deliberación;
- streaming SSE de actividad de agentes;
- selección y validación de repositorios;
- configuración persistente del consejo;
- almacenamiento principal en SQLite;
- preview y aprobación de documentos de consenso;
- frontend ampliado para progreso, repositorios y configuración.

Esta versión compila e importa en backend y produce un build frontend válido. Sin embargo, gran
parte de ella todavía no está commiteada, no hay tests automatizados, el lint no está en verde y
el README describe la arquitectura anterior.

Room agrega participantes persistentes, rondas, turnos, interrupciones y contexto incremental.
La fase posterior de trabajo paralelo agrega tareas, procesos concurrentes, ramas, worktrees,
commits e integración. Ambas funcionalidades multiplican la cantidad de estados y fallos que el
sistema debe recuperar.

Implementarlas directamente sobre el estado actual mezclaría tres esfuerzos difíciles de
separar:

1. consolidar la migración OpenRouter/JSON → providers/SQLite/SSE;
2. corregir el lifecycle y la seguridad de procesos existentes;
3. introducir las máquinas de estado de Room y worktrees.

Además, Git worktree necesita un commit base. El estado real del producto no puede ser baseline
de nuevas ramas mientras viva únicamente como modificaciones locales.

## Decisión

Crear una fase explícita de **estabilización previa**. ADR 0003 no entra en implementación hasta
que se cumpla el gate definido aquí.

La estabilización no busca rediseñar el producto ni implementar Room por adelantado. Busca dejar
una base versionada, testeable, recuperable y con límites claros para ejecutar agentes.

Se trabajará en siete frentes:

1. baseline Git y limpieza de artefactos;
2. paths y persistencia deterministas;
3. runtime unificado de workers;
4. ejecuciones durables y cancelables;
5. contratos tipados y tests;
6. separación de estado en el frontend;
7. documentación y operación reproducible.

## 1. Baseline Git

Antes de cambios arquitectónicos nuevos se creará un checkpoint de la aplicación actual.

El checkpoint debe:

- incluir la migración vigente de backend y frontend;
- incluir documentación y ADRs relevantes;
- excluir bases SQLite, logs, pidfiles, caches, builds y credenciales;
- registrar explícitamente la eliminación de `backend/openrouter.py` si la migración se confirma;
- pasar verificaciones mínimas de backend, frontend y whitespace;
- dejar el working tree limpio.

No se usarán stashes automáticos ni comandos destructivos para alcanzar ese estado. Los cambios
actuales pertenecen al usuario y deben revisarse como una unidad antes del commit.

El archivo `council.db` ubicado en la raíz se considera artefacto de ejecución, no fuente del
producto. Se deberá identificar cuál base contiene datos vigentes antes de moverlo o eliminarlo.

### Consecuencia para Room

El commit aprobado se convierte en el primer baseline desde el cual podrán crearse worktrees. Un
repo sucio continuará siendo válido para conversar en modo read-only, pero no para iniciar tareas
paralelas hasta que exista un checkpoint explícito, según ADR 0003.

## 2. Paths y persistencia deterministas

Las rutas de datos no dependerán del directorio desde el que se lanza Python.

Actualmente valores como:

```python
DB_PATH = "data/council.db"
```

son relativos al `cwd`. Esto puede crear bases diferentes al iniciar el backend desde launchers,
tests o shells distintos.

Se decide:

- definir una raíz de aplicación absoluta mediante `pathlib.Path`;
- derivar desde ella base de datos, configuración, runtime y directorio neutro de agentes;
- permitir overrides explícitos por variables de entorno para tests y despliegues;
- no usar el repo analizado como ubicación implícita de datos internos;
- verificar y documentar la migración desde conversaciones JSON legacy.

### Migraciones

La creación idempotente de tablas puede mantenerse para bootstrap, pero los cambios de esquema
deben adquirir versión antes de agregar Room.

La solución puede ser una tabla interna de migraciones o una herramienta dedicada. Debe ofrecer:

- número de versión aplicado;
- migraciones ordenadas y transaccionales;
- ejecución repetible;
- rollback manual documentado cuando una migración no sea reversible;
- base temporal aislada para tests.

No se agregarán las tablas de Room mediante una acumulación de `ALTER TABLE` implícitos durante
requests normales.

### Integridad y concurrencia

La secuencia de mensajes y eventos debe asignarse dentro de una transacción. Calcular
`MAX(position) + 1` sin una restricción única no es suficiente cuando puedan coexistir requests,
reconexiones y workers.

Antes de Room se definirán:

- restricciones únicas para posiciones o secuencias dentro de su stream;
- transacciones para append de mensajes/eventos;
- política de busy timeout y WAL;
- ownership de conexiones y operaciones bloqueantes;
- comportamiento ante duplicación o retry de un request.

## 3. Runtime unificado de workers

La lógica de ejecutar agentes se extraerá de la función monolítica de streaming y se formalizará
como un `WorkerExecutor`.

El executor representa capacidades, no solo nombres de modelo:

```text
WorkerSpec
  command
  environment
  supports_tools
  supports_streaming
  supports_write
  parser
  timeout_policy
  sandbox_policy
```

La configuración existente en `~/.bashrc` (`ds-run`, `codex-run`, `agy-run` y workers locales)
sirve como antecedente y UX humana, pero el backend no dependerá de funciones de un shell
interactivo. Los comandos y entornos necesarios vivirán en configuración declarativa o código
del proyecto, sin incluir secretos.

### Lifecycle obligatorio

Cada ejecución seguirá una secuencia explícita:

```text
created → starting → running → completed
                           ├→ failed
                           ├→ timed_out
                           └→ cancelled
```

El executor debe:

- lanzar cada worker en un process group controlable;
- consumir stdout y stderr concurrentemente;
- aplicar timeout de inactividad y, cuando corresponda, timeout total;
- distinguir salida válida, error del proveedor, timeout y cancelación;
- terminar procesos hijos además del proceso principal;
- esperar la recolección del proceso para no dejar zombies;
- preservar stderr acotado para diagnóstico;
- emitir un único estado terminal;
- limpiar archivos temporales aun ante excepciones;
- admitir un token o handle de cancelación.

No se abrirá `stderr=PIPE` sin un consumidor concurrente. Un worker que llena stderr no debe poder
bloquear indefinidamente el stream de stdout.

### Seguridad

Los permisos se conceden por ejecución:

- deliberación, investigación y Room conversacional: read-only;
- generación de preview de consenso: read-only y sin `cwd` escribible;
- escritura aprobada o tarea futura: capability explícita y temporal;
- ningún worker puede hacer push remoto por defecto.

`--dangerously-skip-permissions` y `danger-full-access` se consideran excepciones de transporte,
no garantías de seguridad. Cuando sean inevitables, deben quedar visibles en metadata y audit log.

## 4. Ejecuciones durables

La conexión SSE no será la única dueña del trabajo.

Hoy el request que transmite eventos también crea y espera la tarea. Una desconexión del browser
puede dejar ambiguo si la ejecución continúa, fue cancelada o terminó sin que el cliente reciba
el resultado.

Se introducirá el concepto de `run`:

```text
run
  id
  conversation_id
  kind
  status
  created_at
  started_at
  finished_at
  error
```

Y un log ordenado de eventos:

```text
run_event
  run_id
  sequence
  type
  payload
  created_at
```

Decisiones:

- persistir una transición antes de publicarla por SSE;
- usar secuencias monotónicas por run;
- permitir reconexión y replay desde la última secuencia observada;
- separar iniciar una ejecución de observar su stream;
- hacer idempotentes cancelación y consulta de estado;
- impedir dos runs deliberativos activos sobre la misma conversación salvo decisión posterior;
- persistir fallos parciales de agentes sin perder el resultado del resto del consejo.

Room reutilizará esta infraestructura para rondas y tareas, en lugar de inventar un segundo
lifecycle incompatible.

## 5. Contratos y calidad

### Eventos tipados

El contrato canónico de eventos dejará de ser una colección implícita de diccionarios. Se
definirán modelos discriminados para:

- etapas;
- estado de agentes;
- tools y thoughts;
- resultados y rankings;
- finalización, error y cancelación;
- títulos y metadata.

Backend y frontend deben validar o centralizar el manejo de eventos desconocidos. Los eventos
incompatibles requieren versionado del contrato.

### Suite mínima

Antes de comenzar ADR 0003 deben existir tests automatizados para:

1. parsers de eventos Claude y Codex;
2. lifecycle exitoso, timeout, stderr abundante, cancelación y proceso fallido;
3. ranking, anonimización y síntesis con providers falsos;
4. validación de repos y path traversal;
5. configuración y salud de modelos sin exponer secretos;
6. almacenamiento SQLite, migraciones e integridad de secuencias;
7. generación, preview y target seguro del consenso;
8. stream SSE y replay con eventos simulados;
9. reducer frontend ante secuencias normales, parciales y fallidas.

Los tests no llaman proveedores reales ni consumen créditos por defecto. Se usarán executors y
streams falsos reproducibles.

### Gate de calidad

El gate local mínimo será equivalente a:

```text
backend tests
backend import/compile
frontend tests
frontend lint
frontend build
git diff --check
```

Los tres errores y el warning de hooks detectados actualmente en frontend se corrigen dentro de
esta fase.

## 6. Estado del frontend

`App.jsx` no continuará absorbiendo cada nuevo evento y transición.

Se extraerán:

- cliente SSE/reconexión;
- reducer de conversación Council;
- estado de runs;
- acciones de documentación de consenso;
- manejo consistente de error y cancelación.

La actualización optimista debe reconciliarse con el estado persistido. Un error después de
guardar el mensaje del usuario no puede dejar al frontend creyendo que el mensaje fue eliminado
mientras la base lo conserva.

La UI de Room tendrá su propio reducer o máquina de estados. Compartirá componentes y transporte,
pero no agregará sus casos directamente al reducer de Council.

## 7. Documentación y operación

El README se actualizará para describir el producto real:

- providers actuales y requisitos de cada uno;
- SQLite como almacenamiento principal;
- investigación, SSE, selección de repo y configuración;
- scripts de arranque;
- variables de entorno y archivos de credenciales esperados;
- verificaciones y troubleshooting;
- límites de seguridad de los agentes.

También se reconciliará ADR 0001 con la implementación actual de consenso: el modelo genera una
preview read-only y el backend escribe un path restringido después de la aprobación.

Los launchers deberán usar la misma raíz de datos y producir estado/status coherente. La carga de
NVM no se asumirá implícita en shells no interactivos.

## Fuera de alcance

Esta fase no incluye:

- participantes o rondas de Room;
- handoff entre agentes;
- asignación de tareas de código;
- creación o integración de worktrees;
- push remoto;
- contenedores o sandbox fuerte por worker;
- rediseño visual general del frontend.

Puede introducir abstracciones que Room reutilizará, pero no comportamiento de producto visible
que pertenezca a ADR 0003.

## Secuencia de implementación

1. Inventariar y revisar el working tree actual.
2. Corregir `.gitignore`, paths de datos y artefactos ambiguos.
3. Crear el checkpoint aprobado.
4. Introducir migraciones e integridad de persistencia.
5. Extraer `WorkerExecutor` y endurecer lifecycle/cancelación.
6. Persistir runs y eventos; desacoplar SSE de la ejecución.
7. Tipar eventos y agregar fakes.
8. Construir la suite mínima y dejar lint/build en verde.
9. Extraer reducers y reconciliación del frontend.
10. Actualizar README, ADR 0001 y operación.
11. Ejecutar el gate completo y declarar cumplidos los criterios de salida.

## Consecuencias

### Positivas

- Room comienza desde un commit reproducible y compatible con worktrees.
- Fallos, timeouts y desconexiones dejan estados observables y recuperables.
- Los providers comparten un executor en vez de duplicar wrappers y permisos.
- Los tests reducen el riesgo de introducir una máquina de estados sobre comportamiento incierto.
- El frontend deja de depender de un componente coordinador monolítico.
- Paths y migraciones eliminan bases fantasma y evolución implícita del esquema.
- La documentación vuelve a representar el producto instalado.

### Costos

- Retrasa la primera funcionalidad visible de Room.
- Agrega persistencia de runs/eventos y una abstracción de ejecución antes de necesitarlas en toda
  su extensión.
- Requiere decidir el destino de datos legacy y cambios locales existentes.
- Algunos providers seguirán teniendo límites de sandbox que solo podrán mitigarse, no eliminarse.

El costo se acepta porque estas piezas serían necesarias durante Room y resultan más caras de
introducir después de que existan rondas y tareas reales.

## Alternativas consideradas

- **Implementar Room directamente y refactorizar después**: descartado; mezcla fallos actuales con
  los de la nueva máquina de estados.
- **Crear únicamente un commit y continuar**: insuficiente; resuelve el baseline pero no procesos,
  persistencia ni tests.
- **Mantener SSE acoplado al request**: descartado para operaciones largas y reconectables.
- **Reutilizar `.bashrc` mediante `bash -ic`**: descartado; depende de configuración interactiva,
  complica quoting y expande innecesariamente la autoridad del shell.
- **Adoptar inmediatamente una cola externa**: pospuesto; SQLite y tareas asyncio pueden cubrir el
  despliegue local inicial si se definen ownership e idempotencia.
- **Reescribir toda la aplicación**: descartado; los límites actuales de council, providers,
  storage y frontend son recuperables.

## Gate de entrada a ADR 0003

ADR 0003 puede comenzar cuando:

1. la versión actual está commiteada y el working tree queda limpio;
2. datos, logs y secretos están excluidos y usan paths absolutos o configurados;
3. existe un mecanismo versionado de migraciones;
4. `WorkerExecutor` consume stdout/stderr, cancela y clasifica estados terminales correctamente;
5. runs y eventos sobreviven a una desconexión y pueden reproducirse en orden;
6. no se ejecutan proveedores reales en tests;
7. backend tests/import y frontend tests/lint/build están en verde;
8. la lógica de eventos dejó de concentrarse en `App.jsx`;
9. README y ADR 0001 coinciden con la implementación vigente;
10. el gate completo puede ejecutarse mediante un comando documentado.
