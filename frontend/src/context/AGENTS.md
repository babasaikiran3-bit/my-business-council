<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# context

## Purpose
React Context that holds the app-wide state shared across routes for the Parenting Roundtable frontend: authentication/session, the user's child profiles plus the currently-active child, the conversation list, and the onboarding / free-question flags, plus a global retry banner. It deliberately does **not** hold chat-streaming state — that stays local to the Ask page — so this layer only carries what multiple screens need. A single `AppProvider` wraps the whole router tree and a `useApp()` hook exposes the value to pages and components.

## Key Files
| File | Description |
| --- | --- |
| `AppContext.jsx` | Defines `AppContext`, the `AppProvider` component (all global state + async refreshers), and the `useApp()` consumer hook. Bootstraps auth/children/conversations on mount and mirrors a few flags to `localStorage`. |

## For AI Agents

### Working In This Directory
- **Provider is mounted once** in `../main.jsx`, wrapping `<App/>` inside `<BrowserRouter>`. Any new global state goes in the `value` object here, not in a second provider.
- **`useApp()` returns `null` outside the provider** (created via `createContext(null)`), so a component rendered outside `AppProvider` will crash on property access. Don't call it from `main.jsx` siblings of the provider.
- **Three `localStorage` keys are the source of truth for persisted flags**, defined in the `LS` map: `pr_onboarded`, `pr_active_child`, `pr_free_ask_used`. Keep reads/writes going through the existing setters (`setActiveChildId`, `completeOnboarding`, `markFreeAskUsed`, `clearFreeAsk`) so state and storage never diverge. If you rename a key, migrate existing values — users already have these stored.
- **Active-child reconciliation lives in `refreshChildren`**: it preserves the current `activeChildId` only if it still exists in the fetched list, else falls back to `list[0]?.id ?? null` and updates `localStorage` accordingly. Preserve this functional-updater pattern (`setActiveChildIdState((cur) => ...)`) — it avoids a stale-closure bug.
- **All three refreshers swallow errors by design** (`refreshAuth`/`refreshChildren` silently, `refreshConversations` sets a Korean retry `banner`). Auth is best-effort so anonymous users still work. Don't make these throw.
- **User-facing strings are Korean** (e.g. the banner `'대화 목록을 불러오지 못했어요.'`). Match that language for any new copy added here.
- **Derived values are computed in render**, not stored: `activeChild` (lookup by id), `isAuthenticated` (`!!user?.authenticated`), `enabledProviders` (provider keys whose value is truthy). Add new derived data the same way rather than adding redundant state.
- **All callbacks are `useCallback`-wrapped** and the mount `useEffect` depends on the three refreshers — keep new refreshers memoized so the effect doesn't loop.

### Testing Requirements
From `frontend/`:
- `npm run build` — must compile (Vite, React 19).
- `npm run lint` — ESLint; watch for missing/extra hook deps on any new `useCallback`/`useEffect`.
- Manual: with the backend on port 8001, load the app and confirm auth state, the active-child chip, and the conversation list all populate on first render, and that an active child persists across reload.

### Common Patterns
- **Consumer pattern**: `const { ... } = useApp();` — used by `App.jsx`, `components/AppLayout.jsx`, `components/LoginWall.jsx`, and pages `Start.jsx`, `Ask.jsx`, `Settings.jsx`.
- **State + storage pairing**: lazy-init from `localStorage` (e.g. `useState(() => localStorage.getItem(...) === 'true')`), then write through a dedicated `useCallback` setter that updates both React state and storage.
- **Best-effort async**: every network refresher is `try/catch` with graceful degradation; failures never break the UI.
- **`banner` retry contract**: `setBanner({ text, retry })` where `retry` is a callable the UI can invoke to re-attempt the failed load.

## Dependencies

### Internal
- `../api` (`api` object) — `getMe`, `getAuthProviders`, `listChildren`, `listConversations`, `logout` back the refreshers and `logout`.
- `../main.jsx` — mounts `AppProvider` around the app.
- Consumers: `../App.jsx`, `../components/AppLayout.jsx`, `../components/LoginWall.jsx`, `../pages/Start.jsx`, `../pages/Ask.jsx`, `../pages/Settings.jsx`.

### External
- `react` — `createContext`, `useContext`, `useState`, `useEffect`, `useCallback`.
- Browser `localStorage` (Web Storage API) for persisted flags.

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
