# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Multi-Provider System

The application now supports three LLM provider modes via a provider abstraction layer:

1. **OpenRouter Mode** (default): All models use OpenRouter API (cloud-based, paid)
2. **Ollama Mode**: All models use local Ollama server (self-hosted, free)
3. **Mixed Mode**: Combine both providers with explicit prefixes per model

**Key Design Decisions:**
- **Backward Compatibility**: Existing OpenRouter configs work without changes
- **Zero-Configuration Local**: Ollama mode requires no API keys
- **Cost Optimization**: Mixed mode allows free local + premium cloud models
- **Provider Abstraction**: Clean separation between provider logic and core council logic

### Backend Structure (`backend/`)

**`config.py`**
- Contains `LLM_PROVIDER` (determines provider mode: openrouter/ollama/mixed)
- Contains `COUNCIL_MODELS` (list of model identifiers, format depends on mode)
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer)
- Adapts model configurations based on `LLM_PROVIDER` setting
- Environment variables from `.env`:
  - `OPENROUTER_API_KEY`: Required for openrouter/mixed modes
  - `OLLAMA_BASE_URL`: Required for ollama/mixed modes (default: http://localhost:11434)
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**Model Specification Formats:**
- **OpenRouter mode**: `"openai/gpt-4o"`, `"google/gemini-2.5-flash-lite"`
- **Ollama mode**: `"llama3.1:8b"`, `"mistral:latest"`
- **Mixed mode**: `"openrouter:openai/gpt-4o"`, `"ollama:llama3.1:8b"`

**`providers/` directory** - Provider Abstraction Layer

**`providers/base.py`**
- `LLMProvider` abstract base class defining provider interface
- All providers must implement: `query_model()` and `query_models_parallel()`
- Ensures consistent API across different provider implementations

**`providers/openrouter.py`**
- `OpenRouterProvider`: Implementation for OpenRouter API
- Handles OpenRouter-specific API format and authentication
- Supports both standard and reasoning models (o1, etc.)
- `query_model()`: Single async model query to OpenRouter
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`
- Returns dict with 'content' and optional 'reasoning_details'
- Graceful degradation: returns None on failure, continues with successful responses

**`providers/ollama.py`**
- `OllamaProvider`: Implementation for local Ollama server
- Communicates with Ollama HTTP API (default: localhost:11434)
- Supports streaming and non-streaming responses
- `query_model()`: Single async model query to Ollama
- `query_models_parallel()`: Parallel queries to local Ollama server
- Same return format as OpenRouter for consistency
- Error handling for common issues (server not running, model not found)

**`providers/__init__.py`** - Factory and Routing Logic
- `get_provider(provider_name)`: Factory function with singleton pattern
- `parse_model_spec(model_spec)`: Parses model specifications into (provider, model_id)
- `query_model(model_spec, messages)`: Routes single query to appropriate provider
- `query_models_parallel(model_specs, messages)`: Intelligent parallel routing
- Supports both simple mode (global provider) and mixed mode (per-model provider)
- Groups queries by provider for efficient batch execution
- All queries execute concurrently (both within and across providers)

**`council.py`** - The Core Logic
- `stage1_collect_responses()`: Parallel queries to all council models
- `stage2_collect_rankings()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Prompts models to evaluate and rank (with strict format requirements)
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
- `stage3_synthesize_final()`: Chairman synthesizes from all responses + rankings
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both numbered lists and plain format
- `calculate_aggregate_rankings()`: Computes average rank position across all peer evaluations

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, messages[]}`
- Assistant messages contain: `{role, stage1, stage2, stage3}`
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- POST `/api/conversations/{id}/message` returns metadata in addition to stages
- Metadata includes: label_to_model mapping and aggregate_rankings

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- Handles message sending and metadata storage
- Important: metadata is stored in the UI state for display but not persisted to backend JSON

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable)
- Enter to send, Shift+Enter for new line
- User messages wrapped in markdown-content class for padding

**`components/Stage1.jsx`**
- Tab view of individual model responses
- ReactMarkdown rendering with markdown-content wrapper

**`components/Stage2.jsx`**
- **Critical Feature**: Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display (models receive anonymous labels)
- Shows "Extracted Ranking" below each evaluation so users can validate parsing
- Aggregate rankings shown with average position and vote count
- Explanatory text clarifies that boldface model names are for readability only

**`components/Stage3.jsx`**
- Final synthesized answer from chairman
- Green-tinted background (#f0fff0) to highlight conclusion

**Styling (`*.css`)**
- Light mode theme (not dark mode)
- Primary color: #4a90e2 (blue)
- Global markdown styling in `index.css` with `.markdown-content` class
- 12px padding on all markdown content to prevent cluttered appearance

## Key Design Decisions

### Stage 2 Prompt Format
The Stage 2 prompt is very specific to ensure parseable output:
```
1. Evaluate each response individually first
2. Provide "FINAL RANKING:" header
3. Numbered list format: "1. Response C", "2. Response A", etc.
4. No additional text after ranking section
```

This strict format allows reliable parsing while still getting thoughtful evaluations.

### De-anonymization Strategy
- Models receive: "Response A", "Response B", etc.
- Backend creates mapping: `{"Response A": "openai/gpt-5.1", ...}`
- Frontend displays model names in **bold** for readability
- Users see explanation that original evaluation used anonymous labels
- This prevents bias while maintaining transparency

### Error Handling Philosophy
- Continue with successful responses if some models fail (graceful degradation)
- Never fail the entire request due to single model failure
- Log errors but don't expose to user unless all models fail

### UI/UX Transparency
- All raw outputs are inspectable via tabs
- Parsed rankings shown below raw text for validation
- Users can verify system's interpretation of model outputs
- This builds trust and allows debugging of edge cases

## Provider Abstraction Pattern

### Architecture Pattern: Abstract Factory

The multi-provider system uses the **Abstract Factory** and **Strategy** patterns:

```
LLMProvider (Abstract Base Class)
    ↓
    ├── OpenRouterProvider (Concrete Implementation)
    ├── OllamaProvider (Concrete Implementation)
    └── Future providers... (Extensible)

Factory Function: get_provider(name) → LLMProvider instance
Routing Layer: parse_model_spec() + query_model() + query_models_parallel()
```

**Benefits:**
- **Encapsulation**: Provider-specific logic isolated in dedicated classes
- **Extensibility**: Add new providers by implementing `LLMProvider` interface
- **Consistency**: All providers return same response format
- **Testability**: Mock providers easily for testing
- **Performance**: Singleton pattern for provider instances

### Model Specification Parsing

The system intelligently routes models to providers:

1. **Simple Mode** (openrouter or ollama):
   - `"llama3.1:8b"` → Uses `LLM_PROVIDER` from config
   - No prefix needed, provider determined globally

2. **Mixed Mode**:
   - `"ollama:llama3.1:8b"` → Explicitly routes to Ollama
   - `"openrouter:openai/gpt-4"` → Explicitly routes to OpenRouter
   - All models MUST have prefix in mixed mode

3. **Parsing Logic**:
   ```python
   # Check for explicit prefix
   if model_spec.startswith("ollama:"):
       return ("ollama", model_spec[7:])
   elif model_spec.startswith("openrouter:"):
       return ("openrouter", model_spec[11:])

   # Fall back to global provider (if not mixed mode)
   return (LLM_PROVIDER, model_spec)
   ```

### Parallel Execution Strategy

The routing layer optimizes parallel execution:

1. **Input**: List of model specs (potentially mixed providers)
2. **Grouping**: Group models by provider for batch execution
3. **Parallel Provider Queries**: Each provider batch runs concurrently
4. **Result Aggregation**: Map provider results back to original model specs
5. **Output**: Dictionary of all results (including failures as None)

**Example Flow:**
```python
# Input
model_specs = [
    "ollama:llama3.1:8b",
    "ollama:mistral:latest",
    "openrouter:openai/gpt-4",
    "openrouter:anthropic/claude-3.5-sonnet"
]

# Grouping
{
    "ollama": ["llama3.1:8b", "mistral:latest"],
    "openrouter": ["openai/gpt-4", "anthropic/claude-3.5-sonnet"]
}

# Execution (concurrent)
await asyncio.gather(
    ollama_provider.query_models_parallel([...]),  # 2 models
    openrouter_provider.query_models_parallel([...])  # 2 models
)

# Result mapping back to original specs
```

### Error Handling Philosophy

**Graceful Degradation at Every Layer:**

1. **Provider Level**:
   - Individual model failures return None
   - Don't propagate exceptions to council logic
   - Log errors but continue with successful responses

2. **Routing Level**:
   - Invalid model specs → None result
   - Provider instantiation failures → None for affected models
   - Parse errors → None result

3. **Council Level**:
   - Continue with successful responses from Stage 1
   - Adapt Stage 2 ranking to available responses
   - Stage 3 synthesis uses whatever data is available

**Rationale**: Better to get partial results than complete failure. The council system is designed to aggregate multiple perspectives, so it's robust to individual model failures.

## Migration Guide: Single Provider to Multi-Provider

### For Existing Users (Minimal Changes)

If you're already using OpenRouter, **no changes required**. The system defaults to `openrouter` mode for backward compatibility.

**Optional**: Add `LLM_PROVIDER=openrouter` to `.env` for explicitness.

### Migrating to Ollama (Local)

1. Install Ollama (see README.md)
2. Pull models:
   ```bash
   ollama pull llama3.1:8b
   ollama pull mistral:latest
   ollama pull qwen2.5:3b
   ```
3. Update `.env`:
   ```bash
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   ```
4. Update `backend/config.py`:
   ```python
   COUNCIL_MODELS = [
       "llama3.1:8b",
       "mistral:latest",
       "qwen2.5:3b",
   ]
   CHAIRMAN_MODEL = "llama3.1:8b"
   ```
5. Restart backend

### Migrating to Mixed Mode (Hybrid)

1. Set up both OpenRouter and Ollama
2. Update `.env`:
   ```bash
   LLM_PROVIDER=mixed
   OPENROUTER_API_KEY=sk-or-v1-...
   OLLAMA_BASE_URL=http://localhost:11434
   ```
3. Update `backend/config.py` with prefixes:
   ```python
   COUNCIL_MODELS = [
       "ollama:llama3.1:8b",              # Local, free
       "ollama:mistral:latest",           # Local, free
       "openrouter:google/gemini-2.5-flash-lite",  # Cloud, paid
       "openrouter:anthropic/claude-3.5-haiku",  # Cloud, paid
   ]
   CHAIRMAN_MODEL = "openrouter:google/gemini-2.5-flash-lite"
   ```
4. Restart backend

### Adding a New Provider (For Developers)

To add support for a new LLM provider (e.g., HuggingFace, Anthropic Direct, etc.):

1. Create `backend/providers/your_provider.py`:
   ```python
   from backend.providers.base import LLMProvider

   class YourProvider(LLMProvider):
       def __init__(self, api_key: str):
           self.api_key = api_key

       async def query_model(self, model_id, messages, timeout=120.0):
           # Implement API call to your provider
           # Return {"content": str, "reasoning_details": dict or None}
           # Return None on failure
           pass

       async def query_models_parallel(self, model_ids, messages):
           # Implement parallel queries
           # Return {model_id: result_dict} for all models
           pass
   ```

2. Update `backend/providers/__init__.py`:
   ```python
   from backend.providers.your_provider import YourProvider

   def get_provider(provider_name: str) -> LLMProvider:
       if provider_name == "your_provider":
           return YourProvider(api_key=YOUR_PROVIDER_API_KEY)
       # ... existing code

   def parse_model_spec(model_spec: str):
       if model_spec.startswith("your_provider:"):
           return ("your_provider", model_spec[14:])
       # ... existing code
   ```

3. Update `backend/config.py`:
   ```python
   VALID_PROVIDERS = ["openrouter", "ollama", "mixed", "your_provider"]
   YOUR_PROVIDER_API_KEY = os.getenv("YOUR_PROVIDER_API_KEY")
   ```

4. Test thoroughly with both simple and mixed modes

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`) not absolute imports. This is critical for Python's module system to work correctly when running as `python -m backend.main`.

### Provider Imports in council.py
The core council logic now imports from `backend.providers` instead of `backend.openrouter`:
```python
from backend.providers import query_model, query_models_parallel
```
This maintains backward compatibility while routing to the appropriate provider.

### Port Configuration
- Backend: 8001 (changed from 8000 to avoid conflict)
- Frontend: 5173 (Vite default)
- Update both `backend/main.py` and `frontend/src/api.js` if changing

### Markdown Rendering
All ReactMarkdown components must be wrapped in `<div className="markdown-content">` for proper spacing. This class is defined globally in `index.css`.

### Model Configuration
Models are hardcoded in `backend/config.py`. Chairman can be same or different from council members. The current default is Gemini as chairman per user preference.

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Ranking Parse Failures**: If models don't follow format, fallback regex extracts any "Response X" patterns in order
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only available in API responses

## Future Enhancement Ideas

- Configurable council/chairman via UI instead of config file
- Streaming responses instead of batch loading
- Export conversations to markdown/PDF
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models (o1, etc.) with special handling

## Testing Notes

Use `test_openrouter.py` to verify API connectivity and test different model identifiers before adding to council. The script tests both streaming and non-streaming modes.

## Data Flow Summary

```
User Query
    ↓
Stage 1: Parallel queries → [individual responses]
    ↓
Stage 2: Anonymize → Parallel ranking queries → [evaluations + parsed rankings]
    ↓
Aggregate Rankings Calculation → [sorted by avg position]
    ↓
Stage 3: Chairman synthesis with full context
    ↓
Return: {stage1, stage2, stage3, metadata}
    ↓
Frontend: Display with tabs + validation UI
```

The entire flow is async/parallel where possible to minimize latency.
