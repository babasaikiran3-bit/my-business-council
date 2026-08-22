"""End-to-end check of the MCP server over a real stdio session.

Run: uv run --system-certs python test_mcp_server.py

Spawns backend.mcp_server as a subprocess exactly as Claude Desktop would,
then does a full round trip. Makes ~9 real model calls and takes 45s+.
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).parent
progress_seen: list[str] = []


async def on_progress(progress: float, total: float | None, message: str | None) -> None:
    progress_seen.append(message or "")
    print(f"  progress {progress:.0f}/{total:.0f} - {message}")


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.mcp_server"],
        cwd=str(REPO),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("ok  session initialised")

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            assert "ask_council" in names, f"ask_council missing, got {names}"
            tool = next(t for t in tools.tools if t.name == "ask_council")
            assert tool.input_schema["required"] == ["question"], tool.input_schema["required"]
            print(f"ok  tool listed: {names}")

            print("--- calling ask_council (this makes ~9 real model calls) ---")
            res = await session.call_tool(
                "ask_council",
                {"question": "In one sentence: is an offset account or extra repayments better?"},
                progress_callback=on_progress,
            )

            assert not res.is_error, f"tool errored: {res.content}"
            data = res.structured_content
            assert data is not None, "no structured_content returned"
            # The SDK wraps a plain-dict return under "result".
            if set(data.keys()) == {"result"}:
                data = data["result"]

            for key in ("answer", "consensus", "ranking", "models_responded", "chairman"):
                assert key in data, f"missing key {key!r} in {list(data)}"
            assert "responses" not in data, "summary detail must not include raw responses"
            assert data["answer"].strip(), "chairman returned an empty answer"

            print("ok  result keys:", list(data))
            print("ok  models_responded:", data["models_responded"])
            print("ok  consensus:", data["consensus"]["verdict"], "-", data["consensus"]["note"])
            print("ok  ranking:")
            for r in data["ranking"]:
                print(f"      {r['model']:32} avg {r['average_rank']}  ({r['rankings_count']} votes)")
            print("ok  answer:", data["answer"][:160].replace("\n", " "), "...")

    assert progress_seen, "no progress notifications received - slow clients will time out"
    print(f"\nok  {len(progress_seen)} progress notifications received")
    print("\nPASSED")


if __name__ == "__main__":
    asyncio.run(main())
