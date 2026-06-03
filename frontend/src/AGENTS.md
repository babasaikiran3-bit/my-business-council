<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# src

## Purpose
Application source for the Parenting Roundtable React 19 + Vite frontend. This directory holds the entry point (`main.jsx`), the top-level routing shell (`App.jsx`), the backend API client (`api.js`), and the global stylesheets (`index.css`, `App.css`). It wires together the router, the app-wide `AppContext` provider, the route-level `pages/`, and the reusable `components/`. The UI is a single-question-per-conversation parenting advisor: a page collects a question plus a child profile, streams the 4-stage council pipeline (Stage 0 grounding → Stage 1 panel → Stage 2 ranking → Stage 3 chairman) over SSE from the backend, and renders each stage as it arrives. The `assets/` directory (only `react.svg`) is intentionally undocumented.

## Key Files
| File | Description |
| --- | --- |
| `main.jsx` | Vite entry. Mounts `<App>` under `StrictMode` → `BrowserRouter` → `AppProvider`, and imports `index.css`. The provider order matters: routing and context must wrap `App`. |
| `App.jsx` | Top-level route table (react-router-dom v7 `Routes`/`Route`). `/` shows `Landing` for new visitors, else redirects to `/ask` via the `hasOnboarded` flag from `useApp()`. `/start` is the onboarding flow; `/ask`, `/ask/:id`, `/settings` render inside the shared `AppLayout` shell; `*` redirects to `/`. |
| `api.js` | Backend API client. Base URL is `import.meta.env.VITE_API_BASE \|\| 'http://localhost:8001'`. Exports a single `api` object: conversation CRUD, the SSE streaming `sendMessageStream`, auth/providers/me/login/logout, child-profile CRUD, and consent endpoints. All requests use `credentials: 'include'` (cookie sessions). |
| `index.css` | Global design tokens + base styles. Defines the "Warm Clinic" CSS custom properties (rose brand, sage trust, single reserved `--alert` red, warm neutrals, radii, shadows, motion easing), imports the Pretendard webfont, and ships the global `.markdown-content` and `.blocked-link` rules. |
| `App.css` | Layout/chrome styles for the app shell: `.app` flex container, `.main-col`, the dismissible `.app-banner`, the `.mobile-topbar`, `.icon-button`, and the responsive sidebar-as-drawer behavior (`@media (max-width: 899px)`). |

## Subdirectories
| Directory | Purpose |
| --- | --- |
| `components/` | Reusable UI: app shell/layout, the stage renderers (Stage0–Stage3), safe-markdown link rendering, and shared widgets (see `components/AGENTS.md`). |
| `context/` | `AppContext` provider/hook holding app-wide state — auth, child profiles, active child, conversation list, onboarding/free-ask flags, and the global banner (see `context/AGENTS.md`). |
| `lib/` | Framework-agnostic helpers used across pages/components (see `lib/AGENTS.md`). |
| `pages/` | Route-level screens: `Landing`, `Start`, `Ask`, `Settings` (see `pages/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- **Backend base URL/port**: `api.js` targets `http://localhost:8001` by default (the backend runs on 8001, NOT 8000). For production builds set `VITE_API_BASE` at build time. Do not hardcode the host elsewhere — import `api` from `./api`.
- **SSE consumption is hand-rolled in `sendMessageStream`**: it `fetch`es `.../message/stream`, reads `response.body.getReader()`, decodes with `TextDecoder({stream:true})`, and buffers across chunks (an event split over two TCP frames must not be dropped — the trailing partial line is held until its `\n`). Each `data: ` line is JSON-parsed and dispatched as `onEvent(event.type, event)`. A `STREAM_TIMEOUT_MS` (180s) `AbortController` resets on every chunk; on abort/network error it emits a synthetic `{type:'error', message}` (Korean-language copy). If you add a new stage/event type, the parsing here stays the same — only the page's `onEvent` reducer changes.
- **CSRF + cookies are load-bearing**: every state-changing request sends `X-Requested-With: parenting-roundtable` (`CSRF_HEADERS`) and `credentials: 'include'`. Removing either header or the credentials flag breaks auth and the backend's CSRF check. JSON bodies use `JSON_HEADERS` (= `Content-Type` + CSRF). Read-only GETs still need `credentials: 'include'` for session cookies.
- **Routing invariants**: `App.jsx` gates `/` on `hasOnboarded` (from `useApp()`, persisted in `localStorage` as `pr_onboarded`). The app routes (`/ask`, `/ask/:id`, `/settings`) are nested under a single `<Route element={<AppLayout />}>` — add new in-shell screens as children there, not as siblings. `*` must keep redirecting to `/`.
- **Provider order in `main.jsx`**: `BrowserRouter` must wrap `AppProvider` must wrap `App`. `useApp()` returns `null` if a consumer renders outside `AppProvider`.
- **`age_days` vs age label**: the streaming send takes a typed `ageDays` (number|null) plus optional `opts.childProfileId` and `opts.idempotencyKey`; this is the real age signal driving backend safety triage (not a parsed prose label).
- **Styling**: never introduce new hex colors — use the tokens in `index.css` (`var(--rose-*)`, `var(--sage-*)`, `var(--alert)`, `var(--ink*)`, etc.). Red (`--alert`) is reserved for emergencies only. Model-authored bodies must keep the `.markdown-content` wrapper, and unverified links render as `.blocked-link`.

### Testing Requirements
Run from `frontend/`:
```bash
npm run build      # production build must succeed
npm run lint       # eslint must pass
npm run dev        # local dev server on :5173 (expects backend on :8001)
```
Manual smoke: an Ask flow must stream Stage 0 → 3 in order and render the emergency banner for a newborn-fever question.

### Common Patterns
- Single shared `api` object (named export from `api.js`); no per-request client construction.
- Network failures degrade gracefully: read APIs (`getMe`, `getAuthProviders`, `listChildren`, `getConsents`) return `{}`/`[]`/`null` on non-OK rather than throwing; write APIs throw. The context layer catches and surfaces a dismissible banner.
- Korean-language user-facing strings (this is a Korean-market product).
- CSS uses `100dvh`, `env(safe-area-inset-*)`, and a 899px breakpoint to collapse the sidebar into a drawer.

## Dependencies

### Internal
- `./context/AppContext.jsx` — `AppProvider` (wraps the tree) and `useApp()` (consumed by `App.jsx` for `hasOnboarded`).
- `./components/AppLayout` — the signed-in shell (sidebar + bottom tabs) wrapping the app routes.
- `./pages/*` — `Landing`, `Start`, `Ask`, `Settings` route components.
- `./api` — imported by `AppContext` and the pages for all backend calls.

### External
- `react` / `react-dom` (v19) — `StrictMode`, `createRoot`.
- `react-router-dom` (v7) — `BrowserRouter`, `Routes`, `Route`, `Navigate`.
- Pretendard webfont via CDN `@import` in `index.css`.
- Browser `fetch` + `AbortController` + `TextDecoder` for SSE streaming (no SSE library).

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
