"""WorkerExecutor — unified subprocess lifecycle for agent CLIs.

Aligned with ADR 0002 §3.  Each execution follows:

    created → starting → running → completed
                                ├→ failed
                                ├→ timed_out
                                └→ cancelled

Features:
- Controllable process group (start_new_session + killpg)
- Concurrent stdout / stderr consumption (stderr reader task drains pipe)
- Bounded stderr retention (last 10 KiB kept for diagnostics)
- Inactivity timeout (per-read-line deadline)
- Outcome classification (completed / failed / timed_out / cancelled)
- CancellationToken for cooperative cancellation
- Child-process termination and reaping
- Temp-file cleanup on all paths
"""

from __future__ import annotations

import asyncio
import os
import signal
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class WorkerOutcome(str, Enum):
    """Terminal state of a worker execution."""
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class WorkerResult:
    """Structured result from WorkerExecutor.run()."""
    outcome: WorkerOutcome
    final_text: Optional[str] = None
    """Accumulated final text (or None if the run didn't produce one)."""
    stderr_tail: str = ""
    """Last ~10 KiB of stderr, decoded with replacement characters."""
    returncode: Optional[int] = None
    """Exit code (None when the process was killed by signal or never started)."""
    error_message: Optional[str] = None
    """Provider / executor error when outcome is FAILED."""


class CancellationToken:
    """Lightweight cooperative cancellation handle.

    The caller creates a token, passes it to the executor, and calls
    ``cancel()`` from another coroutine / callback when the run should stop.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    # -- read-only property (no await needed) --
    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    # -- mutation --
    def cancel(self) -> None:
        self._event.set()

    # -- for use inside executor loops --
    async def wait(self) -> None:
        await self._event.wait()


# Type alias for the parser callable used by streaming.py.
# (event list, optional final text)
EventParser = Callable[[Dict[str, Any], str], Tuple[List[Dict[str, Any]], Optional[str]]]

# Type alias for the emit callback.
EmitFn = Callable[[Dict[str, Any]], None]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STDERR_MAX_BYTES = 10 * 1024  # 10 KiB
_KILL_GRACE = 5.0              # seconds to wait after SIGTERM before SIGKILL
_STDERR_DRAIN = 5.0            # seconds to wait for stderr task to finish


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _reap(proc: asyncio.subprocess.Process) -> Optional[int]:
    """Wait for *proc* to exit (no signal).  Returns the exit code or ``None``."""
    if proc.returncode is not None:
        return proc.returncode
    try:
        return await asyncio.wait_for(proc.wait(), timeout=_KILL_GRACE)
    except asyncio.TimeoutError:
        return None


async def _terminate_and_reap(proc: asyncio.subprocess.Process) -> Optional[int]:
    """SIGTERM → wait → SIGKILL → wait for the process group led by *proc*.

    Escalates after ``_KILL_GRACE`` seconds if the process hasn't exited.
    Returns the exit code or ``None`` when even SIGKILL didn't work.
    """
    if proc.returncode is not None:
        return proc.returncode

    pid = proc.pid
    if pid is None:
        return None

    # ── SIGTERM ──────────────────────────────────────────────────────
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return proc.returncode  # already gone

    try:
        return await asyncio.wait_for(proc.wait(), timeout=_KILL_GRACE)
    except asyncio.TimeoutError:
        pass

    # ── SIGKILL escalation ───────────────────────────────────────────
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        return proc.returncode

    try:
        return await asyncio.wait_for(proc.wait(), timeout=_KILL_GRACE)
    except asyncio.TimeoutError:
        return None


async def _drain_stderr(stderr: asyncio.StreamReader, max_bytes: int) -> str:
    """Consume *stderr* until EOF, keeping at most *max_bytes* tail bytes."""
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await stderr.read(4096)
        if not chunk:
            break
        if total < max_bytes:
            chunks.append(chunk)
            total += len(chunk)
    raw = b"".join(chunks)
    if len(raw) > max_bytes:
        raw = raw[-max_bytes:]  # keep the tail
    return raw.decode(errors="replace")


# ---------------------------------------------------------------------------
# WorkerExecutor
# ---------------------------------------------------------------------------

class WorkerExecutor:
    """Unified subprocess lifecycle for agent CLIs.

    Launch, stream, and terminate a subprocess with concurrent stderr
    consumption, inactivity timeout, cancellation support, and
    deterministic outcome classification.

    Parameters
    ----------
    argv:
        Command + arguments to execute.
    parser:
        Callable ``(json_dict, model_id) -> (list_of_events, final_text_or_None)``.
        Same contract as ``parse_claude_event`` / ``parse_codex_event``.
    model_id:
        Passed through to *parser* for event tagging.
    env:
        Extra environment variables (merged on top of ``os.environ``).
    cwd:
        Working directory for the subprocess.
    inactivity_timeout:
        Seconds without a stdout line before declaring ``TIMED_OUT``.
    final_file:
        Optional path read after successful exit (Codex ``-o`` pattern).
    cancel_token:
        Optional ``CancellationToken`` that the caller can signal to abort.
    """

    def __init__(
        self,
        argv: List[str],
        parser: EventParser,
        model_id: str,
        *,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        inactivity_timeout: float = 300.0,
        final_file: Optional[str] = None,
        cancel_token: Optional[CancellationToken] = None,
    ) -> None:
        self._argv = list(argv)
        self._parser = parser
        self._model_id = model_id
        self._env = env
        self._cwd = cwd
        self._inactivity_timeout = inactivity_timeout
        self._final_file = final_file
        self._cancel_token = cancel_token

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, emit: EmitFn) -> WorkerResult:
        """Execute the subprocess, streaming parsed events via *emit*.

        Returns a ``WorkerResult`` whose ``outcome`` field is always one of
        the four terminal values.
        """
        # --- prepare environment ----------------------------------------
        run_env: Optional[Dict[str, str]] = None
        if self._env:
            run_env = {**os.environ, **self._env}

        # --- launch ------------------------------------------------------
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
                env=run_env,
                start_new_session=True,  # gives us a dedicated process group
            )
        except Exception as exc:
            return WorkerResult(
                outcome=WorkerOutcome.FAILED,
                error_message=f"launch failed: {exc}",
            )

        # --- concurrent stderr consumer ----------------------------------
        stderr_task = asyncio.create_task(
            _drain_stderr(proc.stderr, _STDERR_MAX_BYTES)
        )

        result: Optional[WorkerResult] = None
        try:
            result = await self._stream_loop(proc, emit)
        except Exception as exc:
            # Something unexpected blew up inside the streaming machinery
            # itself (not a subprocess failure).  Kill and classify.
            await _terminate_and_reap(proc)
            result = WorkerResult(
                outcome=WorkerOutcome.FAILED,
                error_message=str(exc),
            )
        finally:
            # Ensure the stderr consumer is done.
            if not stderr_task.done():
                stderr_task.cancel()
            tail = ""
            try:
                tail = await asyncio.wait_for(
                    stderr_task, timeout=_STDERR_DRAIN
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                tail = "(stderr drain timed out)"
            if result is not None:
                result.stderr_tail = tail

        # --- post-exit: read final_file if applicable --------------------
        if self._final_file and result.outcome == WorkerOutcome.COMPLETED:
            try:
                with open(self._final_file) as fh:
                    txt = fh.read().strip()
                if txt:
                    result.final_text = txt
            except OSError:
                pass

        return result

    # ------------------------------------------------------------------
    # Streaming loop
    # ------------------------------------------------------------------

    async def _stream_loop(
        self,
        proc: asyncio.subprocess.Process,
        emit: EmitFn,
    ) -> WorkerResult:
        """Read stdout line-by-line with cancellation and inactivity checks."""
        final_text: Optional[str] = None

        while True:
            # --- cancellation check (inline, no task overhead) --------------
            if self._cancel_token and self._cancel_token.cancelled:
                await _terminate_and_reap(proc)
                return WorkerResult(outcome=WorkerOutcome.CANCELLED)

            # --- read one line with inactivity timeout --------------------
            read_task = asyncio.create_task(proc.stdout.readline())

            wait_tasks: List[asyncio.Task] = [read_task]
            if self._cancel_token:
                cancel_task = asyncio.create_task(self._cancel_token.wait())
                wait_tasks.append(cancel_task)
            else:
                cancel_task = None

            done, pending = await asyncio.wait(
                wait_tasks,
                timeout=self._inactivity_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Tear down the tasks we didn't use.
            for t in pending:
                t.cancel()

            # --- classify what happened ----------------------------------
            if not done:
                # No task completed → inactivity timeout.
                await _terminate_and_reap(proc)
                return WorkerResult(outcome=WorkerOutcome.TIMED_OUT)

            if cancel_task is not None and cancel_task in done:
                # Cancellation token fired.
                await _terminate_and_reap(proc)
                # Dispose of the readline result (if any) to avoid leaks.
                if read_task in done:
                    try:
                        read_task.result()
                    except Exception:
                        pass
                return WorkerResult(outcome=WorkerOutcome.CANCELLED)

            # readline completed
            line: bytes = read_task.result()
            if not line:
                break  # EOF on stdout

            # --- parse ---------------------------------------------------
            raw = line.decode(errors="replace").strip()
            if not raw:
                continue

            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            evts, maybe_final = self._parser(obj, self._model_id)
            for e in evts:
                emit(e)
            if maybe_final is not None:
                final_text = maybe_final

        # --- natural EOF — wait for process exit then classify ------------
        returncode = await _reap(proc)

        if returncode == 0:
            return WorkerResult(
                outcome=WorkerOutcome.COMPLETED,
                final_text=final_text,
                returncode=0,
            )
        else:
            return WorkerResult(
                outcome=WorkerOutcome.FAILED,
                final_text=final_text,
                returncode=returncode,
            )
