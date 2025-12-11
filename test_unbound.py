"""Test script for Unbound API integration."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Council models to test
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4-5",
    "x-ai/grok-4",
]

async def test_model(model: str):
    """Test a single model via Unbound API."""
    import httpx

    api_key = os.getenv("UNBOUND_API_KEY")
    api_url = "https://api.getunbound.ai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say 'Hello!' and identify yourself in one short sentence."}],
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            content = data['choices'][0]['message']['content']
            return True, content[:100] + "..." if len(content) > 100 else content

    except Exception as e:
        return False, str(e)

async def test_all_models():
    """Test all council models."""
    print(f"API Provider: {os.getenv('API_PROVIDER', 'openrouter')}")
    print(f"Testing {len(COUNCIL_MODELS)} council models via Unbound API...")
    print("=" * 60)

    for model in COUNCIL_MODELS:
        print(f"\n{model}:")
        success, result = await test_model(model)
        if success:
            print(f"  ✓ {result}")
        else:
            print(f"  ✗ Error: {result}")

    print("\n" + "=" * 60)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(test_all_models())
