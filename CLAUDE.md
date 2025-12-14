# CLAUDE.md - Technical Notes for Eternal Copilot

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

Eternal Copilot is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Recent Changes (December 2024)

### Tailwind CSS v4 Migration
- **CSS-first configuration**: No `tailwind.config.js` file - configuration is done via `@theme` directive in `index.css`
- **Import syntax**: Uses `@import "tailwindcss"` instead of `@tailwind` directives
- **PostCSS plugin**: Uses `@tailwindcss/postcss` instead of `tailwindcss`

### shadcn/ui Component Integration
- Migrated to shadcn/ui component library with Radix UI primitives
- Uses **zinc color palette** (neutral grays) for the design system
- Components: Button, Card, Tabs, Textarea, ScrollArea

### Resizable Sidebar Feature
- Drag the right edge to resize (min: 240px, max: 480px, default: 288px)
- Width persists in localStorage with key `eternal-copilot-sidebar-width`
- Visual grip indicator appears on hover

### CSS Reset Fix
- **Removed** `margin: 0; padding: 0` from the universal selector (`*`)
- This was overriding Tailwind utility classes like `px-14` and `px-12`
- Tailwind's Preflight already handles CSS normalization

### ScrollArea Padding Fix
- Padding must be applied to an **inner wrapper div**, NOT the ScrollArea root
- Radix ScrollArea wraps content in a Viewport that doesn't inherit root padding

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COPILOT_MODELS` (list of OpenRouter model identifiers) - currently 5 models:
  - `openai/gpt-5.2-pro`
  - `google/gemini-3-pro-preview`
  - `anthropic/claude-opus-4.5`
  - `x-ai/grok-code-fast-1`
  - `x-ai/grok-4`
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer) - currently `google/gemini-3-pro-preview`
- Contains `PROMPT_IMPROVER_MODEL` (model for "Improve Prompt" feature) - currently `google/gemini-3-pro-preview`
- Uses environment variable `OPENROUTER_API_KEY` from `.env`
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`openrouter.py`**
- `query_model()`: Single async model query
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`
- Returns dict with 'content' and optional 'reasoning_details'
- Graceful degradation: returns None on failure, continues with successful responses

**`copilot.py`** - The Core Logic
- `improve_user_prompt()`: Uses `PROMPT_IMPROVER_MODEL` to rewrite user prompts for clarity
- `stage1_collect_responses()`: Parallel queries to all copilot models
- `stage2_collect_rankings()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Prompts models to evaluate and rank (with strict format requirements)
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
- `stage3_synthesize_final()`: Chairman synthesizes from all responses + rankings
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both numbered lists and plain format
- `calculate_aggregate_rankings()`: Computes average rank position across all peer evaluations
- `generate_conversation_title()`: Uses `google/gemini-2.5-flash` for fast title generation from first message
- `run_full_copilot()`: Orchestrates the complete 3-stage process

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, messages[]}`
- Assistant messages contain: `{role, stage1, stage2, stage3}`
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- API Endpoints:
  - `GET /` - Health check
  - `POST /api/improve-prompt` - Improve user prompt using LLM
  - `GET /api/conversations` - List all conversations
  - `POST /api/conversations` - Create new conversation
  - `GET /api/conversations/{id}` - Get specific conversation
  - `POST /api/conversations/{id}/message` - Send message (batch response)
  - `POST /api/conversations/{id}/message/stream` - Send message with SSE streaming
- Streaming endpoint sends Server-Sent Events for progressive UI updates:
  - `stage1_start`, `stage1_complete`, `stage2_start`, `stage2_complete`, `stage3_start`, `stage3_complete`
  - `title_complete` - when conversation title is generated
  - `complete` - when all stages finish
  - `error` - on failure
- Metadata returned includes: label_to_model mapping and aggregate_rankings

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- Handles message sending and metadata storage
- Important: metadata is stored in the UI state for display but not persisted to backend JSON

**`components/Sidebar.jsx`**
- Resizable sidebar with drag-to-resize functionality
- localStorage persistence for width (key: `eternal-copilot-sidebar-width`)
- Min: 240px, Max: 480px, Default: 288px
- Uses shadcn/ui ScrollArea with padding fix (see Common Gotchas)
- Custom horizontal padding: `px-14` for header, `px-12` for conversation list

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable) using shadcn/ui Textarea
- Enter to send, Shift+Enter for new line
- User messages wrapped in markdown-content class for padding
- Uses shadcn/ui Card, Button, ScrollArea components
- **Prompt Improvement Feature**:
  - "✨ Improve Prompt" button uses `/api/improve-prompt` endpoint
  - Shows original prompt below textarea for comparison after improvement
  - "↩ Undo" button reverts to original prompt if needed

**`components/Stage1.jsx`**
- Tab view of individual model responses using shadcn/ui Tabs
- ReactMarkdown rendering with markdown-content wrapper
- Wrapped in shadcn/ui Card component

**`components/Stage2.jsx`**
- **Critical Feature**: Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display (models receive anonymous labels)
- Shows "Extracted Ranking" below each evaluation so users can validate parsing
- Aggregate rankings shown with average position and vote count
- Explanatory text clarifies that boldface model names are for readability only

**`components/Stage3.jsx`**
- Final synthesized answer from Lead Synthesizer
- Uses `bg-muted/30` background to highlight conclusion (shadcn/ui style)

**`components/ui/*.jsx`** (shadcn/ui Components)
- `button.jsx` - Button with variants (default, destructive, outline, secondary, ghost, link)
- `card.jsx` - Card, CardHeader, CardContent, CardTitle, CardDescription, CardFooter
- `tabs.jsx` - Tabs, TabsList, TabsTrigger, TabsContent
- `textarea.jsx` - Textarea with focus ring styling
- `scroll-area.jsx` - ScrollArea, ScrollBar (Radix-based)

**`lib/utils.js`**
- `cn()` function - merges Tailwind classes using `clsx` and `tailwind-merge`

**Styling (`index.css`)**
- Light mode theme with shadcn/ui zinc color palette
- CSS-first Tailwind v4 configuration via `@theme` directive
- Global markdown styling with `.markdown-content` class
- No `tailwind.config.js` - all theme config in CSS

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
- Backend creates mapping: `{"Response A": "openai/gpt-5.2-pro", ...}`
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
Models are hardcoded in `backend/config.py`. Chairman can be same or different from copilot models. The current default is Gemini as chairman per user preference.

## System Requirements

### Node.js Version Requirement
- **Node.js 18+ required** (20+ recommended)
- Vite 7.x uses modern JavaScript features (`??=` operator) not available in Node.js 14.x
- Error symptom: `SyntaxError: Unexpected token '??='`

### Installing Node.js 20 on macOS (Homebrew)
```bash
brew install node@20
```

**Important:** Node.js 20 is installed as "keg-only" (not symlinked to PATH). Add to shell config:

```bash
# For Apple Silicon Macs (~/.zshrc or ~/.bash_profile)
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"

# For Intel Macs
export PATH="/usr/local/opt/node@20/bin:$PATH"
```

Then run `source ~/.zshrc` or restart terminal.

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Ranking Parse Failures**: If models don't follow format, fallback regex extracts any "Response X" patterns in order
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only available in API responses
5. **Node.js Version Too Old**: If frontend fails with `Unexpected token '??='`, upgrade to Node.js 18+ (see System Requirements above)
6. **Keg-only Node.js**: After `brew install node@20`, you must manually add the PATH to your shell config file
7. **CSS Reset Overriding Tailwind**: Never add `padding: 0` or `margin: 0` to the universal selector (`*`) - this overrides Tailwind utilities. Tailwind's Preflight already handles CSS normalization.
8. **ScrollArea Padding Not Working**: Radix ScrollArea wraps content in a Viewport. Padding applied to ScrollArea root doesn't reach content. **Solution**: Wrap content in a `<div>` with padding inside ScrollArea.
9. **CSS Changes Not Visible**: Always hard refresh (`Cmd+Shift+R`) after CSS changes. Vite's HMR may not clear browser cache for CSS.
10. **No tailwind.config.js**: This is intentional for Tailwind CSS v4. Configuration is done via `@theme` directive in `index.css`, not JavaScript.

## Future Enhancement Ideas

- Configurable copilot models/chairman via UI instead of config file
- ~~Streaming responses instead of batch loading~~ ✅ Implemented via SSE
- ~~Resizable sidebar~~ ✅ Implemented with localStorage persistence
- ~~shadcn/ui component migration~~ ✅ Completed with zinc color palette
- Export conversations to markdown/PDF
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models (o1, etc.) with special handling
- Dark mode toggle (theme infrastructure is in place via CSS variables)
- Keyboard shortcuts for common actions (new conversation, toggle sidebar)
- Search/filter conversations in sidebar

## Testing Notes

Use `test_openrouter.py` to verify API connectivity and test different model identifiers before adding to the copilot. The script tests both streaming and non-streaming modes.

**Note:** The `test_openrouter.py` file may need to be created. You can test OpenRouter connectivity manually by running the backend and making API calls via the frontend or curl.

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
Stage 3: Lead Synthesizer synthesis with full context
    ↓
Return: {stage1, stage2, stage3, metadata}
    ↓
Frontend: Display with tabs + validation UI
```

The entire flow is async/parallel where possible to minimize latency.
