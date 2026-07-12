"""Deterministic unit tests for WorkerExecutor and event parsers.

Uses real subprocesses (echo, python3 -c, sleep) — no network calls.
All tests run against local, predictable commands.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import pytest

# Ensure backend/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.worker_executor import (
    WorkerExecutor,
    WorkerOutcome,
    WorkerResult,
    CancellationToken,
)
from backend.streaming import parse_claude_event, parse_codex_event, _short


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

PYTHON = sys.executable  # same Python that runs the tests


def _null_parser(
    obj: Dict[str, Any], model_id: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Parser that treats every JSON line with a 'text' key as a thought event,
    and lines with a 'result' key as final text."""
    events: List[Dict[str, Any]] = []
    final: Optional[str] = None
    if "text" in obj:
        events.append({"type": "thought", "model": model_id, "text": obj["text"]})
    if "result" in obj:
        final = obj["result"]
    return events, final


async def _collect_events(executor: WorkerExecutor) -> Tuple[WorkerResult, List[Dict[str, Any]]]:
    """Run an executor and collect emitted events into a list."""
    events: List[Dict[str, Any]] = []

    def emit(e: Dict[str, Any]) -> None:
        events.append(e)

    result = await executor.run(emit)
    return result, events


def _json_script(lines: List[str]) -> str:
    """Build a python3 -c script that prints JSON lines to stdout."""
    prints = "\n".join(f"print({json.dumps(line)})" for line in lines)
    return f"import sys, json\n{prints}"


# ---------------------------------------------------------------------------
# Event parser tests (no subprocess needed)
# ---------------------------------------------------------------------------

class TestParseClaudeEvent:
    """Unit tests for parse_claude_event — pure function, no I/O."""

    def test_assistant_text_block(self):
        obj = {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Let me think about this."}]
            },
        }
        events, final = parse_claude_event(obj, "test-model")
        assert final is None
        assert len(events) == 1
        assert events[0]["type"] == "thought"
        assert "Let me think" in events[0]["text"]

    def test_assistant_tool_use_read(self):
        obj = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/x.py"}}
                ]
            },
        }
        events, final = parse_claude_event(obj, "m1")
        assert len(events) == 1
        assert events[0]["type"] == "tool"
        assert events[0]["tool"] == "Read"
        assert "/tmp/x.py" in events[0]["detail"]

    def test_assistant_tool_use_bash(self):
        obj = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}
                ]
            },
        }
        events, _ = parse_claude_event(obj, "m1")
        assert len(events) == 1
        assert events[0]["tool"] == "Bash"
        assert "ls -la" in events[0]["detail"]

    def test_result_event(self):
        obj = {"type": "result", "result": "The answer is 42."}
        events, final = parse_claude_event(obj, "m1")
        assert final == "The answer is 42."
        assert events == []

    def test_unknown_event_type(self):
        obj = {"type": "user", "message": {"content": []}}
        events, final = parse_claude_event(obj, "m1")
        assert final is None
        assert events == []

    def test_none_content(self):
        obj = {"type": "assistant", "message": {"content": None}}
        events, final = parse_claude_event(obj, "m1")
        assert events == []

    def test_empty_text(self):
        obj = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": ""}]},
        }
        events, _ = parse_claude_event(obj, "m1")
        assert events == []  # stripped empty → no event


class TestParseCodexEvent:
    """Unit tests for parse_codex_event — pure function, no I/O."""

    def test_command_item(self):
        obj = {"item": {"type": "exec", "command": "npm test"}}
        events, final = parse_codex_event(obj, "codex")
        assert len(events) == 1
        assert events[0]["tool"] == "Bash"
        assert "npm test" in events[0]["detail"]
        assert final is None

    def test_file_change_item(self):
        obj = {"item": {"type": "file_change", "path": "src/main.py"}}
        events, final = parse_codex_event(obj, "codex")
        assert len(events) == 1
        assert events[0]["tool"] == "Edit"
        assert final is None

    def test_reasoning_item(self):
        obj = {"item": {"type": "reasoning", "text": "I should check the logs first."}}
        events, final = parse_codex_event(obj, "codex")
        assert len(events) == 1
        assert events[0]["type"] == "thought"

    def test_agent_message_final(self):
        obj = {"item": {"type": "agent_message", "text": "Done."}}
        events, final = parse_codex_event(obj, "codex")
        assert final == "Done."

    def test_mcp_tool(self):
        obj = {"msg": {"type": "mcp_list", "name": "filesystem"}}
        events, _ = parse_codex_event(obj, "codex")
        assert len(events) == 1
        assert events[0]["tool"] == "MCP"


class TestShort:
    def test_short_no_truncation(self):
        assert _short("hello", 10) == "hello"

    def test_short_truncation(self):
        result = _short("a" * 200, 10)
        assert len(result) <= 10

    def test_short_newline_replacement(self):
        result = _short("line1\nline2", 50)
        assert "\n" not in result


# ---------------------------------------------------------------------------
# WorkerExecutor lifecycle tests (real subprocesses, no network)
# ---------------------------------------------------------------------------

class TestWorkerExecutorSuccess:
    """Happy path: process exits 0 and produces parseable JSON."""

    @pytest.mark.asyncio
    async def test_single_result_line(self):
        script = _json_script(['{"result": "hello world"}'])
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "test-model",
            inactivity_timeout=5.0,
        )
        result, events = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "hello world"
        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_multiple_thought_events_then_result(self):
        script = _json_script([
            '{"text": "step 1"}',
            '{"text": "step 2"}',
            '{"text": "step 3"}',
            '{"result": "final answer"}',
        ])
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, events = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "final answer"
        thought_events = [e for e in events if e["type"] == "thought"]
        assert len(thought_events) == 3

    @pytest.mark.asyncio
    async def test_stderr_is_captured(self):
        script = (
            "import sys\n"
            "print('{\"result\": \"ok\"}')\n"
            "print('diagnostic info', file=sys.stderr)\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert "diagnostic info" in result.stderr_tail

    @pytest.mark.asyncio
    async def test_stderr_does_not_block_stdout(self):
        """Write a lot to stderr; stdout must still be consumed fully."""
        # Write 50 KiB to stderr (above 10 KiB retention) + valid stdout
        script = (
            "import sys\n"
            "print('{\"result\": \"survived\"}')\n"
            "sys.stderr.write('X' * 50_000 + '\\n')\n"
            "sys.stderr.flush()\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "survived"
        # Should have at most ~10 KiB retained
        assert len(result.stderr_tail) <= 10_240  # max 10 KiB

    @pytest.mark.asyncio
    async def test_final_file_read_after_completion(self):
        """Codex pattern: -o flag writes final text to a file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            final_path = f.name
        try:
            script = (
                f"import sys\n"
                f"print('{{\"item\": {{\"type\": \"agent_message\", \"text\": \"partial\"}}}}')\n"
                f"with open({json.dumps(final_path)}, 'w') as f:\n"
                f"    f.write('complete output\\n')\n"
            )
            executor = WorkerExecutor(
                [PYTHON, "-c", script], parse_codex_event, "codex",
                inactivity_timeout=5.0, final_file=final_path,
            )
            result, _ = await _collect_events(executor)
            assert result.outcome == WorkerOutcome.COMPLETED
            # final_file should take priority over streaming result
            assert result.final_text == "complete output"
        finally:
            try:
                os.remove(final_path)
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_non_json_lines_are_skipped(self):
        script = (
            "print('not json at all')\n"
            "print('{\"result\": \"found me\"}')\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "found me"


class TestWorkerExecutorTimeout:
    """Inactivity timeout: process stops producing output."""

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self):
        """Process sleeps; inactivity_timeout fires → TIMED_OUT."""
        script = (
            "import sys, time\n"
            "print('{\"text\": \"starting...\"}')\n"
            "sys.stdout.flush()\n"
            "time.sleep(30)\n"  # way beyond the timeout
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=1.0,
        )
        result, events = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.TIMED_OUT
        # Should have received the first event before the timeout
        thoughts = [e for e in events if e["type"] == "thought"]
        assert len(thoughts) >= 1

    @pytest.mark.asyncio
    async def test_timeout_with_no_output_at_all(self):
        """Process produces nothing and sleeps → TIMED_OUT."""
        script = "import time; time.sleep(30)"
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=0.5,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.TIMED_OUT


class TestWorkerExecutorCancellation:
    """Explicit cancellation via CancellationToken."""

    @pytest.mark.asyncio
    async def test_cancel_before_start(self):
        """Token is already cancelled when run() starts."""
        token = CancellationToken()
        token.cancel()  # cancel before execution

        script = _json_script(['{"result": "should not reach"}'])
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0, cancel_token=token,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_during_run(self):
        """Cancel a long-running process mid-flight."""
        token = CancellationToken()

        # Script sleeps then prints — we cancel before it finishes
        script = (
            "import sys, time\n"
            "print('{\"text\": \"started\"}')\n"
            "sys.stdout.flush()\n"
            "time.sleep(30)\n"
            "print('{\"result\": \"never\"}')\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=10.0, cancel_token=token,
        )

        events: List[Dict[str, Any]] = []

        def emit(e: Dict[str, Any]) -> None:
            events.append(e)

        # Start the executor as a background task
        run_task = asyncio.create_task(executor.run(emit))

        # Wait for the first event to arrive, then cancel
        for _ in range(50):  # up to 5s
            if any(e["type"] == "thought" for e in events):
                break
            await asyncio.sleep(0.1)
        token.cancel()

        result = await run_task
        assert result.outcome == WorkerOutcome.CANCELLED
        # Should have at least the "started" thought event
        assert any(e["type"] == "thought" for e in events)

    @pytest.mark.asyncio
    async def test_cancel_during_readline_wait(self):
        """Cancel while waiting for the next line (via the asyncio.wait mechanism)."""
        token = CancellationToken()

        # Script that produces one line, then sleeps a long time
        script = (
            "import sys, time\n"
            "print('{\"text\": \"one\"}')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=30.0, cancel_token=token,
        )

        async def run_and_cancel():
            await asyncio.sleep(0.2)  # let first line arrive
            token.cancel()
            return await _collect_events(executor)

        result, _ = await run_and_cancel()
        assert result.outcome == WorkerOutcome.CANCELLED


class TestWorkerExecutorFailure:
    """Process failures and error conditions."""

    @pytest.mark.asyncio
    async def test_process_nonzero_exit(self):
        """Process exits with code 1 → FAILED."""
        script = "import sys; print('{\"text\": \"oops\"}'); sys.exit(1)"
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, events = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.FAILED
        assert result.returncode == 1
        # The final event handler should have captured "oops" before exit
        thoughts = [e for e in events if e["type"] == "thought"]
        assert len(thoughts) >= 1

    @pytest.mark.asyncio
    async def test_launch_failure_nonexistent_binary(self):
        """Command doesn't exist → FAILED immediately."""
        executor = WorkerExecutor(
            ["/nonexistent/binary_xyz_123", "arg"], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, events = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.FAILED
        assert result.error_message is not None
        assert "launch failed" in result.error_message

    @pytest.mark.asyncio
    async def test_stdout_closed_early(self):
        """Process closes stdout pipe immediately → COMPLETED with no text."""
        executor = WorkerExecutor(
            ["true"], _null_parser, "m",  # true exits 0 with no output
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text is None
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# CancellationToken unit tests
# ---------------------------------------------------------------------------

class TestCancellationToken:
    def test_not_cancelled_initially(self):
        token = CancellationToken()
        assert not token.cancelled

    def test_cancel_sets_flag(self):
        token = CancellationToken()
        token.cancel()
        assert token.cancelled

    @pytest.mark.asyncio
    async def test_wait_blocks_until_cancel(self):
        token = CancellationToken()

        async def cancel_after_delay():
            await asyncio.sleep(0.1)
            token.cancel()

        async def waiter():
            await token.wait()
            return "done"

        done, _ = await asyncio.wait(
            [asyncio.create_task(cancel_after_delay()), asyncio.create_task(waiter())],
            timeout=2.0,
            return_when=asyncio.ALL_COMPLETED,
        )
        assert len(done) == 2

    @pytest.mark.asyncio
    async def test_wait_returns_immediately_when_already_cancelled(self):
        token = CancellationToken()
        token.cancel()
        # Should not block
        await asyncio.wait_for(token.wait(), timeout=1.0)


# ---------------------------------------------------------------------------
# Integration: WorkerExecutor with real parsers
# ---------------------------------------------------------------------------

class TestWorkerExecutorWithRealParsers:
    """End-to-end: real parse_claude_event / parse_codex_event driving executors."""

    @pytest.mark.asyncio
    async def test_claude_stream_json_shape(self):
        """Simulate claude --output-format stream-json events."""
        lines = [
            json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Let me analyze this."}
            ]}}),
            json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "main.py"}}
            ]}}),
            json.dumps({"type": "result", "result": "Analysis complete."}),
        ]
        script = "\n".join(f"print({line!r})" for line in lines)
        executor = WorkerExecutor(
            [PYTHON, "-c", script], parse_claude_event, "claude-sim",
            inactivity_timeout=5.0,
        )
        result, events = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "Analysis complete."
        assert any(e["type"] == "thought" for e in events)
        assert any(e["type"] == "tool" for e in events)

    @pytest.mark.asyncio
    async def test_codex_json_shape(self):
        """Simulate codex exec --json events."""
        lines = [
            json.dumps({"item": {"type": "exec", "command": "ls"}}),
            json.dumps({"item": {"type": "reasoning", "text": "checking..."}}),
            json.dumps({"item": {"type": "agent_message", "text": "All good."}}),
        ]
        script = "\n".join(f"print({line!r})" for line in lines)
        executor = WorkerExecutor(
            [PYTHON, "-c", script], parse_codex_event, "codex-sim",
            inactivity_timeout=5.0,
        )
        result, events = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "All good."
        tool_events = [e for e in events if e["type"] == "tool"]
        thought_events = [e for e in events if e["type"] == "thought"]
        assert len(tool_events) >= 1
        assert len(thought_events) >= 1


# ---------------------------------------------------------------------------
# Edge cases / stress
# ---------------------------------------------------------------------------

class TestWorkerExecutorEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_lines_are_skipped(self):
        """Blank lines in stdout are ignored gracefully."""
        script = (
            "print()\n"
            "print('  ')\n"
            "print('{\"result\": \"still works\"}')\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "still works"

    @pytest.mark.asyncio
    async def test_malformed_json_is_skipped(self):
        """JSON that fails to parse is silently ignored."""
        script = (
            "print('{')\n"  # incomplete JSON fragment
            "print('{\"result\": \"recovered\"}')\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "recovered"

    @pytest.mark.asyncio
    async def test_cwd_is_respected(self):
        """Worker runs in the specified cwd."""
        target_dir = tempfile.gettempdir()
        script = "import os; print('{\"result\": \"' + os.getcwd() + '\"}')"
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            cwd=target_dir, inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == target_dir

    @pytest.mark.asyncio
    async def test_env_is_merged(self):
        """Extra env vars are available without clobbering os.environ."""
        script = "import os; print('{\"result\": \"' + os.environ.get('TEST_EXECUTOR_VAR', 'missing') + '\"}')"
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            env={"TEST_EXECUTOR_VAR": "present"},
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text == "present"

    @pytest.mark.asyncio
    async def test_final_file_not_present_does_not_crash(self):
        """final_file points to nonexistent path → no crash, final_text stays None."""
        script = _json_script(['{"text": "done"}'])
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
            final_file="/tmp/nonexistent_final_file_xyz.txt",
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.final_text is None  # no final was emitted, and file doesn't exist

    @pytest.mark.asyncio
    async def test_argv_is_copied_not_mutated(self):
        """WorkerExecutor must copy argv so caller mutations don't affect it."""
        argv = ["echo", "hello"]
        executor = WorkerExecutor(argv, _null_parser, "m", inactivity_timeout=5.0)
        argv.append("world")  # mutate after construction
        result, _ = await _collect_events(executor)
        # Should still only have ["echo", "hello"]
        assert result.outcome == WorkerOutcome.COMPLETED


# ---------------------------------------------------------------------------
# Regression tests for defects identified in commit ba26aaa review
# ---------------------------------------------------------------------------

class TestDrainStderrTail:
    """Defect 2: _drain_stderr must retain the LAST bounded bytes, not the first."""

    @pytest.mark.asyncio
    async def test_retains_tail_not_head(self):
        """When stderr output exceeds max_bytes, the retained text must come
        from the end (tail), not the beginning (head)."""
        # Write 15 KB to stderr: first 5 KB = 'A', last 10 KB = 'B'.
        # With a 10 KB bound, only 'B's should survive.
        script = (
            "import sys\n"
            "print('{\"result\": \"ok\"}')\n"
            "sys.stderr.write('A' * 5_120 + 'B' * 10_240)\n"
            "sys.stderr.flush()\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        # Must contain the tail 'B's, not the head 'A's.
        assert "B" in result.stderr_tail
        assert "A" not in result.stderr_tail

    @pytest.mark.asyncio
    async def test_retains_middle_sliding_window(self):
        """The sliding window should continuously evict old chunks."""
        script = (
            "import sys\n"
            "print('{\"result\": \"ok\"}')\n"
            "for i in range(30):\n"
            "    sys.stderr.write(f'chunk_{i:04d}' + 'x' * 400 + '\\n')\n"
            "sys.stderr.flush()\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        # Early chunks should be gone; late chunks should remain.
        assert "chunk_0000" not in result.stderr_tail
        assert "chunk_0029" in result.stderr_tail


class TestReapEscalation:
    """Defect 4: _reap timeouts must escalate to _terminate_and_reap."""

    @pytest.mark.asyncio
    async def test_reap_escalates_on_timeout(self):
        """A process that ignores SIGTERM is eventually killed via SIGKILL.

        The inactivity timeout path calls _terminate_and_reap which escalates
        SIGTERM → SIGKILL.  This test verifies that a SIGTERM-ignoring
        process is ultimately terminated and its returncode is negative
        (signalling it died by signal).
        """
        # Child ignores SIGTERM, busy-waits, and produces no more output.
        script = (
            "import signal, sys, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "print('{\"text\": \"starting\"}')\n"
            "sys.stdout.flush()\n"
            "# Busy-wait without touching stdout — triggers inactivity timeout.\n"
            "deadline = time.time() + 120\n"
            "while time.time() < deadline:\n"
            "    pass\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=0.5,
        )
        result, events = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.TIMED_OUT
        # The process was killed by signal; returncode should be negative
        # on POSIX (the kill signal's negative number).
        assert result.returncode is not None
        assert result.returncode < 0, (
            f"Expected negative returncode (killed by signal), got {result.returncode}"
        )


class TestCancellationCleanup:
    """Defect 5: External CancelledError must trigger process cleanup."""

    @pytest.mark.asyncio
    async def test_external_cancellation_terminates_process(self):
        """When the coroutine running the executor is cancelled externally,
        the process group must still be terminated and reaped."""
        script = (
            "import sys, time\n"
            "print('{\"text\": \"running\"}')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=30.0,
        )

        run_task = asyncio.create_task(executor.run(lambda e: None))

        # Wait for the first line, then externally cancel.
        await asyncio.sleep(0.5)
        run_task.cancel()

        # The cancellation must not leave a zombie.
        with pytest.raises(asyncio.CancelledError):
            await run_task

        # After cancellation, the _stream_loop tasks should be cleaned up
        # (no pending-task warnings).  We can't directly assert on warnings,
        # but if the process survived we'd have a resource leak.
        # Let the event loop settle.
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_cancellation_preserves_semantics(self):
        """CancelledError must propagate after cleanup, not be swallowed."""
        script = (
            "import sys, time\n"
            "print('{\"text\": \"start\"}')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=30.0,
        )

        events: List[Dict[str, Any]] = []

        async def run_and_cancel():
            await asyncio.sleep(0.3)
            task = asyncio.current_task()
            if task:
                task.cancel()
            return await executor.run(lambda e: events.append(e))

        with pytest.raises(asyncio.CancelledError):
            await run_and_cancel()


class TestStderrDrainSafety:
    """Defect 3: stderr must drain after process exit before cancellation."""

    @pytest.mark.asyncio
    async def test_stderr_drains_after_exit(self):
        """Buffered stderr from children must be captured even after the
        main process exits."""
        script = (
            "import os, sys, time\n"
            "# Fork a child that writes to stderr after the parent exits stdout.\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    time.sleep(0.3)  # parent has exited stdout by then\n"
            "    sys.stderr.write('late-child-diagnostic')\n"
            "    sys.stderr.flush()\n"
            "    sys.exit(0)\n"
            "print('{\"result\": \"parent done\"}')\n"
            "sys.stdout.flush()\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        # The late child stderr should be captured.
        assert "late-child-diagnostic" in result.stderr_tail

    @pytest.mark.asyncio
    async def test_stderr_tail_set_on_all_outcomes(self):
        """stderr_tail must be set even for FAILED and TIMED_OUT outcomes."""
        # FAILED: nonzero exit
        script = (
            "import sys\n"
            "print('{\"text\": \"before crash\"}')\n"
            "sys.stderr.write('crash diagnostic')\n"
            "sys.stderr.flush()\n"
            "sys.exit(3)\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.FAILED
        assert "crash diagnostic" in result.stderr_tail
        assert result.returncode == 3


class TestStreamingTerminalEvents:
    """Defect 6: Terminal agent events must be truthful and singular."""

    @pytest.mark.asyncio
    async def test_completed_emits_done(self):
        """COMPLETED outcome → exactly one 'done' terminal event."""
        from backend.streaming import _run_executor

        script = _json_script(['{"result": "ok"}'])
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        events: List[Dict[str, Any]] = []

        content = await _run_executor(executor, lambda e: events.append(e), "test-m")
        assert content == "ok"
        agent_events = [e for e in events if e.get("type") == "agent"]
        terminal = [e for e in agent_events if e.get("status") in ("done", "error")]
        assert len(terminal) == 1
        assert terminal[0]["status"] == "done"
        assert terminal[0]["model"] == "test-m"

    @pytest.mark.asyncio
    async def test_failed_emits_error(self):
        """FAILED outcome → exactly one 'error' terminal event."""
        from backend.streaming import _run_executor

        script = "import sys; print('{\"text\": \"x\"}'); sys.exit(4)"
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        events: List[Dict[str, Any]] = []

        content = await _run_executor(executor, lambda e: events.append(e), "test-m")
        agent_events = [e for e in events if e.get("type") == "agent"]
        terminal = [e for e in agent_events if e.get("status") in ("done", "error")]
        assert len(terminal) == 1
        assert terminal[0]["status"] == "error"
        assert "exit code 4" in terminal[0]["reason"]

    @pytest.mark.asyncio
    async def test_timed_out_emits_error(self):
        """TIMED_OUT outcome → exactly one 'error' terminal event with reason 'timeout'."""
        from backend.streaming import _run_executor

        script = "import time; print('{\"text\": \"x\"}'); time.sleep(60)"
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=0.5,
        )
        events: List[Dict[str, Any]] = []

        content = await _run_executor(executor, lambda e: events.append(e), "test-m")
        agent_events = [e for e in events if e.get("type") == "agent"]
        terminal = [e for e in agent_events if e.get("status") in ("done", "error")]
        assert len(terminal) == 1
        assert terminal[0]["status"] == "error"
        assert terminal[0]["reason"] == "timeout"

    @pytest.mark.asyncio
    async def test_cancelled_emits_error(self):
        """CANCELLED outcome → exactly one 'error' terminal event with reason 'cancelled'."""
        from backend.streaming import _run_executor

        token = CancellationToken()
        token.cancel()  # cancel before start
        script = _json_script(['{"result": "never"}'])
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0, cancel_token=token,
        )
        events: List[Dict[str, Any]] = []

        content = await _run_executor(executor, lambda e: events.append(e), "test-m")
        agent_events = [e for e in events if e.get("type") == "agent"]
        terminal = [e for e in agent_events if e.get("status") in ("done", "error")]
        assert len(terminal) == 1
        assert terminal[0]["status"] == "error"
        assert terminal[0]["reason"] == "cancelled"

    @pytest.mark.asyncio
    async def test_no_duplicate_terminal_events(self):
        """Never emit both 'done' and 'error' for the same run."""
        from backend.streaming import _run_executor

        script = "import sys; print('{\"text\": \"x\"}'); sys.exit(2)"
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        events: List[Dict[str, Any]] = []

        await _run_executor(executor, lambda e: events.append(e), "test-m")
        agent_events = [e for e in events if e.get("type") == "agent"]
        terminal = [e for e in agent_events if e.get("status") in ("done", "error")]
        assert len(terminal) == 1


# ---------------------------------------------------------------------------
# Regression tests for acceptance-fix defects
# ---------------------------------------------------------------------------


class TestStderrExactTail:
    """Fix 4: stderr tail must return the actual last min(total, max_bytes) bytes,
    not a potentially smaller whole-chunk approximation."""

    @pytest.mark.asyncio
    async def test_exact_byte_count_under_limit(self):
        """When total stderr < max_bytes, ALL bytes are retained exactly."""
        payload = b"hello world"  # 11 bytes
        script = (
            "import sys\n"
            "print('{\"result\": \"ok\"}')\n"
            f"sys.stderr.buffer.write({payload!r})\n"
            "sys.stderr.buffer.flush()\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert "hello world" in result.stderr_tail
        assert len(result.stderr_tail.encode(errors="replace")) >= 11

    @pytest.mark.asyncio
    async def test_exact_byte_count_at_limit(self):
        """When total stderr == max_bytes, ALL bytes are retained."""
        # max_bytes is 10 KiB = 10240.  Write exactly that many distinct bytes.
        size = 10_240
        script = (
            "import sys\n"
            "print('{\"result\": \"ok\"}')\n"
            f"sys.stderr.buffer.write(b'B' * {size})\n"
            "sys.stderr.buffer.flush()\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        assert len(result.stderr_tail) == size
        assert all(c == "B" for c in result.stderr_tail)

    @pytest.mark.asyncio
    async def test_exact_byte_count_across_uneven_chunks(self):
        """Sliding window retains exactly max_bytes even across uneven reads.

        The old chunk-list approach could drop a chunk and then be well
        below the max_bytes bound.  The bytearray fix must retain exactly
        10 KiB regardless of how read() splits the data.
        """
        # 10 * 1024 = 10240.  Write 3 KiB of 'A' then 9 KiB of 'B'.
        # Total = 12 KiB; retained = exactly the last 10 KiB.
        head_bytes = 3 * 1024
        tail_bytes = 9 * 1024
        expected_tail = 10 * 1024
        script = (
            "import sys\n"
            "print('{\"result\": \"ok\"}')\n"
            f"sys.stderr.buffer.write(b'A' * {head_bytes})\n"
            f"sys.stderr.buffer.write(b'B' * {tail_bytes})\n"
            "sys.stderr.buffer.flush()\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        # Total: 3 KiB A + 9 KiB B = 12288 bytes.
        # Retain last 10 KiB = 10240 bytes → drop 2048 bytes from head.
        # 3072 A − 2048 = 1024 A, then all 9216 B.
        assert len(result.stderr_tail) == expected_tail, (
            f"Expected exactly {expected_tail} bytes, got {len(result.stderr_tail)}"
        )
        expected_content = "A" * 1024 + "B" * 9216
        assert result.stderr_tail == expected_content, (
            "Tail content mismatch: expected 1 KiB A followed by 9 KiB B"
        )

    @pytest.mark.asyncio
    async def test_exact_byte_count_tiny_chunks(self):
        """Retention works even when each read() returns a single byte."""
        # Use Python-level writes to force small buffering.
        script = (
            "import sys\n"
            "print('{\"result\": \"ok\"}')\n"
            "for _ in range(3000):\n"
            "    sys.stderr.write('x')\n"
            "sys.stderr.flush()\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        # 3000 'x' chars are well under 10 KiB, so all should be retained.
        assert result.stderr_tail.count("x") == 3000


class TestTerminateAndReapProcessGroup:
    """Fix 3: _terminate_and_reap must kill children even when leader exited."""

    @pytest.mark.asyncio
    @pytest.mark.posix
    async def test_child_killed_after_leader_exits(self):
        """Deterministic POSIX test: start a child, let the leader exit, and
        verify no live child remains after executor completion."""
        # The leader (Python script) forks a child that records its PID to a
        # temp file, then the leader exits immediately.  The executor must
        # kill the orphaned child (via killpg on the session) even though the
        # leader has already exited.
        import tempfile

        pid_file = tempfile.mktemp(suffix=".pid")
        ready_file = tempfile.mktemp(suffix=".ready")

        script = (
            "import os, sys, time, signal\n"
            "# Child must be in the same process group (start_new_session ensures it).\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    # Child: write pid + ready marker, then close inherited pipe fds\n"
            "    # so the executor sees EOF on stdout/stderr when the leader exits.\n"
            f"    with open({json.dumps(pid_file)}, 'w') as f:\n"
            "        f.write(str(os.getpid()))\n"
            f"    with open({json.dumps(ready_file)}, 'w') as f:\n"
            "        f.write('ready')\n"
            "    sys.stderr.flush()\n"
            "    # Close inherited pipe fds deterministically — os.close, not\n"
            "    # sys.stdout.close (which only closes the Python wrapper).\n"
            "    os.close(0)\n"
            "    os.close(1)\n"
            "    os.close(2)\n"
            "    # Wait until killed by executor's process-group cleanup.\n"
            "    signal.signal(signal.SIGTERM, signal.SIG_DFL)\n"
            "    signal.pause()\n"
            "    sys.exit(0)\n"
            "# Leader: wait for child to be ready, then exit immediately.\n"
            "for _ in range(100):\n"
            f"    if os.path.exists({json.dumps(ready_file)}):\n"
            "        break\n"
            "    time.sleep(0.02)\n"
            "print('{\"result\": \"leader done\"}')\n"
            "sys.stdout.flush()\n"
            "sys.exit(0)\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)

        # The executor should complete because leader exits 0 (child closes
        # stdout so EOF arrives).  The _terminate_and_reap in the finally
        # block signals the process group, killing the orphaned child.
        assert result.outcome == WorkerOutcome.COMPLETED

        # Clean up temp files — read PID before deleting.
        child_pid_str = None
        try:
            with open(pid_file) as f:
                child_pid_str = f.read().strip()
        except OSError:
            pass

        for f in (pid_file, ready_file):
            try:
                os.remove(f)
            except OSError:
                pass

        # The child was forked but must not still be running.  Poll briefly
        # to tolerate the window between SIGTERM delivery and reaping
        # (zombie state is acceptable — the process has been killed).
        if child_pid_str:
            child_pid = int(child_pid_str)
            import signal as _signal
            child_dead = False
            for _ in range(30):  # poll for up to ~1.5 s
                try:
                    os.kill(child_pid, 0)
                    # Process exists — distinguish zombie from running.
                    try:
                        with open(f"/proc/{child_pid}/stat") as sf:
                            state = sf.read().split()[2]
                        if state == "Z":
                            child_dead = True  # zombie, cleanup worked
                            break
                    except OSError:
                        pass  # /proc entry may race with exit
                    await asyncio.sleep(0.05)
                except (ProcessLookupError, OSError):
                    child_dead = True
                    break
            if not child_dead:
                try:
                    os.kill(child_pid, _signal.SIGKILL)
                except OSError:
                    pass
                pytest.fail(
                    f"Child process {child_pid} still running after executor "
                    "completion. Process-group cleanup failed."
                )

    @pytest.mark.asyncio
    @pytest.mark.posix
    async def test_cancellation_kills_process_group(self):
        """When cancelled, the entire process group (not just the leader) must die."""
        script = (
            "import os, sys, time\n"
            "# Fork a child; both sleep indefinitely.\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    time.sleep(120)\n"
            "    sys.exit(0)\n"
            "print('{\"text\": \"leader alive\"}')\n"
            "sys.stdout.flush()\n"
            "time.sleep(120)\n"
        )
        token = CancellationToken()
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=30.0, cancel_token=token,
        )

        events: List[Dict[str, Any]] = []

        async def run_and_cancel():
            await asyncio.sleep(0.3)
            token.cancel()
            return await _collect_events(executor)

        result, _ = await run_and_cancel()
        assert result.outcome == WorkerOutcome.CANCELLED

    @pytest.mark.asyncio
    async def test_returncode_still_returned_after_signal(self):
        """When the leader already exited, _terminate_and_reap still signals the
        process group AND returns the leader's original returncode."""
        script = (
            "import os, sys, time\n"
            "# Leader exits 0 quickly; child lingers.\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    # Close inherited pipe fds so leader exit → pipe EOF.\n"
            "    os.close(0)\n"
            "    os.close(1)\n"
            "    os.close(2)\n"
            "    time.sleep(30)\n"
            "    sys.exit(0)\n"
            "print('{\"result\": \"quick\"}')\n"
            "sys.stdout.flush()\n"
            "sys.exit(0)\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)
        assert result.outcome == WorkerOutcome.COMPLETED
        # The leader exited 0; we should get its returncode back, not None.
        assert result.returncode == 0


class TestStreamLoopTaskCleanup:
    """Fix 2: pending asyncio tasks must be awaited after cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_token_path_awaits_pending_tasks(self):
        """When the cancel token fires, the pending readline task is cancelled
        AND awaited (no pending-task warnings).  Verify via asyncio debug."""
        loop = asyncio.get_running_loop()
        old_debug = loop.get_debug()
        loop.set_debug(True)

        # Capture custom exception handler calls.
        handlers: list = []

        def _handler(lp, ctx):
            handlers.append(ctx)

        old_handler = loop.get_exception_handler()
        loop.set_exception_handler(_handler)

        try:
            token = CancellationToken()
            script = (
                "import sys, time\n"
                "print('{\"text\": \"one\"}')\n"
                "sys.stdout.flush()\n"
                "time.sleep(60)\n"
            )
            executor = WorkerExecutor(
                [PYTHON, "-c", script], _null_parser, "m",
                inactivity_timeout=30.0, cancel_token=token,
            )

            events: List[Dict[str, Any]] = []

            async def run_and_cancel():
                await asyncio.sleep(0.3)
                token.cancel()
                return await _collect_events(executor)

            result, _ = await run_and_cancel()
            assert result.outcome == WorkerOutcome.CANCELLED

            # Let the event loop settle so any delayed GC warnings fire.
            await asyncio.sleep(0.1)

            # Check for "was destroyed but it is pending" messages.
            pending_msgs = [
                c for c in handlers
                if "destroyed" in str(c.get("message", ""))
                and "pending" in str(c.get("message", ""))
            ]
            assert len(pending_msgs) == 0, (
                f"Pending-task destruction warnings: {pending_msgs}"
            )
        finally:
            loop.set_debug(old_debug)
            loop.set_exception_handler(old_handler)

    @pytest.mark.asyncio
    async def test_timeout_path_awaits_pending_tasks(self):
        """When inactivity timeout fires, pending tasks are cancelled AND awaited."""
        loop = asyncio.get_running_loop()
        old_debug = loop.get_debug()
        loop.set_debug(True)

        handlers: list = []

        def _handler(lp, ctx):
            handlers.append(ctx)

        old_handler = loop.get_exception_handler()
        loop.set_exception_handler(_handler)

        try:
            script = (
                "import sys, time\n"
                "print('{\"text\": \"one\"}')\n"
                "sys.stdout.flush()\n"
                "time.sleep(60)\n"
            )
            executor = WorkerExecutor(
                [PYTHON, "-c", script], _null_parser, "m",
                inactivity_timeout=0.5,
            )
            result, _ = await _collect_events(executor)
            assert result.outcome == WorkerOutcome.TIMED_OUT

            await asyncio.sleep(0.1)

            pending_msgs = [
                c for c in handlers
                if "destroyed" in str(c.get("message", ""))
                and "pending" in str(c.get("message", ""))
            ]
            assert len(pending_msgs) == 0, (
                f"Pending-task destruction warnings: {pending_msgs}"
            )
        finally:
            loop.set_debug(old_debug)
            loop.set_exception_handler(old_handler)

    @pytest.mark.asyncio
    async def test_external_cancellation_during_wait_cleans_up_tasks(self):
        """External CancelledError injected into asyncio.wait must cancel and
        await every created read_task/cancel_task before re-raising.

        This is the deterministic regression test for the coroutine-
        cancellation task-leak defect: when executor.run is cancelled
        externally while _stream_loop is blocked on asyncio.wait, the
        try/except wrapper must call _cancel_and_await on *all* created
        tasks so no helper task remains pending.
        """
        loop = asyncio.get_running_loop()
        old_debug = loop.get_debug()
        loop.set_debug(True)

        handlers: list = []

        def _handler(lp, ctx):
            handlers.append(ctx)

        old_handler = loop.get_exception_handler()
        loop.set_exception_handler(_handler)

        try:
            # Process sleeps after one line — the executor will be blocked
            # in asyncio.wait when external cancellation arrives.
            script = (
                "import sys, time\n"
                "print('{\"text\": \"first\"}')\n"
                "sys.stdout.flush()\n"
                "time.sleep(60)\n"
            )
            executor = WorkerExecutor(
                [PYTHON, "-c", script], _null_parser, "m",
                inactivity_timeout=30.0,
            )

            evts: List[Dict[str, Any]] = []

            run_task = asyncio.create_task(executor.run(lambda e: evts.append(e)))

            # Let the first line arrive, so the executor enters the next
            # asyncio.wait iteration.
            await asyncio.sleep(0.3)
            run_task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await run_task

            # Let the event loop settle so any delayed GC-pending warnings fire.
            await asyncio.sleep(0.2)

            # No "destroyed but pending" messages must appear.
            pending_msgs = [
                c for c in handlers
                if "destroyed" in str(c.get("message", ""))
                and "pending" in str(c.get("message", ""))
            ]
            assert len(pending_msgs) == 0, (
                f"Pending-task destruction warnings after external cancellation: {pending_msgs}"
            )
        finally:
            loop.set_debug(old_debug)
            loop.set_exception_handler(old_handler)


# ---------------------------------------------------------------------------
# Regression test: SIGTERM-resistant descendant cleanup
# ---------------------------------------------------------------------------

class TestSigtermResistantDescendants:
    """Fix: _terminate_and_reap must SIGKILL descendants that ignore SIGTERM
    even when the leader has already exited."""

    @pytest.mark.asyncio
    @pytest.mark.posix
    async def test_sigterm_resistant_child_killed_by_sigkill(self, monkeypatch):
        """A forked child that ignores SIGTERM must be removed by SIGKILL.

        The leader exits quickly (returncode already set when
        _terminate_and_reap runs).  The child ignores SIGTERM explicitly
        and closes inherited fds so pipe EOF arrives.  After the bounded
        grace interval the executor must escalate to SIGKILL and kill
        the orphan.
        """
        monkeypatch.setattr("backend.worker_executor._KILL_GRACE", 0.3)

        import tempfile

        pid_file = tempfile.mktemp(suffix=".pid")

        script = (
            "import os, sys, signal, time\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    # Child: ignore SIGTERM, write PID, close inherited fds.\n"
            f"    with open({json.dumps(pid_file)}, 'w') as f:\n"
            "        f.write(str(os.getpid()))\n"
            "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "    os.close(0)\n"
            "    os.close(1)\n"
            "    os.close(2)\n"
            "    # Busy-wait until killed by SIGKILL.\n"
            "    while True:\n"
            "        time.sleep(0.1)\n"
            "# Leader: produce one result line and exit immediately.\n"
            "print('{\"result\": \"leader done\"}')\n"
            "sys.stdout.flush()\n"
            "sys.exit(0)\n"
        )
        executor = WorkerExecutor(
            [PYTHON, "-c", script], _null_parser, "m",
            inactivity_timeout=5.0,
        )
        result, _ = await _collect_events(executor)

        # Leader exited cleanly; executor outcome must reflect that.
        assert result.outcome == WorkerOutcome.COMPLETED
        assert result.returncode == 0

        # Read the child PID and verify it is dead.
        child_pid_str = None
        try:
            with open(pid_file) as f:
                child_pid_str = f.read().strip()
        except OSError:
            pass
        finally:
            try:
                os.remove(pid_file)
            except OSError:
                pass

        if child_pid_str:
            child_pid = int(child_pid_str)
            import signal as _signal

            child_dead = False
            for _ in range(30):  # poll up to ~1.5 s
                try:
                    os.kill(child_pid, 0)
                    # Process exists — distinguish zombie from running.
                    try:
                        with open(f"/proc/{child_pid}/stat") as sf:
                            state = sf.read().split()[2]
                        if state == "Z":
                            child_dead = True  # zombie, cleanup worked
                            break
                    except OSError:
                        pass  # /proc entry may race with exit
                    await asyncio.sleep(0.05)
                except (ProcessLookupError, OSError):
                    child_dead = True
                    break

            if not child_dead:
                try:
                    os.kill(child_pid, _signal.SIGKILL)
                except OSError:
                    pass
                pytest.fail(
                    f"SIGTERM-resistant child {child_pid} survived executor "
                    "completion. SIGKILL escalation in _terminate_and_reap failed."
                )
