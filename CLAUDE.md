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
- Components: Button, Card, Tabs, Textarea, ScrollArea, Sidebar, DropdownMenu, Separator, Sheet, Tooltip

### Dashboard Architecture (December 2024)
- **Renamed from "Eternal Copilot" to "Eternal Ops Control"**
- Transformed from single-purpose Copilot app to multi-feature dashboard
- Copilot functionality is now one menu item among several (not primary focus)
- Navigation sidebar with collapsible icon mode using shadcn/ui Sidebar components
- Feature-based routing with placeholder views for future features

### CSS Reset Fix
- **Removed** `margin: 0; padding: 0` from the universal selector (`*`)
- This was overriding Tailwind utility classes like `px-14` and `px-12`
- Tailwind's Preflight already handles CSS normalization

### ScrollArea Padding Fix
- Padding must be applied to an **inner wrapper div**, NOT the ScrollArea root
- Radix ScrollArea wraps content in a Viewport that doesn't inherit root padding

### WorkOS AuthKit Authentication (Phase 1)
- **Provider**: WorkOS AuthKit with Microsoft OAuth (SSO)
- **Email Domain Validation**: Only `@eternal.ag` emails allowed (403 for others)
- **Token Verification**: Local JWT validation using JWKS (no per-request API calls)
- **Token Caching**: 45-second TTL cache using `cachetools.TTLCache` for verified tokens
- **JWKS Caching**: 1-hour TTL cache to avoid repeated JWKS fetches
- **User-Scoped Storage**: Conversations stored in Supabase with `user_id` column for scoping
- **Frontend Components**:
  - `AuthGuard.jsx` - Protects routes, shows sign-in screen
  - `Callback.jsx` - Handles OAuth callback at `/callback` route (auto-handled by AuthKitProvider)
  - `UserMenu.jsx` - Displays user info and sign-out button
- **API Client**: `frontend/src/api.js` includes `setTokenGetter()` and automatic 401 retry with token refresh
- **Session Configuration** (configured in WorkOS Dashboard → Authentication):
  - Maximum session length: 7 days (168 hours)
  - Inactivity timeout: 7 days
  - Access token duration: 5-15 minutes (short for security, auto-refreshed by SDK)
  - `refreshBufferInterval: 60` in AuthKitProvider ensures tokens refresh 60s before expiry
- **Session Invalidation Scenarios**:
  1. User explicitly clicks "Sign Out"
  2. Security exceptions (token revocation, password change, account lockout)
  3. Session timeout after 7 days (max length) or inactivity timeout
- **Sign-out Redirect**: Must be configured in WorkOS Dashboard → Redirects → Sign-out redirects

### WorkOS SDK v5.0+ JWT Validation Fix (December 2024)

**Problem**: After integrating WorkOS authentication, all API requests failed with 401 Unauthorized.

**Root Cause**: The code was calling `workos.user_management.get_user_by_access_token(token)` which **does not exist** in WorkOS Python SDK v5.0+. This method was either removed or never existed in this SDK version.

**Error Message**:
```
Token verification failed: 'UserManagement' object has no attribute 'get_user_by_access_token'
```

**Solution**: Replaced the non-existent API call with local JWT validation using JWKS (JSON Web Key Set):

1. **Added dependency**: `python-jose[cryptography]>=3.3.0` to `requirements.txt`

2. **New `get_jwks()` function** in `backend/auth.py`:
   - Fetches JWKS from WorkOS via `workos.user_management.get_jwks_url()`
   - Caches JWKS for 1 hour to avoid repeated fetches
   - Falls back to expired cache if fetch fails

3. **Rewrote `verify_workos_token()` function**:
   - Validates JWT locally using RS256 algorithm
   - Extracts user info from JWT claims (`sub`, `email`, `first_name`, `last_name`)
   - Fallback: if `email` not in JWT, fetches user details from WorkOS API using `get_user(user_id)`

**Key Code Pattern**:
```python
from jose import JWTError, jwt

# Fetch JWKS (cached for 1 hour)
jwks = await get_jwks()

# Validate JWT locally
payload = jwt.decode(
    token,
    jwks,
    algorithms=["RS256"],
    audience=WORKOS_CLIENT_ID,
    options={
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": True,
    }
)

# Extract user info from claims
user_id = payload.get("sub")
email = payload.get("email", "")

# Fallback: fetch from WorkOS API if email not in token
if not email:
    user = workos.user_management.get_user(user_id=user_id)
    email = user.email
```

**Files Modified**:
| File | Change |
|------|--------|
| `requirements.txt` | Added `python-jose[cryptography]>=3.3.0` |
| `backend/auth.py` | Added `get_jwks()`, rewrote `verify_workos_token()` |

**Verification**: After fix, errors changed from 401 (token verification) to 403 (email domain validation), confirming JWT validation works correctly.

### FK Schema Migration (December 16, 2024)

**Migrated from polymorphic `messages` table to FK design across all environments.**

The original schema used a single `messages` table with a `role` column (`user`/`assistant`) and sparse columns for stage data. This was refactored to:
- `messages` table: User messages only (no `role` column)
- `assistant_responses` table: AI responses with 1:1 FK to `messages`

**Migration Script**: `scripts/migrate_to_fk_design.sql`

**Supabase Environments Migrated**:
| Environment | Project ID | Region | Status | Date |
|-------------|------------|--------|--------|------|
| Development | `logtcdlczkdkglxmosyz` | eu-central-1 | ✅ Complete | Dec 16, 2024 |
| Staging | `ggfwstjrjckkecchxjhp` | eu-west-2 | ✅ Complete | Dec 16, 2024 |
| Production | `vthibdgqnxfbjrscxdlf` | eu-west-1 | ✅ Complete | Dec 16, 2024 |

**Production Data Migration Results**:
| Metric | Before | After | Notes |
|--------|--------|-------|-------|
| Conversations | 62 | 62 | Preserved |
| User Messages | 6 | 6 | Preserved |
| Assistant Messages | 9 | — | Deleted from old table |
| Assistant Responses | — | 3 | Migrated to new table |
| Orphaned Data | — | 6 deleted | Assistant messages without preceding user messages |

**Orphaned Data Discovery**: 6 of 9 assistant messages in production had no preceding user message (orphaned data created during early development/testing). These were deleted during migration as they couldn't be linked to a user message.

**Verification Checklist** (all passed on all environments):
- ✅ `messages` table has no `role` column
- ✅ `assistant_responses` table exists with correct columns
- ✅ FK constraint `fk_assistant_responses_user_message` with CASCADE delete
- ✅ UNIQUE constraint on `user_message_id` (enforces 1:1 relationship)
- ✅ Indexes: `idx_assistant_responses_user_message_id`, `idx_assistant_responses_created_at`
- ✅ RLS enabled with 3 policies (SELECT, INSERT, UPDATE)
- ✅ No orphaned records in any table
- ✅ All 17 storage tests pass

### Test Data Cleanup Implementation

**Problem**: Test suite was polluting development database with test conversations (32+ phantom conversations).

**Solution**: Implemented automatic cleanup in `tests/conftest.py`:
```python
@pytest.fixture(autouse=True)
def cleanup_test_data(test_user_id):
    """Cleanup test data after each test to prevent database pollution."""
    yield
    from backend.storage import get_supabase_client
    try:
        supabase = get_supabase_client()
        supabase.table("conversations").delete().eq("user_id", test_user_id).execute()
    except Exception as e:
        print(f"Warning: Failed to cleanup test data for {test_user_id}: {e}")
```

**Test User ID Pattern**: `test_user_{uuid_hex[:8]}` (e.g., `test_user_409b4ae3`)

### Typesense Search Integration (December 2024)

**Full-text search integration using Typesense Cloud for instant conversation/message search.**

**Architecture Overview**:
- **Backend**: `backend/search.py` manages client initialization, collection schemas, and scoped API key generation
- **Frontend**: `frontend/src/components/GlobalSearch.jsx` provides search UI with TypesenseInstantSearchAdapter
- **Security**: Scoped API keys with embedded `user_id` filter prevent cross-user data access

**Collection Schemas**:
| Collection | Searchable Fields | Security |
|------------|-------------------|----------|
| `conversations` | id, title, original_query, created_at, source | `user_id` (facet) |
| `messages` | id, conversation_id, content, created_at, source | `user_id` (facet) |
| `zep_memories` | id, content, memory_type, created_at, source | `user_id` (facet) |

**Environment Variables** (all in root `.env.*` files):
| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TYPESENSE_HOST` | Yes | Typesense Cloud hostname | `y4nhrpvekb3i76owp-1.a1.typesense.net` |
| `TYPESENSE_PORT` | Yes | API port (443 for HTTPS) | `443` |
| `TYPESENSE_PROTOCOL` | Yes | Connection protocol | `https` |
| `TYPESENSE_API_KEY` | Yes | Admin API key (write access) | From Typesense Cloud |
| `TYPESENSE_SEARCH_ONLY_KEY` | Yes | Search-only key (read access) | From Typesense Cloud |

**Migration Commands for New Environments**:
```bash
# 1. Initialize collections (creates schemas)
python -m backend.search init

# 2. Sync existing data from Supabase
python -m backend.search sync

# 3. Verify setup (optional)
python -c "
from backend.search import get_typesense_client
client = get_typesense_client()
for name in ['conversations', 'messages', 'zep_memories']:
    info = client.collections[name].retrieve()
    print(f'{name}: {info[\"num_documents\"]} documents')
"
```

**API Endpoints**:
- `GET /api/search/key` - Returns scoped search key for authenticated user (protected by WorkOS auth)

**Scoped API Key Security**:
```python
# Scoped key embeds user_id filter at Typesense level
scoped_key = client.keys.generate_scoped_search_key(
    search_key=TYPESENSE_SEARCH_ONLY_KEY,
    key_parameters={
        "filter_by": f"user_id:={user_id}",  # Cannot be bypassed by client
        "expires_at": int(time.time()) + 3600,  # 1-hour expiry
    }
)
```

**Real-time Indexing**:
- `create_conversation()` → auto-indexes to `conversations` collection
- `add_user_message()` → auto-indexes to `messages` collection
- `update_conversation_title()` / `update_conversation_queries()` → updates index
- All indexing operations are non-blocking (failures logged, don't block storage)

**Graceful Degradation**:
- If Typesense is unavailable, storage operations continue normally
- Frontend shows "Search not configured" instead of crashing
- All indexing uses try/catch with warning logs

### Typesense Code Review Fixes (December 2024)

**Bug Fixes Applied During Code Review**:

1. **User Switch Cache Invalidation**:
   - **Problem**: Module-level adapter cache retained previous user's scoped key after sign-out/sign-in
   - **Solution**: Added `adapterUserId` tracking and `resetAdapterCache()` function; cache resets when `user?.id` changes
   - **File**: `frontend/src/components/GlobalSearch.jsx`

2. **401 Error Recovery**:
   - **Problem**: Expired/invalid scoped keys returned empty results without refreshing
   - **Solution**: Added error detection in `performSearch()` that resets cache on 401/403 responses
   - **File**: `frontend/src/components/GlobalSearch.jsx`

3. **Typesense SDK v29+ Breaking Change**:
   - **Problem**: `generate_scoped_search_key()` parameter renamed from `parameters` to `key_parameters`
   - **Problem**: Return type changed from `str` to `bytes`
   - **Solution**: Updated parameter name and added `bytes.decode("utf-8")` conversion
   - **File**: `backend/search.py`

4. **Unused Code Cleanup**:
   - Removed unused `useNavigate` import from `GlobalSearch.jsx`
   - Removed unused `user_id` parameter from `_safe_update_conversation_in_index()` in `storage.py`

**Files Modified**:
| File | Changes |
|------|---------|
| `frontend/src/components/GlobalSearch.jsx` | User cache invalidation, 401 handling, removed unused import |
| `backend/search.py` | SDK v29+ compatibility (`key_parameters`, `bytes` conversion) |
| `backend/storage.py` | Removed unused `user_id` parameter from update function |

### Collapsible Navigation Pattern (December 2024)

**Implemented collapsible sub-menu navigation following the shadcn/ui sidebar-07 pattern.**

**Installation**: Added `@radix-ui/react-collapsible` via `npx shadcn@latest add collapsible`

**Components Added**:
- `Collapsible`, `CollapsibleContent`, `CollapsibleTrigger` from `@/components/ui/collapsible`
- `SidebarMenuSub`, `SidebarMenuSubButton`, `SidebarMenuSubItem` from `@/components/ui/sidebar`
- `ChevronRight` icon from `lucide-react` for expand/collapse indicator

**NAV_ITEMS Structure Enhancement**:
```javascript
// Each navigation item now supports optional subItems for collapsible menus
{
  id: "settings",           // Unique identifier
  label: "Settings",        // Display text
  icon: Settings,           // Lucide icon component
  disabled: false,          // Optional: disable the item
  badge: "Soon",            // Optional: badge text (e.g., "Soon", "New")
  isActive: true,           // Optional: default expanded state for collapsible items
  subItems: [               // Optional: array of sub-menu items
    { id: "settings-general", label: "General" },
    { id: "settings-notifications", label: "Notifications" },
  ]
}
```

**NavMain Component Behavior**:
- Automatically detects `subItems` presence to determine rendering pattern
- Items WITH `subItems`: Render as `Collapsible` with `ChevronRight` that rotates 90° when expanded
- Items WITHOUT `subItems`: Render as flat navigation with direct click handling

**Collapsible Items Added**:
| Parent Item | Sub-Items |
|-------------|-----------|
| Workflows | Workflow Builder, Templates, Run History |
| Analytics | Overview, Usage Metrics, Performance, Cost Analysis |
| Reports | Scheduled Reports, Custom Reports, Exports |
| Team | Members, Roles & Permissions, Invitations |
| Security | Audit Log, Active Sessions, API Keys, SSO Configuration |
| Settings | General, Notifications, Integrations, Billing |

**Badge + ChevronRight Overlap Fix**:
- **Problem**: `SidebarMenuBadge` uses absolute positioning (`position: absolute; right: 1rem`), causing overlap with `ChevronRight` icon
- **Solution**: Moved badge INSIDE `SidebarMenuButton` as inline `<span>` element
- **Layout**: Badge uses `ml-auto` to push right, chevron uses `ml-2` (small gap) when badge present, `ml-auto` when no badge
```jsx
// Badge inline with conditional chevron margin
{item.badge && (
  <span className="ml-auto text-xs text-muted-foreground">{item.badge}</span>
)}
<ChevronRight className={`${item.badge ? "ml-2" : "ml-auto"} transition-transform ...`} />
```

**Logo Size Adjustment**:
- Full logo (expanded state): Changed from `h-8` to `h-13` in `LogoSwitcher` component
- Logo mark (collapsed state): Remains at `size-8`

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COPILOT_MODELS` (list of OpenRouter model identifiers) - currently 4 models:
  - `openai/gpt-5.2-pro`
  - `google/gemini-3-pro-preview`
  - `anthropic/claude-opus-4.5`
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

**`auth.py`** (WorkOS Authentication with JWT Validation)
- `AuthenticatedUser` dataclass with `id`, `email`, `name`, `profile_picture_url`
- `get_jwks()`: Fetches and caches JWKS from WorkOS (1-hour TTL) for local JWT validation
- `validate_email_domain()`: Enforces `@eternal.ag` emails (raises 403 for others)
- `verify_workos_token()`: Validates JWT locally using JWKS + RS256, extracts user info from claims, fallback to WorkOS API if email not in token
- `get_current_user()`: FastAPI dependency for protected endpoints (returns `AuthenticatedUser`)
- `get_workos_client()`: Singleton pattern for WorkOS client initialization
- **Important**: Uses `python-jose` for JWT validation, NOT WorkOS SDK's non-existent `get_user_by_access_token()` method

**`storage.py`**
- Supabase-backed conversation storage with FK design
- All functions require `user_id` parameter to scope data by authenticated user
- Tables: `conversations` → `messages` (user only) → `assistant_responses` (1:1 FK)
- User messages stored in `messages` table, AI responses in `assistant_responses`
- `_convert_joined_row_to_messages()`: Handles Supabase's 1:1 nested select (returns dict, not array)
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API
- **Typesense Integration**: Helper functions `_safe_index_conversation()`, `_safe_index_message()`, `_safe_update_conversation_in_index()` for real-time search indexing

**`search.py`** (Typesense Search Integration)
- `get_typesense_client()`: Singleton client initialization with lazy loading
- `is_typesense_configured()`: Checks if all required environment variables are set
- `generate_scoped_search_key()`: Creates user-scoped API keys with embedded `user_id` filter
- `index_conversation()` / `index_message()`: Add documents to Typesense collections
- `init_collections()`: CLI command to create collection schemas
- `sync_from_supabase()`: CLI command to sync existing data to Typesense
- **CLI Interface**: `python -m backend.search [init|sync]`

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
  - `stage1_start` - includes list of models being queried
  - `model_response` - fires for each model as it responds (includes model name, success status, elapsed_ms)
  - `stage1_complete`, `stage2_start`, `stage2_complete`, `stage3_start`, `stage3_complete`
  - `title_complete` - when conversation title is generated
  - `complete` - when all stages finish
  - `error` - on failure
- Metadata returned includes: label_to_model mapping and aggregate_rankings

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Simplified to ~70 lines after dashboard refactor
- Uses React Router Routes for `/callback` and protected main app
- `AuthenticatedApp` component manages feature-based navigation
- Renders `DashboardLayout` with feature components based on `activeFeature` state

**`components/dashboard/DashboardLayout.jsx`**
- Main layout wrapper using SidebarProvider and SidebarInset
- Takes `activeFeature`, `onFeatureChange`, and `children` props

**`components/dashboard/DashboardSidebar.jsx`**
- Navigation sidebar with grouped menu items (Overview, AI Tools, Analytics, Administration)
- Uses shadcn/ui Sidebar components with collapsible icon mode
- NAV_ITEMS array defines sections: Home, Copilot, Analytics, Reports, Workflows, Team, Security, Settings
- Copilot and Home are active; other features show "Soon" badge

**`components/dashboard/DashboardHeader.jsx`**
- Top header with SidebarTrigger and separator

**`components/features/CopilotFeature.jsx`**
- Complete self-contained Copilot with all streaming/state logic (~450 lines)
- All SSE streaming, stage timings, model statuses, error handling
- Uses `ConversationSidebar` and `ChatInterface` components

**`components/features/copilot/ConversationSidebar.jsx`**
- Secondary sidebar for conversation list within Copilot feature
- 256px fixed width with ScrollArea for conversation list

**`components/features/HomeFeature.jsx`**
- Dashboard home page with quick action cards and stats placeholders
- `onNavigate` prop for navigation to features

**`components/features/PlaceholderFeature.jsx`**
- Generic "coming soon" placeholder for future features

**`components/AuthGuard.jsx`**
- Protects routes and shows sign-in screen
- Exports `AuthGuard` component and `useCurrentUser` hook
- Uses shadcn/ui Card and Button components for styling

**`components/Callback.jsx`**
- Handles OAuth redirect from WorkOS
- AuthKitProvider processes callback automatically; component waits for auth completion

**`components/UserMenu.jsx`**
- Displays current user info with avatar/initials in sidebar footer
- Uses shadcn/ui SidebarMenu and DropdownMenu components
- Sign-out option in dropdown menu

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

**`components/ProgressIndicator.jsx`**
- `Stage1Progress`: Shows individual model statuses during Stage 1 collection
  - Displays each model's status: processing (spinner), received (checkmark), failed (X)
  - Shows elapsed time and completion status
- `StageProgress`: Generic stage loading indicator with timer
  - Used for Stage 2 and Stage 3 progress display
  - Color-coded by stage (blue for Stage 2, purple for Stage 3)

**`components/ui/*.jsx`** (shadcn/ui Components)
- `button.jsx` - Button with variants (default, destructive, outline, secondary, ghost, link)
- `card.jsx` - Card, CardHeader, CardContent, CardTitle, CardDescription, CardFooter
- `tabs.jsx` - Tabs, TabsList, TabsTrigger, TabsContent
- `textarea.jsx` - Textarea with focus ring styling
- `scroll-area.jsx` - ScrollArea, ScrollBar (Radix-based)

**`lib/utils.js`**
- `cn()` function - merges Tailwind classes using `clsx` and `tailwind-merge`

**`api.js`**
- API client with WorkOS authentication support
- `setTokenGetter()` - receives token getter from WorkOS AuthKit's useAuth hook
- `getAuthHeaders()` - gets Authorization Bearer headers with optional force refresh
- `fetchWithRetry()` - makes fetch requests with automatic 401 retry after token refresh
- All API methods use `fetchWithRetry()` for consistent authentication
- SSE streaming handles 401 with token refresh before retry

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

### Environment Variable Organization

This project uses **two separate `.env` files** following the standard Vite convention:

| File | Purpose | Variable Access |
|------|---------|-----------------|
| `.env` (project root) | Backend secrets | `os.getenv()` via `python-dotenv` |
| `frontend/.env` | Frontend config | `import.meta.env.VITE_*` |

**Why separate files?**
- **Vite's `VITE_` prefix requirement**: Vite only exposes environment variables prefixed with `VITE_` to client-side code for security
- **Different runtimes**: Backend runs in Python, frontend runs in browser
- **Security boundary**: `OPENROUTER_API_KEY` and `WORKOS_API_KEY` must never be exposed to browser

**Variables by location:**

```
┌─────────────────────────────────────────────────────────────┐
│                    .env (ROOT - SECRET)                      │
│  - OPENROUTER_API_KEY    ← Never exposed to browser          │
│  - WORKOS_API_KEY        ← Never exposed to browser          │
│  - WORKOS_CLIENT_ID      ← Duplicated in frontend            │
│  - EMPLOYEE_EMAIL_DOMAIN                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               frontend/.env (PUBLIC)                         │
│  - VITE_WORKOS_CLIENT_ID     ← Same value as WORKOS_CLIENT_ID│
│  - VITE_WORKOS_REDIRECT_URI  ← OAuth callback URL            │
│  - VITE_API_BASE_URL         ← Optional API override         │
└─────────────────────────────────────────────────────────────┘
```

**Critical duplication:** `WORKOS_CLIENT_ID` must be set in BOTH files with the same value:
- Backend: `WORKOS_CLIENT_ID=client_xxxxx`
- Frontend: `VITE_WORKOS_CLIENT_ID=client_xxxxx`

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
11. **WorkOS Client ID Must Be in Both .env Files**: `WORKOS_CLIENT_ID` (backend) and `VITE_WORKOS_CLIENT_ID` (frontend) must have the same value. If only one is set, either backend token validation or frontend OAuth will fail.
12. **Authentication Configuration Error Screen**: If frontend shows "Configuration Error", ensure `VITE_WORKOS_CLIENT_ID` is set in `frontend/.env`. If backend returns 500, ensure `WORKOS_API_KEY` and `WORKOS_CLIENT_ID` are set in root `.env`.
13. **Supabase 1:1 Nested Select Returns Dict, Not Array**: When querying `messages` with nested `assistant_responses` using a UNIQUE FK, Supabase returns a single dict instead of an array. The `_convert_joined_row_to_messages()` function handles both cases:
```python
# Handle both dict (1:1) and array (1:N) cases
response = None
if isinstance(response_data, dict) and response_data:
    response = response_data  # 1:1 returns single dict
elif isinstance(response_data, list) and len(response_data) > 0:
    response = response_data[0]  # 1:N returns array
```
14. **WorkOS SDK v5.0+ Breaking Change**: The `get_user_by_access_token()` method **does not exist** in WorkOS Python SDK v5.0+. Use local JWT validation with JWKS instead. Access tokens are JWTs that should be validated locally using the RS256 algorithm and the JWKS endpoint from `workos.user_management.get_jwks_url()`. See the "WorkOS SDK v5.0+ JWT Validation Fix" section above for implementation details.
15. **SidebarMenuBadge + ChevronRight Overlap**: When using `SidebarMenuBadge` (absolute positioned) alongside `ChevronRight` icon in collapsible menu items, they overlap. **Solution**: Move badge inside `SidebarMenuButton` as an inline `<span>` with `ml-auto`, then use conditional margin on chevron: `ml-2` when badge present, `ml-auto` when no badge.
16. **Typesense SDK v29+ Breaking Change**: The `generate_scoped_search_key()` function has two breaking changes in SDK v29+: (1) parameter renamed from `parameters` to `key_parameters`, (2) return type changed from `str` to `bytes`. **Solution**: Use `key_parameters=` and call `.decode("utf-8")` on the result.
17. **Typesense Search Key User Switch**: Module-level adapter cache (`typesenseAdapter`) retains previous user's scoped key after sign-out/sign-in, causing empty results. **Solution**: Track `adapterUserId` and reset cache when `user?.id` changes via `useEffect`.
18. **"Search not configured" After Auth**: If GlobalSearch's `useEffect` runs before authentication completes, API calls return 401 and the component shows "Search not configured". **Solution**: Use `useAuth()` hook and gate configuration check on `!isAuthLoading && user`.
19. **Typesense Deprecation Warning**: The Typesense SDK v29 logs `AnalyticsRulesV1 is deprecated on v30+. Use client.analytics instead.` This is informational only and doesn't affect functionality.

## Future Enhancement Ideas

- Configurable copilot models/chairman via UI instead of config file
- ~~Streaming responses instead of batch loading~~ ✅ Implemented via SSE
- ~~Resizable sidebar~~ ✅ Implemented with localStorage persistence
- ~~shadcn/ui component migration~~ ✅ Completed with zinc color palette
- ~~WorkOS AuthKit authentication~~ ✅ Implemented Phase 1 (Microsoft SSO, email domain validation)
- Export conversations to markdown/PDF
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models (o1, etc.) with special handling
- Dark mode toggle (theme infrastructure is in place via CSS variables)
- Keyboard shortcuts for common actions (new conversation, toggle sidebar)
- ~~Search/filter conversations in sidebar~~ ✅ Implemented via Typesense global search
- Multi-tenant support (Phase 2+: organization-based conversation sharing)
- RBAC for team permissions

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
