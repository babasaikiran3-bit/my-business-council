"""End-to-end check of the chained council tools over a real stdio session.

Run: uv run --system-certs python test_council_chain.py
Makes ~9 real model calls. Also exercises the two error paths, which cost nothing.
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).parent
Q = "In one sentence: what is an offset account?"


def unwrap(res):
    d = res.structured_content
    return d["result"] if d and set(d.keys()) == {"result"} else d


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "backend.mcp_server"], cwd=str(REPO)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = [t.name for t in (await session.list_tools()).tools]
            for n in ("council_open", "council_rank", "council_close"):
                assert n in names, f"{n} missing from {names}"
            print("ok  tools:", names)

            # --- error path 1: unknown id (no model calls) ---
            res = await session.call_tool("council_rank", {"council_id": "nope1234"})
            assert res.is_error, "unknown council_id must error"
            assert "council_open" in str(res.content), "error must name the recovery step"
            print("ok  unknown council_id errors with recovery step")

            # --- stage 1 ---
            s1 = unwrap(await session.call_tool("council_open", {"question": Q}))
            cid = s1["council_id"]
            assert s1["responses"], "no responses"
            assert "council_rank" in s1["next_step"]
            print(f"ok  council_open -> {cid}, {s1['models_responded']} responded")

            # --- error path 2: close before rank (no model calls) ---
            early = unwrap(await session.call_tool("council_close", {"council_id": cid}))
            assert "error" in early, "close before rank must be refused"
            assert "council_rank" in early["error"]
            print("ok  council_close before council_rank refused with recovery step")

            # --- stage 2 ---
            s2 = unwrap(await session.call_tool("council_rank", {"council_id": cid}))
            assert s2["council_id"] == cid, "council_id must round-trip"
            assert s2["ranking"], "no ranking"
            print(f"ok  council_rank -> {s2['consensus']['verdict']}, {len(s2['ranking'])} ranked")

            # --- stage 3 ---
            s3 = unwrap(await session.call_tool("council_close", {"council_id": cid}))
            assert s3["answer"].strip(), "empty synthesis"
            print(f"ok  council_close -> {s3['chairman']}")
            print("    ", s3["answer"][:120].replace("\n", " "), "...")

    print("\nPASSED")


if __name__ == "__main__":
    asyncio.run(main())
