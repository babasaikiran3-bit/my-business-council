"""Self-check for provider routing.

Run: uv run python test_providers.py
Exercises request building and response parsing for every provider branch
without touching the network. No real keys needed.
"""

import os

# Set before importing so build_request finds them. setdefault so a real
# .env-loaded value is never clobbered.
for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY"):
    os.environ.setdefault(var, f"test-{var.lower()}")

from backend.providers import (  # noqa: E402
    ProviderError,
    build_request,
    parse_response,
    split_model_id,
)

MSGS = [{"role": "user", "content": "hi"}]


def test_splits_provider_and_model():
    assert split_model_id("anthropic/claude-opus-5") == ("anthropic", "claude-opus-5")
    # Model names containing a slash keep everything after the first one.
    assert split_model_id("google/gemini-3-pro-preview")[1] == "gemini-3-pro-preview"


def test_rejects_bad_model_ids():
    for bad in ("gpt-5.1", "openai/", "nosuchprovider/x"):
        try:
            split_model_id(bad)
        except ProviderError:
            continue
        raise AssertionError(f"expected ProviderError for {bad!r}")


def test_anthropic_uses_native_auth_and_requires_max_tokens():
    url, headers, payload = build_request("anthropic/claude-opus-5", MSGS)
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "test-anthropic_api_key"
    assert "Authorization" not in headers, "Anthropic must not use Bearer auth"
    assert headers["anthropic-version"]
    assert payload["max_tokens"] > 0, "Anthropic rejects requests without max_tokens"
    assert payload["model"] == "claude-opus-5", "provider prefix must be stripped"


def test_openai_compatible_providers_use_bearer():
    for model_id, expected_host in (
        ("openai/gpt-5.1", "api.openai.com"),
        ("x-ai/grok-4", "api.x.ai"),
        ("google/gemini-3-pro-preview", "generativelanguage.googleapis.com"),
    ):
        url, headers, payload = build_request(model_id, MSGS)
        assert expected_host in url, f"{model_id} -> {url}"
        assert headers["Authorization"].startswith("Bearer ")
        assert "x-api-key" not in headers
        assert "/" not in payload["model"], "provider prefix must be stripped"


def test_missing_key_is_a_clear_error():
    saved = os.environ.pop("XAI_API_KEY")
    try:
        build_request("x-ai/grok-4", MSGS)
    except ProviderError as e:
        assert "XAI_API_KEY" in str(e), f"error must name the missing var: {e}"
    else:
        raise AssertionError("expected ProviderError when key is unset")
    finally:
        os.environ["XAI_API_KEY"] = saved


def test_parses_anthropic_content_blocks():
    data = {
        "content": [
            {"type": "thinking", "thinking": "ignore me"},
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "world"},
        ]
    }
    assert parse_response("anthropic", data)["content"] == "Hello world"


def test_parses_openai_choices():
    data = {"choices": [{"message": {"content": "Hello world"}}]}
    result = parse_response("openai", data)
    assert result["content"] == "Hello world"
    assert result["reasoning_details"] is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
