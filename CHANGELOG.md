# Changelog

All notable changes to the Eternal Copilot project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Dark mode toggle (planned)
- Keyboard shortcuts for common actions (planned)
- Search/filter conversations in sidebar (planned)
- Export conversations to markdown/PDF (planned)

---

## [1.3.0] - 2025-12-16

### Added
- **WorkOS AuthKit Authentication**: Microsoft SSO with @eternal.ag email domain validation
  - JWT validation using JWKS (local validation, no per-request API calls)
  - Token caching with 45-second TTL for verified tokens
  - JWKS caching with 1-hour TTL
  - AuthGuard, Callback, and UserMenu components
- **Supabase Storage Backend**: Migrated from JSON files to Supabase PostgreSQL
  - FK schema design: `conversations` → `messages` → `assistant_responses`
  - Row Level Security (RLS) policies for user data isolation
  - Migrated all environments (dev, staging, production)
- **Test Data Cleanup**: Automatic cleanup in pytest fixtures to prevent database pollution
- **Progress Indicators**: Real-time model status display during Stage 1

### Changed
- Storage backend from JSON files to Supabase
- Authentication from none to WorkOS AuthKit with Microsoft SSO

### Fixed
- **WorkOS SDK v5.0+ JWT Validation**: Replaced non-existent `get_user_by_access_token()` with local JWT validation using JWKS

### Technical Details
- JWT validation uses `python-jose` library with RS256 algorithm
- Supabase tables: `conversations`, `messages`, `assistant_responses`, `conversation_shares`
- Test user ID pattern: `test_user_{uuid_hex[:8]}`

---


## [1.2.0] - 2025-12-14

### Added
- **Resizable Sidebar**: Drag the right edge to resize the sidebar between 240px and 480px
- **localStorage Persistence**: Sidebar width automatically saves and restores on page reload
- **Visual Resize Grip**: Grip indicator appears on hover over the sidebar edge

### Changed
- **Tailwind CSS v4 Migration**: Migrated from Tailwind v3 to v4 with CSS-first configuration
  - Removed `tailwind.config.js` - configuration now done via `@theme` directive in CSS
  - Updated import syntax from `@tailwind` directives to `@import "tailwindcss"`
  - Changed PostCSS plugin from `tailwindcss` to `@tailwindcss/postcss`
- **shadcn/ui Component Integration**: Migrated all UI components to shadcn/ui library
  - Button, Card, Tabs, Textarea, ScrollArea components
  - Uses zinc color palette (neutral grays) for consistent design
  - All components use Radix UI primitives for accessibility

### Fixed
- **CSS Reset Override Bug**: Removed `padding: 0; margin: 0` from universal selector (`*`) that was overriding Tailwind utility classes
- **ScrollArea Padding Issue**: Fixed padding not being applied to ScrollArea content by moving padding to inner wrapper div
- **Tailwind Utility Classes**: All padding classes (`px-14`, `px-12`, etc.) now work correctly

### Technical Details
- Sidebar padding: `px-14` for header, `px-12` for conversation list
- ScrollArea requires padding on inner content wrapper, not on the component root
- Tailwind's Preflight handles CSS normalization, so custom resets are unnecessary

---

## [1.1.0] - 2024-12-13

### Added
- **Server-Sent Events (SSE) Streaming**: Real-time progressive updates for copilot deliberation
  - See each stage complete as it happens (Stage 1 → Stage 2 → Stage 3)
  - Loading indicators show current processing stage
  - New API endpoint: `POST /api/conversations/{id}/message/stream`
- **Prompt Improvement Feature**: "✨ Improve Prompt" button to enhance user queries
  - Uses fast LLM to rewrite prompts for clarity
  - Shows original prompt for comparison
  - "↩ Undo" button to revert changes

### Changed
- Moved from batch API responses to streaming for better UX
- Updated frontend to handle SSE events with progressive UI updates

---

## [1.0.0] - 2024-12-12

### Added
- **3-Stage Copilot Deliberation System**:
  - Stage 1: Parallel queries to all copilot LLMs
  - Stage 2: Anonymous peer review and ranking
  - Stage 3: Chairman synthesis of final answer
- **Anonymized Peer Review**: Models evaluate responses without knowing which model generated them
- **Tab-based UI**: View individual model responses and evaluations in tabs
- **Aggregate Rankings**: Combined ranking scores across all peer evaluations
- **Conversation History**: JSON-based storage with conversation persistence
- **React + Vite Frontend**: Modern React with Vite for fast development
- **FastAPI Backend**: Async Python backend with OpenRouter API integration

### Technical Stack
- Backend: FastAPI, Python 3.10+, async httpx
- Frontend: React, Vite, react-markdown
- API: OpenRouter for multi-model access
- Storage: JSON files in `data/conversations/`

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 1.3.0 | 2025-12-16 | WorkOS auth, Supabase storage, progress indicators |
| 1.2.0 | 2025-12-14 | Tailwind v4, shadcn/ui, resizable sidebar |
| 1.1.0 | 2024-12-13 | SSE streaming, prompt improvement |
| 1.0.0 | 2024-12-12 | Initial release, 3-stage copilot system |

