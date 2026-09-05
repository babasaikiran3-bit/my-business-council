# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key mechanism is anonymized structured critique in Stage 2, preventing model favoritism and enabling more robust synthesis.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `PROVIDER` (`openrouter` or `ollama`)
- Contains `COUNCIL_MODELS` (list of model identifiers for the selected provider)
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer)
- Contains provider-specific settings (`OPENROUTER_API_KEY`, `OPENROUTER_API_URL`, `OLLAMA_API_URL`, optional `TITLE_MODEL`)
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`providers/`**
- `base.py`: `BaseProvider` interface with async `query_model()` and `query_models_parallel()`
- `openrouter_provider.py`: OpenRouter implementation
- `ollama_provider.py`: Ollama implementation (supports multiple local models in parallel)
- `factory.py`: Config-driven provider selection

**`openrouter.py`**
- Backward-compatible OpenRouter helper module
- Delegates to `OpenRouterProvider` so existing imports still work

**`council.py`** - The Core Logic
- Depends on `BaseProvider` via `get_provider()` (not on OpenRouter module directly)
- `stage1_collect_responses()`: Parallel queries to all council models
- `stage2_collect_critiques()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Prompts models to return strict JSON critiques with fields:
    - strengths
    - weaknesses
    - missing_information
    - unsupported_claims
    - suggested_improvements
- `stage3_synthesize_final()`: synthesizer receives only anonymous responses + structured critiques (no model names)
- `is_trivial_prompt()` + `generate_direct_response()`: skip review stage for greetings/trivial prompts
- `run_full_council(..., developer_mode=False)`: hides internal deliberation by default

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, messages[]}`
- Assistant messages contain: `{role, stage1, stage2, stage3}`
- Note: metadata (developer mode flags, anonymization maps, critique summaries) is NOT persisted to storage, only returned via API

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- POST `/api/conversations/{id}/message` returns metadata in addition to stages
- Metadata includes developer-mode deliberation fields (for example `label_to_model`) and skip flags

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
Stage 2 now enforces strict JSON output for structured critiques to support deterministic parsing and future role-based agent pipelines.

### De-anonymization Strategy
- Models receive: "Response A", "Response B", etc.
- Backend creates mapping: `{"Response A": "openai/gpt-5.1", ...}`
- Frontend can display mapping only in Developer Mode
- This prevents bias while maintaining transparency

### Error Handling Philosophy
- Continue with successful responses if some models fail (graceful degradation)
- Never fail the entire request due to single model failure
- Log errors but don't expose to user unless all models fail

### UI/UX Transparency
- Internal outputs are hidden by default for end users
- Developer Mode reveals raw candidate responses and structured critiques
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
Models are configured in `backend/config.py`. Chairman can be same or different from council members. `COUNCIL_MODELS` and `CHAIRMAN_MODEL` are provider-agnostic and can point to OpenRouter IDs or local Ollama model names (e.g. `llama3.3`, `qwen3`, `mistral`, `gemma3`).

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Structured Critique Parse Failures**: If models don't follow JSON format, parser falls back gracefully and synthesis still proceeds
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only available in API responses

## Future Enhancement Ideas

- Configurable council/chairman via UI instead of config file
- Streaming responses instead of batch loading
- Export conversations to markdown/PDF
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models (o1, etc.) with special handling

## Testing Notes

Use provider-specific smoke tests or API probes to verify connectivity before adding models to council:
- OpenRouter: validate key and model IDs
- Ollama: ensure local daemon is running and models are pulled

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
