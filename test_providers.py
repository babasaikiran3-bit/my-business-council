"""Test script for provider abstraction system."""

import asyncio
from backend.providers import ProviderFactory


async def test_provider_parsing():
    """Test model identifier parsing."""
    print("\n=== Testing Model Identifier Parsing ===")

    factory = ProviderFactory(default_provider="openrouter")

    test_cases = [
        ("ollama:llama2", ("ollama", "llama2")),
        ("openrouter:gpt-4", ("openrouter", "gpt-4")),
        ("lmstudio:mistral", ("lmstudio", "mistral")),
        ("gpt-4", ("openrouter", "gpt-4")),  # Uses default
        ("openai/gpt-4o", ("openrouter", "openai/gpt-4o")),  # OpenRouter format
    ]

    for model_id, expected in test_cases:
        result = factory.parse_model_identifier(model_id)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{model_id}' → {result} (expected: {expected})")


async def test_provider_validation():
    """Test provider validation."""
    print("\n=== Testing Provider Validation ===")

    # Test with no configuration
    factory = ProviderFactory()
    validation = factory.validate_all()

    print("Provider validation status:")
    for provider, is_valid in validation.items():
        status = "✓ Valid" if is_valid else "✗ Invalid"
        print(f"  {provider}: {status}")

    available = factory.get_available_providers()
    print(f"\nAvailable providers: {available}")


async def test_provider_routing():
    """Test provider routing without actual API calls."""
    print("\n=== Testing Provider Routing ===")

    factory = ProviderFactory(default_provider="openrouter")

    test_models = [
        "ollama:llama2",
        "openrouter:gpt-4",
        "lmstudio:mistral",
    ]

    for model_id in test_models:
        provider_name, model_name = factory.parse_model_identifier(model_id)
        provider = factory.get_provider(provider_name)

        if provider:
            print(f"✓ '{model_id}' → {provider.name} provider (model: {model_name})")
        else:
            print(f"✗ '{model_id}' → No provider found for '{provider_name}'")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("LLM Council - Provider System Tests")
    print("=" * 60)

    await test_provider_parsing()
    await test_provider_validation()
    await test_provider_routing()

    print("\n" + "=" * 60)
    print("Tests Complete!")
    print("=" * 60)
    print("\nNote: These tests verify the provider abstraction layer.")
    print("For actual API testing:")
    print("  - OpenRouter: Requires OPENROUTER_API_KEY in .env")
    print("  - Ollama: Requires 'ollama serve' running on localhost:11434")
    print("  - LMStudio: Requires LMStudio server running on localhost:1234")
    print()


if __name__ == "__main__":
    asyncio.run(main())
