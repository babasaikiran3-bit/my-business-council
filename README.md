# LLM Council

![llmcouncil](header.jpg)

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT 5.1, Google Gemini 3.0 Pro, Anthropic Claude Sonnet 4.5, xAI Grok 4, eg.c), you can group them into your "LLM Council". This repo is a simple, local web app that essentially looks like ChatGPT except it uses OpenRouter to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Chairman LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each individual LLM is given the responses of the other LLMs. Under the hood, the LLM identities are anonymized so that the LLM can't play favorites when judging their outputs. The LLM is asked to rank them in accuracy and insight.
3. **Stage 3: Final response**. The designated Chairman of the LLM Council takes all of the model's responses and compiles them into a single final answer that is presented to the user.

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

### 2. Choose Your LLM Provider

LLM Council supports three provider modes:

- **OpenRouter** (cloud-based): Access to 100+ models via API, requires paid credits
- **Ollama** (local): Run models on your own hardware, completely free and private
- **Mixed** (hybrid): Combine both providers for cost/quality optimization

### 3. Provider Configuration

#### Option A: OpenRouter (Cloud-based)

**1. Get API Key**

Sign up at [openrouter.ai](https://openrouter.ai/) and get your API key. Make sure to purchase credits or enable automatic top-up.

**2. Create `.env` file**

```bash
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
```

**3. Configure models in `backend/config.py`** (optional)

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
```

See available models at [openrouter.ai/models](https://openrouter.ai/models)

#### Option B: Ollama (Local)

**1. Install Ollama**

```bash
# Linux & Mac
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download
```

**2. Start Ollama service**

```bash
# Ollama typically starts automatically after installation
# To verify it's running:
curl http://localhost:11434/api/version
```

**3. Pull models**

```bash
# Download the models you want to use
ollama pull llama3.1:latest
ollama pull mistral:latest
ollama pull qwen2.5:3b
ollama pull phi3:latest
```

See available models at [ollama.com/library](https://ollama.com/library)

**4. Create `.env` file**

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

**5. Configure models in `backend/config.py`** (optional)

```python
COUNCIL_MODELS = [
    "llama3.1:8b",
    "mistral:latest",
    "qwen2.5:3b",
    "phi3:latest",
]

CHAIRMAN_MODEL = "llama3.1:8b"
```

#### Option C: Mixed (Hybrid)

Combine local and cloud models for cost optimization.

**1. Set up both providers**

Follow installation steps for both OpenRouter and Ollama above.

**2. Create `.env` file**

```bash
LLM_PROVIDER=mixed
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
OLLAMA_BASE_URL=http://localhost:11434
```

**3. Configure models in `backend/config.py`** (optional)

Prefix each model with its provider:

```python
COUNCIL_MODELS = [
    "ollama:llama3.1:8b",              # Local, fast, free
    "ollama:mistral:latest",           # Local, fast, free
    "openrouter:google/gemini-2.5-flash-lite",  # Cloud, paid
    "openrouter:anthropic/claude-3.5-haiku",  # Cloud, paid
]

CHAIRMAN_MODEL = "openrouter:google/gemini-2.5-flash-lite"
```

**Benefits of mixed mode:**
- Use free local models for council deliberation
- Use premium cloud models for final synthesis
- Optimize cost vs quality trade-offs
- Keep sensitive data local while using cloud for general queries

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

- **Backend:** FastAPI (Python 3.10+), async httpx, multi-provider support (OpenRouter, Ollama)
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, npm for JavaScript
