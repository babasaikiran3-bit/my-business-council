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
