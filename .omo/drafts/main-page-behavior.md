# Draft: Main Page Behavior

## Requirements (confirmed)
- User asked: "Plan how here(main) page should work in this app"
- Interpret "here(main) page" as the app's primary home route/surface: `/ask`, because `frontend/src/App.jsx` routes `/` to `Landing` for new visitors and redirects onboarded users to `/ask`.

## Technical Decisions
- Preserve `/` as the unauthenticated marketing/entry route and onboarding gate.
- Treat `/ask` as the in-app main page: it should be a task-focused question home, not a marketing landing page.
- Keep conversation streaming state local to `frontend/src/pages/Ask.jsx`; do not lift it into `AppContext`.
- Keep app shell navigation in `frontend/src/components/AppLayout.jsx`, `Sidebar.jsx`, and `BottomTabBar.jsx`.
- Main-page implementation should focus on `frontend/src/pages/Ask.jsx` and `frontend/src/components/ChatInterface.jsx`.

## Research Findings
- `frontend/src/App.jsx`: `/` shows `Landing` when `!hasOnboarded`, otherwise redirects to `/ask`; `/ask` and `/settings` render inside `AppLayout`.
- `frontend/src/pages/Ask.jsx`: owns conversation load/create, SSE reducer, anonymous free-question lock, retry, and new-question navigation.
- `frontend/src/components/ChatInterface.jsx`: renders welcome/home empty state, child chip, category pills, examples, composer, thread output, early sources, progress, Stage3, evidence details, retry, and next-question CTA.
- `frontend/src/context/AppContext.jsx`: stores auth, child profiles, active child, conversation list, `hasOnboarded`, and `freeAskUsed` via localStorage.
- `frontend/src/components/Sidebar.jsx` and `BottomTabBar.jsx`: provide desktop history/settings/new-question nav and mobile home/history/settings nav.

## Open Questions
- None blocking. Default assumption: the user wants a planning artifact for how the current main page should work, not code changes in this turn.

## Scope Boundaries
- INCLUDE: route behavior, user states, main-page content model, conversation lifecycle, onboarding/free-use states, navigation, error states, QA scenarios, and implementation tasks.
- EXCLUDE: backend council logic changes, model prompt changes, production deployment changes, new dependencies, and replacing the existing landing page unless explicitly requested.
