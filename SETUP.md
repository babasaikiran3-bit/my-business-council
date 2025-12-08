# LLM Council - Setup Guide

Complete guide for setting up LLM Council with OpenRouter, Ollama, or LMStudio.

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv pip install -r requirements.txt

# Or using pip
pip install -r requirements.txt
```

### 2. Configure Providers

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure your desired providers (see Configuration Options below).

### 3. Configure Models

Edit `backend/config.py` and set your council models:

```python
# Example: All cloud models (OpenRouter)
COUNCIL_MODELS = [
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4",
    "google/gemini-2.0-flash-exp",
]
CHAIRMAN_MODEL = "google/gemini-2.0-flash-exp"
```

### 4. Start the Backend

```bash
python -m backend.main
```

The API will be available at http://localhost:8001

### 5. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at http://localhost:5173

---

## Configuration Options

### Option 1: Cloud Only (OpenRouter)

**Best for:** Access to cutting-edge models, no local setup required

**Requirements:**
- OpenRouter API key (get one at https://openrouter.ai/keys)

**Configuration:**

`.env`:
```bash
DEFAULT_PROVIDER=openrouter
OPENROUTER_API_KEY=your_api_key_here
```

`backend/config.py`:
```python
COUNCIL_MODELS = [
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4",
    "google/gemini-2.0-flash-exp",
    "x-ai/grok-3",
]
CHAIRMAN_MODEL = "google/gemini-2.0-flash-exp"
```

**Pros:**
- Latest frontier models
- No local GPU required
- Faster inference

**Cons:**
- Costs per token
- Requires internet
- Data sent to third parties

---

### Option 2: Local Only (Ollama)

**Best for:** Privacy, no API costs, offline usage

**Requirements:**
- Ollama installed (https://ollama.ai/)
- Sufficient RAM/GPU for models

**Setup:**

1. Install Ollama:
   ```bash
   # macOS/Linux
   curl https://ollama.ai/install.sh | sh

   # Or download from https://ollama.ai/
   ```

2. Pull models:
   ```bash
   ollama pull llama2:13b-chat
   ollama pull mistral:7b-instruct
   ollama pull codellama:34b-instruct
   ```

3. Start Ollama server:
   ```bash
   ollama serve
   ```

**Configuration:**

`.env`:
```bash
DEFAULT_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

`backend/config.py`:
```python
COUNCIL_MODELS = [
    "ollama:llama2:13b-chat",
    "ollama:mistral:7b-instruct",
    "ollama:codellama:34b-instruct",
]
CHAIRMAN_MODEL = "ollama:mistral:7b-instruct"
```

**Pros:**
- 100% private
- No API costs
- Works offline
- Full control

**Cons:**
- Requires powerful hardware
- Slower inference than cloud
- Limited to open-source models

---

### Option 3: Local Only (LMStudio)

**Best for:** GUI-based local model management, privacy

**Requirements:**
- LMStudio installed (https://lmstudio.ai/)
- Downloaded models

**Setup:**

1. Install LMStudio from https://lmstudio.ai/

2. Download models in LMStudio UI

3. Start the local server:
   - Open LMStudio
   - Go to Developer tab
   - Click "Start Server"
   - Server runs at http://localhost:1234

**Configuration:**

`.env`:
```bash
DEFAULT_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1/chat/completions
```

`backend/config.py`:
```python
COUNCIL_MODELS = [
    "lmstudio:mistral-7b",
    "lmstudio:llama2-13b",
]
CHAIRMAN_MODEL = "lmstudio:mistral-7b"
```

---

### Option 4: Mixed Mode (Recommended)

**Best for:** Balance of quality, cost, and privacy

**Use case:** Use local models for council deliberation, cloud for synthesis

**Configuration:**

`.env`:
```bash
DEFAULT_PROVIDER=openrouter
OPENROUTER_API_KEY=your_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
```

`backend/config.py`:
```python
COUNCIL_MODELS = [
    # Local models for cost-effective deliberation
    "ollama:llama2:13b-chat",
    "ollama:mistral:7b-instruct",
    # High-quality cloud model for comparison
    "openrouter:gpt-4o",
]
# Use powerful cloud model for final synthesis
CHAIRMAN_MODEL = "openrouter:anthropic/claude-sonnet-4"
```

**Benefits:**
- Reduce API costs (local models for Stage 1 & 2)
- Use best cloud model for final answer (Stage 3)
- Compare local vs cloud performance

---

## Model Identifier Format

LLM Council supports flexible model identifiers:

### Prefixed Format (Explicit Provider)
```python
"ollama:llama2"           # Ollama provider
"openrouter:gpt-4"        # OpenRouter provider
"lmstudio:mistral"        # LMStudio provider
```

### Simple Format (Uses DEFAULT_PROVIDER)
```python
# If DEFAULT_PROVIDER=openrouter:
"gpt-4"                   # → openrouter:gpt-4
"anthropic/claude-3"      # → openrouter:anthropic/claude-3

# If DEFAULT_PROVIDER=ollama:
"llama2"                  # → ollama:llama2
```

---

## Testing Your Setup

Run the provider test script:

```bash
python test_providers.py
```

This verifies:
- ✓ Model identifier parsing
- ✓ Provider validation
- ✓ Provider routing

---

## Troubleshooting

### "Provider validation failed"

**OpenRouter:**
- Check `OPENROUTER_API_KEY` is set in `.env`
- Verify key is valid at https://openrouter.ai/keys

**Ollama:**
- Check server is running: `curl http://localhost:11434/api/tags`
- Verify models are installed: `ollama list`
- Try: `ollama serve` to start server

**LMStudio:**
- Ensure local server is started in LMStudio
- Check server URL: http://localhost:1234
- Verify a model is loaded

### "All models failed to respond"

Check configuration:
```python
from backend.providers import ProviderFactory
from backend.config import *

factory = ProviderFactory(
    default_provider=DEFAULT_PROVIDER,
    openrouter_api_key=OPENROUTER_API_KEY,
    ollama_base_url=OLLAMA_BASE_URL,
    lmstudio_base_url=LMSTUDIO_BASE_URL
)

print(factory.validate_all())
print(factory.get_available_providers())
```

### "Module not found" errors

Install all dependencies:
```bash
pip install fastapi uvicorn[standard] python-dotenv httpx pydantic ollama
```

---

## Performance Tips

1. **Local Models:**
   - Use quantized models (Q4_K_M, Q5_K_M) for better speed
   - Smaller models (7B) for council, larger (13B+) for chairman
   - Close other GPU-intensive applications

2. **Cloud Models:**
   - Use fast models for title generation (e.g., gemini-flash)
   - Consider rate limits for parallel requests
   - Monitor costs with OpenRouter dashboard

3. **Mixed Mode:**
   - Local: Stage 1 & 2 (3-4 models, many requests)
   - Cloud: Stage 3 (1 model, 1 request per query)
   - Optimal cost/quality balance

---

## Advanced Configuration

### Custom Ollama Port
```bash
# In .env
OLLAMA_BASE_URL=http://localhost:11435
```

### Custom LMStudio Port
```bash
# In .env
LMSTUDIO_BASE_URL=http://localhost:8080/v1/chat/completions
```

### Multiple Chairman Candidates
You can use different models for different purposes:
```python
CHAIRMAN_MODEL = "openrouter:gpt-4o"
CONVERSATION_TITLE_MODEL = "ollama:mistral"  # Fast local model for titles
```

---

## Next Steps

1. Configure your preferred setup (cloud/local/mixed)
2. Test with `python test_providers.py`
3. Start backend and frontend
4. Try your first query!

For more details, see:
- `CLAUDE.md` - Technical architecture
- `.env.example` - Configuration examples
- `backend/config.py` - Model configuration
