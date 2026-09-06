import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.council import run_full_council
from backend.conversation_context import build_context_messages, format_context_prompt
from backend.providers.ollama_provider import OllamaProvider
from backend.providers.openrouter_provider import OpenRouterProvider
from backend.providers.factory import get_provider
from backend.rag import LocalRetriever, chunk_text, ingest_documents


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("request failed")

    def json(self):
        return self.payload


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    @patch("backend.providers.ollama_provider.httpx.AsyncClient")
    async def test_ollama_sends_local_options(self, client_type):
        client_type.return_value.__aenter__ = AsyncMock(
            return_value=client_type.return_value
        )
        client_type.return_value.__aexit__ = AsyncMock(return_value=None)
        client_type.return_value.post = AsyncMock(
            return_value=FakeResponse({"message": {"content": "local"}})
        )
        result = await OllamaProvider().query_model("phi:2.7b", [])
        payload = client_type.return_value.post.call_args.kwargs["json"]
        self.assertEqual(result["content"], "local")
        self.assertIn("options", payload)
        self.assertIn("keep_alive", payload)

    @patch("backend.providers.openrouter_provider.OPENROUTER_API_KEY", "test-key")
    @patch("backend.providers.openrouter_provider.httpx.AsyncClient")
    async def test_api_provider_normalizes_usage(self, client_type):
        client_type.return_value.__aenter__ = AsyncMock(
            return_value=client_type.return_value
        )
        client_type.return_value.__aexit__ = AsyncMock(return_value=None)
        client_type.return_value.post = AsyncMock(
            return_value=FakeResponse(
                {"choices": [{"message": {"content": "api"}}], "usage": {"total_tokens": 4}}
            )
        )
        result = await OpenRouterProvider().query_model("test/model", [])
        self.assertEqual(result["content"], "api")
        self.assertEqual(result["usage"]["total_tokens"], 4)

    @patch("backend.providers.ollama_provider.httpx.AsyncClient")
    async def test_ollama_timeout_is_graceful(self, client_type):
        client_type.return_value.__aenter__ = AsyncMock(
            return_value=client_type.return_value
        )
        client_type.return_value.__aexit__ = AsyncMock(return_value=None)
        client_type.return_value.post = AsyncMock(side_effect=asyncio.TimeoutError())
        self.assertIsNone(await OllamaProvider().query_model("missing", []))


class RagTests(unittest.TestCase):
    def test_chunking_validates_overlap(self):
        with self.assertRaises(ValueError):
            chunk_text("text", 10, 10)

    def test_ingestion_and_retrieval_include_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("Ollama runs local models.", encoding="utf-8")
            chunks = ingest_documents(directory, 100, 10)
            results = LocalRetriever(chunks).retrieve("local models", 1)
            self.assertEqual(results[0]["source"], str(path))

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            get_provider("not-a-provider")


class ConversationContextTests(unittest.TestCase):
    def test_empty_history_returns_current_query_unchanged(self):
        prompt, info = format_context_prompt("first question", [])
        self.assertEqual(prompt, "first question")
        self.assertEqual(info, {"messages": 0, "chars": 0})

    def test_only_final_answer_is_included(self):
        history = [
            {"role": "user", "content": "Earlier question"},
            {
                "role": "assistant",
                "stage1": [{"response": "private deliberation"}],
                "stage2": [{"critique": "private critique"}],
                "stage3": {"model": "chair", "response": "Public final answer"},
            },
        ]
        messages = build_context_messages(history)
        self.assertEqual(
            messages,
            [
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Public final answer"},
            ],
        )
        self.assertNotIn("private", str(messages))

    def test_recent_window_and_character_truncation(self):
        history = [
            {"role": "user", "content": "old"},
            {"role": "assistant", "stage3": {"response": "old answer"}},
            {"role": "user", "content": "new question"},
        ]
        messages = build_context_messages(history, max_messages=2, max_chars=20)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1]["content"], "new question")
        truncated = build_context_messages(history, max_messages=2, max_chars=8)
        self.assertEqual(truncated[-1]["content"], "question")

    def test_each_limit_can_be_disabled_independently(self):
        history = [{"role": "user", "content": "one"}, {"role": "user", "content": "two"}]
        self.assertEqual(len(build_context_messages(history, max_messages=0, max_chars=100)), 2)
        self.assertEqual(len(build_context_messages(history, max_messages=2, max_chars=0)), 2)

    def test_malformed_history_is_ignored(self):
        self.assertEqual(build_context_messages([None, {}, {"role": "assistant"}]), [])

    def test_non_streaming_and_streaming_can_share_same_context_builder(self):
        history = [
            {"role": "user", "content": "Remember this"},
            {"role": "assistant", "stage3": {"response": "A remembered answer"}},
        ]
        normal_query, normal_info = format_context_prompt("Follow up", history)
        stream_query, stream_info = format_context_prompt("Follow up", history)
        self.assertEqual(normal_query, stream_query)
        self.assertEqual(normal_info, stream_info)
        self.assertIn("Remember this", normal_query)
        self.assertIn("Follow up", normal_query)


class CouncilTests(unittest.IsolatedAsyncioTestCase):
    async def test_council_uses_provider_abstraction(self):
        class StubProvider:
            name = "stub"

            async def query_model(self, model, messages, timeout=None):
                return {"content": f"answer from {model}", "usage": {}, "latency_ms": 1}

            async def query_models_parallel(self, models, messages, timeout=None):
                return {
                    model: await self.query_model(model, messages, timeout)
                    for model in models
                }

        with patch("backend.council.provider", StubProvider()):
            stage1, stage2, stage3, metadata = await run_full_council(
                "Explain a test", developer_mode=True
            )
        self.assertTrue(stage1)
        self.assertTrue(stage2)
        self.assertTrue(stage3["response"])
        self.assertEqual(metadata["provider"], "stub")

    async def test_council_reports_provider_failure(self):
        class FailedProvider:
            name = "ollama"

            async def query_models_parallel(self, models, messages, timeout=None):
                return {model: None for model in models}

        with patch("backend.council.provider", FailedProvider()):
            _, _, result, metadata = await run_full_council(
                "Explain a test", developer_mode=False
            )
        self.assertIn("Ollama is unavailable", result["response"])
        self.assertEqual(metadata["errors"][0]["stage"], "stage1")

    async def test_rag_context_reaches_stage_one(self):
        class StubProvider:
            name = "stub"

            async def query_model(self, model, messages, timeout=None):
                return {"content": messages[0]["content"], "usage": {}, "latency_ms": 1}

            async def query_models_parallel(self, models, messages, timeout=None):
                return {
                    model: await self.query_model(model, messages, timeout)
                    for model in models
                }

        with patch("backend.council.provider", StubProvider()), patch(
            "backend.council.RAG_ENABLED", True
        ), patch(
            "backend.council.retrieve_context",
            return_value=("retrieved fact [Source 1]", [{"source": "guide.md"}]),
        ):
            stage1, _, _, metadata = await run_full_council("Question", True)
        self.assertIn("[Source 1]", stage1[0]["response"])
        self.assertEqual(metadata["rag"]["results"][0]["source"], "guide.md")


if __name__ == "__main__":
    unittest.main()
