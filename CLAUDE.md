# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Provider Abstraction System (NEW!)

**Multi-Provider Support**
LLM Council now supports three providers out of the box:
- **OpenRouter**: Cloud models (GPT-4, Claude, Gemini, etc.)
- **Ollama**: Local models (Llama2, Mistral, CodeLlama, etc.)
- **LMStudio**: Local models via OpenAI-compatible API

**Model Identifier Format**
Models use a flexible identifier format:
- **Prefixed**: `provider:model` (e.g., `ollama:llama2`, `openrouter:gpt-4`)
- **Simple**: `model` (uses `DEFAULT_PROVIDER` from config)

This enables:
- **Cloud-only**: All models via OpenRouter (requires API key, pay-per-use)
- **Local-only**: All models via Ollama/LMStudio (100% private, free)
- **Mixed mode**: Combine providers (e.g., local council + cloud chairman)

**Provider Architecture (`backend/providers/`)**

`base.py` - Abstract base class
- Defines `Provider` interface with `query()` and `query_batch()` methods
- All providers inherit from this base class
- Enforces consistent API across providers

`openrouter.py` - OpenRouterProvider
- Cloud provider using OpenRouter API
- Requires API key from environment
- Supports all OpenRouter models (GPT, Claude, Gemini, etc.)

`ollama.py` - OllamaProvider
- Local provider using Ollama's native API
- Uses ollama library's `AsyncClient.chat()` method
- Default URL: http://localhost:11434

`lmstudio.py` - LMStudioProvider
- Local provider using OpenAI-compatible API
- No authentication required
- Default URL: http://localhost:1234/v1/chat/completions

`factory.py` - ProviderFactory
- Central routing system for model requests
- Parses model identifiers and routes to appropriate provider
- Handles parallel queries across multiple providers
- Caches provider instances for efficiency
- Validates provider configuration on initialization

**How It Works**
1. `council.py` creates ProviderFactory singleton with config
2. Model identifiers like `["ollama:llama2", "openrouter:gpt-4"]` are passed to factory
3. Factory parses each identifier: `("ollama", "llama2")`, `("openrouter", "gpt-4")`
4. Factory routes to appropriate provider and executes query
5. Results returned with original model identifier as key

**Configuration**
See `.env.example` for complete setup instructions. Key variables:
- `DEFAULT_PROVIDER`: Provider for unprefixed model names
- `OPENROUTER_API_KEY`: Required for OpenRouter models
- `OLLAMA_BASE_URL`: Ollama server URL (default: localhost:11434)
- `LMSTUDIO_BASE_URL`: LMStudio server URL (default: localhost:1234)

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COUNCIL_MODELS` (list of model identifiers, any provider)
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer)
- Contains `CONVERSATION_TITLE_MODEL` (fast model for title generation)
- Contains provider configuration (URLs, API keys via environment)
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)
- **Model identifier examples**:
  - Cloud: `"openai/gpt-4"`, `"anthropic/claude-sonnet-4"`
  - Local: `"ollama:llama2"`, `"lmstudio:mistral"`
  - Mixed: `["ollama:llama2", "openrouter:gpt-4"]`

**`council.py`** - The Core Logic
- `get_factory()`: Creates/returns ProviderFactory singleton with config
- `stage1_collect_responses()`: Parallel queries to all council models via factory
- `stage2_collect_rankings()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Prompts models to evaluate and rank (with strict format requirements)
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
  - Uses same council models via factory (supports mixed providers)
- `stage3_synthesize_final()`: Chairman synthesizes from all responses + rankings
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both numbered lists and plain format
- `calculate_aggregate_rankings()`: Computes average rank position across all peer evaluations
- `generate_conversation_title()`: Fast title generation for conversations
- All model queries go through ProviderFactory for automatic routing

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

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`) not absolute imports. This is critical for Python's module system to work correctly when running as `python -m backend.main`.

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

**Provider Testing**
Before configuring models in production:

1. **OpenRouter**: Verify API key and model availability
   - Check models at https://openrouter.ai/models
   - Test with simple query first

2. **Ollama**: Ensure server is running and models are pulled
   ```bash
   ollama serve  # Start server
   ollama pull llama2  # Download model
   ollama list  # Verify installed models
   curl http://localhost:11434/api/tags  # Check API
   ```

3. **LMStudio**: Start local server and load model
   - Open LMStudio → Developer → Start Server
   - Verify server at http://localhost:1234

**Factory Validation**
The ProviderFactory has built-in validation:
```python
from backend.providers import ProviderFactory
factory = ProviderFactory(...)
print(factory.validate_all())  # Check all providers
print(factory.get_available_providers())  # List working providers
```

**Testing Mixed Mode**
Set up a test configuration with mixed providers:
```python
COUNCIL_MODELS = [
    "ollama:llama2",  # Local
    "openrouter:gpt-4o",  # Cloud
]
```
Verify all providers respond correctly before production use.

## Data Flow Summary

```
User Query
    ↓
ProviderFactory initialization (singleton)
    ├─ OpenRouterProvider (if configured)
    ├─ OllamaProvider (if configured)
    └─ LMStudioProvider (if configured)
    ↓
Stage 1: Parse model identifiers → Route to providers → Parallel queries
    → [individual responses with original model IDs]
    ↓
Stage 2: Anonymize → Route to providers → Parallel ranking queries
    → [evaluations + parsed rankings]
    ↓
Aggregate Rankings Calculation → [sorted by avg position]
    ↓
Stage 3: Route chairman model to provider → Synthesis with full context
    → [final answer]
    ↓
Return: {stage1, stage2, stage3, metadata}
    ↓
Frontend: Display with tabs + validation UI
```

**Key Points:**
- All model queries go through ProviderFactory
- Factory automatically routes based on model identifier prefix
- Parallel execution happens both within and across providers
- Each stage can use models from different providers (mixed mode)
- The entire flow is async/parallel where possible to minimize latency
