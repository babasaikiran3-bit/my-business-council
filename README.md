# LLM Council

![llmcouncil](header.jpg)

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT 5.1, Google Gemini 3.0 Pro, Anthropic Claude Sonnet 4.5, xAI Grok 4, eg.c), you can group them into your "LLM Council". This repo is a simple, local web app that essentially looks like ChatGPT except it uses OpenRouter to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Chairman LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each individual LLM is given the responses of the other LLMs. Under the hood, the LLM identities are anonymized so that the LLM can't play favorites when judging their outputs. The LLM is asked to rank them in accuracy and insight.
3. **Stage 3: Final response**. The designated Chairman of the LLM Council takes all of the model's responses and compiles them into a single final answer that is presented to the user.

## Features

This enhanced version includes 5 major features:

🎯 **Feature 1: TOON Integration** - Token optimization using TOON format (30-60% savings)
💾 **Feature 2: Multi-Database Support** - JSON, PostgreSQL, or MySQL storage backends
💬 **Feature 3: Context & Follow-ups** - Natural multi-turn conversations with memory
🛠️ **Feature 4: Advanced AI Tools** - Calculator, Wikipedia, ArXiv, DuckDuckGo, Yahoo Finance, Memory System
⚙️ **Feature 5: Conversation Management** - Delete, edit titles, temporary chat mode with 3-dot menu UI

See [FEATURES.md](FEATURES.md) for detailed feature documentation and [RUN.md](RUN.md) for complete setup instructions.

## Vibe Code Alert

This project was originally 99% vibe coded as a fun Saturday hack. This fork extends it with production-ready features including database support, tool integration, memory systems, and conversation management - all while maintaining the original vision of collaborative LLM decision-making.

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

### 2. Configure API Key

Copy the example environment file and add your API key:

```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

Required configuration:
```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

**Optional configurations** (see [.env.example](.env.example) for all options):
- Storage backend: JSON (default), PostgreSQL, or MySQL
- Feature 4: Tools (Calculator, Wikipedia, etc.) and Memory system
- All free tools enabled by default, optional paid tools (Tavily, OpenAI embeddings)

### 3. Database setup (optional)

The app defaults to JSON file storage (`DATABASE_TYPE=json`). To use a database instead:

**PostgreSQL**
1. Create a database and user:
   ```bash
   createdb llmcouncil
   createuser llmcouncil_user
   psql -c "ALTER USER llmcouncil_user WITH PASSWORD 'change-me';"
   psql -c "GRANT ALL PRIVILEGES ON DATABASE llmcouncil TO llmcouncil_user;"
   ```
2. Set `DATABASE_TYPE=postgresql` and update `POSTGRESQL_URL` in `.env`.
3. Restart the backend; tables auto-create on startup.

**MySQL**
1. Create a database and user:
   ```bash
   mysql -u root -p -e "CREATE DATABASE llmcouncil;"
   mysql -u root -p -e "CREATE USER 'llmcouncil_user'@'%' IDENTIFIED BY 'change-me';"
   mysql -u root -p -e "GRANT ALL PRIVILEGES ON llmcouncil.* TO 'llmcouncil_user'@'%';"
   ```
2. Set `DATABASE_TYPE=mysql` and update `MYSQL_URL` in `.env`.
3. Restart the backend; tables auto-create on startup.

### 3. Configure Models (Optional)

Edit `backend/config.py` to customize the council:

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
```

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

- **Backend:** FastAPI (Python 3.10+), async httpx, OpenRouter API, LangChain, SQLAlchemy
- **Frontend:** React + Vite, react-markdown for rendering, Server-Sent Events for streaming
- **Storage:** JSON files (default), PostgreSQL, or MySQL with unified storage API
- **AI Tools:** Calculator, Wikipedia, ArXiv, DuckDuckGo Search, Yahoo Finance
- **Memory:** ChromaDB with local embeddings (HuggingFace) or optional OpenAI embeddings
- **Package Management:** uv for Python, npm for JavaScript

## Documentation

- **[FEATURES.md](FEATURES.md)** - Complete feature documentation
- **[RUN.md](RUN.md)** - Detailed setup and running instructions
- **[contributions/](contributions/)** - Feature implementation details

## License

Open source - contributions welcome!
