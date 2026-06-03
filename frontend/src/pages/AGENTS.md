<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# pages

## Purpose
Route-level page components for the Parenting Roundtable SPA. Each file is a top-level screen mounted by the router in `frontend/src/App.jsx` (react-router-dom 7). These pages own per-screen UI and local flow state, but pull shared state (auth, children, conversations, banner, onboarding flag) from `AppContext` via the `useApp()` hook. The user journey runs Landing (`/`) → Start onboarding (`/start`) → Ask Q&A (`/ask`), with Settings (`/settings`) for profile/account management. Most pages pair with a sibling `.css` file (Ask is the exception — it renders `ChatInterface`, which carries its own styles). All copy is Korean.

## Key Files
| File | Description |
| --- | --- |
| `Landing.jsx` | Marketing/entry page at `/`. Static hero, 3-step "how it works", trust strip, `ExampleCard` demo, limitations notice, footer. All CTAs are `<Link to="/start">`. No state, no data fetching. Pairs with `Landing.css`. |
| `Start.jsx` | 4-step onboarding wizard (`welcome → child → consent → login`) driven by a `step` index. Creates a child profile (`api.createChild` + `toBirthdate`), records consents (`api.recordConsents(REQUIRED_CONSENTS)`), offers social login, then calls `completeOnboarding()` and navigates to `/ask`. Pairs with `Start.css`. |
| `Ask.jsx` | The main Q&A flow at `/ask` and `/ask/:id`. Owns per-conversation streaming state and the `handleStreamEvent` SSE reducer that drives the council stages (stage0–stage3 + emergency). Renders `ChatInterface` with a `LoginWall` lock node. No paired `.css` (styles live in `ChatInterface`). |
| `Settings.jsx` | Settings page at `/settings`. Manages child profiles (add/edit/delete/select via internal `ChildForm`), account (login/logout), consent status display, and "delete all conversations". Pairs with `Settings.css`. |

## For AI Agents

### Working In This Directory
- **Router wiring (`App.jsx`)**: `Landing` → `/` (only when `!hasOnboarded`; otherwise redirects to `/ask`). `Start` → `/start`. `Ask` → `/ask` and `/ask/:id`, and `Settings` → `/settings` both render **inside** the `<AppLayout />` route (they get the app shell/sidebar); Landing and Start render standalone. Unknown paths redirect to `/`.
- **Shared vs local state**: never lift conversation/streaming state into context — `Ask` deliberately keeps `currentConversation`, `isLoading`, `lastSend` local. Pull `activeChild`, `isAuthenticated`, `freeAskUsed`, `setBanner`, etc. from `useApp()`.
- **Ask streaming is load-bearing.** `handleStreamEvent` maps SSE event types to mutations on the *last* message: `stage0_start/complete`, `stage1_*`, `stage2_complete` (also sets `m.metadata`), `stage3_*`, `emergency`, `title_complete`, `complete`, `error`. The optimistic assistant message in `streamAssistant` seeds `loading: { stage0..stage3 }` and null stage fields — keep that shape in sync with the reducer or stages will not render. The order matters: stage0 (grounding) fires before stage1.
- **`ownedIdRef` invariant**: when a conversation is created locally, `ownedIdRef.current` is set to its id *before* `navigate()` so the load effect (`useEffect` on `routeId`) skips re-fetching and clobbering in-memory streaming state. Don't remove this guard.
- **Anonymous free-ask gate**: `composerLocked = !isAuthenticated && freeAskUsed && !routeId`. On `complete`, anonymous users call `markFreeAskUsed()`. The locked composer renders `<LoginWall />` via `ChatInterface`'s `lockedNode` prop.
- **Age handling**: birthdates use `toBirthdate(year, month)` / `fromBirthdate(birthdate)` from `../lib/age`; Ask passes `activeChild?.age_days` (not a label) to `api.sendMessageStream`. Year/month selects are built from `NOW_YEAR` (19 years back) and months 1–12 in both `Start` and `Settings`.
- **Consents**: `REQUIRED_CONSENTS = ['sensitive_health', 'child_data_by_guardian', 'cross_border_transfer']` in `Start`; `api.recordConsents` failure is intentionally non-blocking for the pilot. Don't make it block onboarding.
- **Social login**: rendered conditionally on `enabledProviders` (`kakao` / `naver`) from context; links go to `api.loginUrl(provider)`. When empty, show the demo-note fallback (both Start and Settings do this).
- **Icons**: import named SVG components from `../components/Icons` (e.g. `ArrowRight`, `ShieldCheck`, `KakaoGlyph`); do not inline SVG or pull in an icon library.
- All user-facing strings are Korean — match the existing tone (warm, reassuring) and keep the `버전 0.1.0 · 파일럿` versioning convention.

### Testing Requirements
- Build: `cd frontend && npm run build`
- Lint: `cd frontend && npm run lint`
- Manual: from the repo root run the backend (`uv run python -m backend.main`, port 8001) and `cd frontend && npm run dev` (port 5173). Walk `/` → `/start` (create child, consent, skip login) → `/ask` (send a question, watch stage0→stage3 stream) → `/settings`. Spot-check the newborn-fever case still surfaces the emergency banner end-to-end.

### Common Patterns
- Default-exported function components; no prop-types. Local UI state via `useState`; side effects via `useEffect` with a `cancelled` flag for fetches.
- Multi-step screens use a `STEPS` array + numeric `step` index and conditionally render one block (`stepName === '...'`). `Settings` factors its repeated add/edit form into a local `ChildForm` component.
- Navigation via `useNavigate()` (often `{ replace: true }`); links via `<Link>`. Route params via `useParams()`.
- Async actions toggle a local `busy`/`isLoading` flag and disable the primary button; errors set a local `error` string or call `setBanner(...)` from context.

## Dependencies

### Internal
- `../api` (`api`) — backend client: `createChild`, `updateChild`, `deleteChild`, `createConversation`, `getConversation`, `sendMessageStream`, `recordConsents`, `getConsents`, `deleteConversation`, `loginUrl`.
- `../context/AppContext` (`useApp`) — auth/user, `childList`/`activeChild(Id)`, `conversations`, `enabledProviders`, `completeOnboarding`, `freeAskUsed`/`markFreeAskUsed`, `setBanner`, refreshers.
- `../lib/age` — `toBirthdate`, `fromBirthdate`, `ageLabel`, `childDisplayName`.
- `../components/*` — `ChatInterface`, `LoginWall` (Ask); `ExampleCard`, `Icons` (Landing); `Icons` (Start, Settings).
- Sibling `*.css` files (Landing/Start/Settings).

### External
- `react` (hooks: `useState`, `useEffect`, `useCallback`, `useRef`).
- `react-router-dom` 7 (`Link`, `useNavigate`, `useParams`).

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
