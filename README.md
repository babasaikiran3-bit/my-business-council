# LLM Council

![llmcouncil](header.jpg)

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT 5.1, Google Gemini 3.0 Pro, Anthropic Claude Sonnet 4.5, xAI Grok 4, eg.c), you can group them into your "LLM Council". This repo is a simple, local web app that essentially looks like ChatGPT except it uses a provider abstraction (OpenRouter and Ollama are supported today) to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Chairman LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Structured critique**. Each model receives anonymized responses and returns structured peer critiques: strengths, weaknesses, missing information, unsupported claims, and suggested improvements.
3. **Stage 3: Final response**. The synthesizer model receives only anonymous responses and structured critiques (no model names) and returns a direct user answer.

For trivial prompts (for example greetings), the critique stage is skipped and the app returns a direct response for speed.

## Vibe Code Alert

This project was 99% vibe coded as a fun Saturday hack because I wanted to explore and evaluate a number of LLMs side by side in the process of [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438). It's nice and useful to see multiple responses side by side, and also the cross-opinions of all LLMs on each other's outputs. I'm not going to support it in any way, it's provided here as is for other people's inspiration and I don't intend to improve it. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Configure Provider

Create a `.env` file in the project root:

```bash
PROVIDER=api
OPENROUTER_API_KEY=sk-or-v1-...
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

For local Ollama:

```bash
PROVIDER=ollama
OLLAMA_API_URL=http://localhost:11434/api/chat
```

Switch backends by changing only `PROVIDER`: use `api` for OpenRouter and
`ollama` for local models. Copy [.env.example](D:/Builds/llm-council/.env.example)
to `.env`. On Windows, start the Ollama app and verify installed tags with
`ollama list`; model names must match exactly, including `:latest`.

### 3. Configure Models (Optional)

Set `API_COUNCIL_MODELS`, `API_CHAIRMAN_MODEL`, or their `OLLAMA_*` equivalents
in `.env` to customize the council:

```python
API_COUNCIL_MODELS=[
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

API_CHAIRMAN_MODEL=google/gemini-3-pro-preview
```

For Ollama, you can run multiple local models as independent council members:

```python
OLLAMA_COUNCIL_MODELS=llama3.2:3b,qwen3.5:2b,phi4-mini:latest
OLLAMA_CHAIRMAN_MODEL=phi4-mini:latest
```

Optional:

```bash
# Override title generation model for any provider
TITLE_MODEL=your-model-name
```

### Local RAG

Set `RAG_ENABLED=true` and place `.txt`, `.md`, or `.markdown` files in
`RAG_DOCUMENTS_DIR` (default `data/documents`). The built-in retriever uses
local deterministic lexical embeddings and returns source labels in council
context. Tune `RAG_TOP_K`, `RAG_CHUNK_SIZE`, and `RAG_CHUNK_OVERLAP`; no vector
database or external service is required.

### Conversation memory

Each request can include a bounded window of recent public user messages and
assistant final answers from the same conversation. Internal Stage 1/Stage 2
developer-mode data is never included. Configure `CONTEXT_MAX_MESSAGES` and
`CONTEXT_MAX_CHARS` in `.env`; set either limit to `0` to disable that bound.
The memory strategy is isolated in
[conversation_context.py](D:/Builds/llm-council/backend/conversation_context.py)
so summaries or semantic memory can be added later without changing the
council pipeline.

### Validation

Run the backend checks with:

```bash
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q backend tests
```

Run the frontend checks with `npm run lint` and `npm run build` from
`frontend/`.

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

**Option 2: Run manually**

Terminal 1 (Backend):
```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

## Tech Stack

- **Backend:** FastAPI (Python 3.10+), async httpx, provider abstraction (OpenRouter + Ollama)
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, npm for JavaScript

## Backend Provider + Collaboration Architecture

- [backend/providers/base.py](D:/Builds/llm-council/backend/providers/base.py) defines `BaseProvider`, the async interface used by council orchestration.
- [backend/providers/openrouter_provider.py](D:/Builds/llm-council/backend/providers/openrouter_provider.py) implements OpenRouter.
- [backend/providers/ollama_provider.py](D:/Builds/llm-council/backend/providers/ollama_provider.py) implements Ollama local models.
- [backend/providers/factory.py](D:/Builds/llm-council/backend/providers/factory.py) selects the active provider from config.
- [backend/council.py](D:/Builds/llm-council/backend/council.py) depends only on the provider interface and uses structured critique artifacts instead of rankings.
- [backend/openrouter.py](D:/Builds/llm-council/backend/openrouter.py) remains as a backward-compatible OpenRouter helper module.

### Internal Deliberation Visibility

- Internal deliberation is hidden by default.
- Optional **Developer Mode** shows candidate responses and structured critiques in the UI.

This structure is designed so future role-based agents (Planner → Retriever → Researcher → Evidence Checker → Critic → Chairman) can exchange structured artifacts without major refactoring.
