"""Manual smoke test for the Stage 0 web-search researcher.

Run from the repo root:

    uv run python test_openrouter.py

It calls query_model with web_search enabled and search_domains restricted to
TRUSTED_DOMAINS on the SEARCH_MODEL for a sample pediatric question, then prints
the returned content, the raw annotations, and the extract_citations() output so
a developer can confirm real trusted-domain URLs come back from the live API.
"""

import asyncio
import json

from backend.config import OPENROUTER_API_KEY, SEARCH_MODEL, TRUSTED_DOMAINS, SEARCH_SYSTEM_PROMPT
from backend.openrouter import query_model, extract_citations


SAMPLE_QUESTION = (
    "My 2-month-old has a fever of 38.5C. What does the official guidance say "
    "about fever in young infants?"
)


async def main() -> None:
    """Query the Stage 0 researcher and print content, annotations, citations."""
    if not OPENROUTER_API_KEY:
        print("OPENROUTER_API_KEY is not set. Add it to your .env and retry.")
        return

    messages = [
        {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": SAMPLE_QUESTION},
    ]

    print(f"Querying {SEARCH_MODEL} with web search restricted to TRUSTED_DOMAINS...\n")
    resp = await query_model(
        SEARCH_MODEL,
        messages,
        web_search=True,
        search_domains=TRUSTED_DOMAINS,
    )

    if resp is None:
        print("Request failed (returned None). Check the error logged above.")
        return

    print("=== CONTENT ===")
    print(resp.get("content"))

    print("\n=== RAW ANNOTATIONS ===")
    print(json.dumps(resp.get("annotations"), indent=2))

    print("\n=== extract_citations() ===")
    citations = extract_citations(resp.get("annotations"))
    print(json.dumps(citations, indent=2))

    print(f"\n{len(citations)} unique citation(s) returned.")


if __name__ == "__main__":
    asyncio.run(main())
