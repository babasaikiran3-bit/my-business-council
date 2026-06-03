# Root Main Hero Plan

## TL;DR
> Summary:      Make `/` the in-product asking surface by rendering `Ask` inside `AppLayout`, while preserving `/start`, `/ask`, `/ask/:id`, and `/settings`. Keep the hero compact, safety-forward, and directly usable: category chips, child context, composer, streaming answer, free-question lock, and retry all remain on the same operational surface.
> Deliverables:
> - Root route mapped to the product hero shell.
> - Main hero copy/proof points/category content factored for testability.
> - Hero composer styling and responsive screenshots.
> - Static route/hero guard plus lint/build/browser evidence.
> Effort:       Short
> Risk:         Medium - root route semantics changed, so onboarding, free-question lock, and conversation streaming must be verified together.

## Scope
### Must have
- `/` renders `frontend/src/pages/Ask.jsx` inside `frontend/src/components/AppLayout.jsx`.
- `/ask`, `/ask/:id`, `/settings`, and `/start` continue to work.
- The empty product surface shows Korean hero copy, trust/proof points, category examples, child context, and an enabled composer once input is entered.
- Sending from `/` creates a conversation, navigates to `/ask/:id`, appends user and assistant messages, consumes mocked or live SSE events, and shows the Stage 3 final answer.
- Anonymous users still lock the empty composer after one completed free question; existing conversation URLs stay readable.
- Context hook/provider split keeps React Fast Refresh lint clean without creating a second context instance.
- Verification evidence is captured under `.omo/evidence/`.

### Must NOT have (guardrails, anti-slop, scope boundaries)
- Must not add new runtime dependencies.
- Must not touch backend council logic, safety prompts, trusted-source matching, or SSE parsing unless a real API mismatch is proven.
- Must not relax safe markdown link matching in `Stage0`, `Stage1`, or `Stage3`.
- Must not parse child age from display text; `Ask` must keep sending typed `activeChild?.age_days ?? null` and `childProfileId`.
- Must not turn red styling into generic decoration; emergency red remains reserved for emergency states.
- Must not remove `/start` or the anonymous one-free-question/login-wall behavior.

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: tests-after + static Node guard (`frontend/scripts/check-main-hero.mjs`) + ESLint + Vite production build + Playwright browser smoke.
- QA policy: every task has agent-executed scenarios.
- Evidence: `.omo/evidence/task-<N>-<slug>.<ext>`

## Execution strategy
### Parallel execution waves
> Target 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks to maximize parallelism.

Wave 1 (no dependencies):
- Task 1: Root route contract and static guard.
- Task 2: Context hook/provider split.
- Task 3: Main hero content constants.

Wave 2 (after Wave 1):
- Task 4: Hero welcome composition and responsive visual styling depends [1, 3].
- Task 5: Composer/category/child interaction behavior depends [2, 3].
- Task 6: Conversation streaming/free-question/retry behavior under root depends [1, 2].

Wave 3 (after Wave 2):
- Task 7: End-to-end browser QA and evidence capture depends [4, 5, 6].

Critical path: Task 1 -> Task 4 -> Task 7

### Dependency matrix
| Task | Depends on | Blocks | Can parallelize with |
|------|------------|--------|----------------------|
| 1    | none       | 4, 6, 7 | 2, 3 |
| 2    | none       | 5, 6, 7 | 1, 3 |
| 3    | none       | 4, 5, 7 | 1, 2 |
| 4    | 1, 3       | 7 | 5, 6 |
| 5    | 2, 3       | 7 | 4, 6 |
| 6    | 1, 2       | 7 | 4, 5 |
| 7    | 4, 5, 6    | none | none |

## Todos
> Implementation + Test = ONE task. Never separate.
> Every task MUST have: References + Acceptance Criteria + QA Scenarios + Commit.

- [ ] 1. Root route contract and static guard

  What to do: Route `/` to `Ask` inside `AppLayout`, keep `/ask`, `/ask/:id`, `/settings`, `/start`, and wildcard-to-root behavior, then add or update a static guard that fails if `/` returns to onboarding-gated landing behavior.
  Must NOT do: Do not remove `/start`; do not make `/ask/:id` standalone outside `AppLayout`; do not reintroduce `hasOnboarded` gating on `/`.

  Parallelization: Can parallel: YES | Wave 1 | Blocks: [4, 6, 7] | Blocked by: []

  References (executor has NO interview context - be exhaustive):
  - Pattern:  `frontend/src/App.jsx:10` - route table entry point.
  - Pattern:  `frontend/src/App.jsx:13` - `AppLayout` wraps app routes.
  - Pattern:  `frontend/src/App.jsx:14` - current `/` -> `Ask` root hero route.
  - Test:     `frontend/scripts/check-main-hero.mjs:8` - static route assertion for `/` inside `AppLayout`.
  - External: `https://reactrouter.com/7.9.4/api/hooks/useNavigate` - React Router navigation API used by downstream route flows.

  Acceptance criteria (agent-executable only):
  - [ ] `cd frontend && npm run test:main-hero` exits 0.
  - [ ] `node -e "const s=require('fs').readFileSync('frontend/src/App.jsx','utf8'); if(!s.includes('<Route path=\"/\" element={<Ask />} />')) process.exit(1)"` exits 0.

  QA scenarios (MANDATORY - task incomplete without these):
  > Name the exact tool AND its exact invocation - not "verify it works". Browser use: use Chrome to drive the page; if Chrome is not available, download and use agent-browser (https://github.com/vercel-labs/agent-browser). Computer use: OS-level GUI automation for a non-browser desktop app.
  ```
  Scenario: root renders product hero
    Tool:     bash
    Steps:    cd frontend && npm run test:main-hero
    Expected: command exits 0 and the static assertion says `/` renders Ask inside AppLayout.
    Evidence: .omo/evidence/task-1-root-route.txt

  Scenario: landing gate is not restored
    Tool:     bash
    Steps:    node -e "const s=require('fs').readFileSync('frontend/src/App.jsx','utf8'); if(/hasOnboarded\\s*\\?\\s*<Navigate\\s+to=\"\\/ask\"/.test(s)) process.exit(1);"
    Expected: command exits 0; no onboarding-gated root redirect exists.
    Evidence: .omo/evidence/task-1-root-route-error.txt
  ```

  Commit: YES | Message: `feat(frontend): make root route the product asking surface` | Files: [`frontend/src/App.jsx`, `frontend/scripts/check-main-hero.mjs`, `frontend/package.json`]

- [ ] 2. Context hook/provider split

  What to do: Keep `AppContext` and `useApp` in `frontend/src/context/appContext.js`, import the shared `AppContext` into `AppContext.jsx`, and update consumers to import `useApp` from `appContext.js`. This keeps the provider module component-focused for lint/Fast Refresh while preserving a single context instance.
  Must NOT do: Do not create a second provider; do not move streaming state into context; do not make context refreshers throw on best-effort auth/children loads.

  Parallelization: Can parallel: YES | Wave 1 | Blocks: [5, 6, 7] | Blocked by: []

  References (executor has NO interview context - be exhaustive):
  - API/Type: `frontend/src/context/appContext.js:3` - single exported `AppContext` instance.
  - API/Type: `frontend/src/context/appContext.js:5` - shared `useApp` hook.
  - Pattern:  `frontend/src/context/AppContext.jsx:3` - provider imports the shared context object.
  - Pattern:  `frontend/src/context/AppContext.jsx:52` - named `refreshConversations` callback can self-reference in retry banner.
  - Pattern:  `frontend/src/context/AppContext.jsx:60` - initial auth/children/conversation refreshes run in parallel.
  - External: `https://vite.dev/guide/cli` - Vite dev/build commands used to verify the split in this SPA.

  Acceptance criteria (agent-executable only):
  - [ ] `cd frontend && npm run lint` exits 0.
  - [ ] `grep -R "from '../context/AppContext'\\|from './context/AppContext'" -n frontend/src --include='*.jsx' --include='*.js'` returns no consumer import except `main.jsx` importing `AppProvider`.

  QA scenarios (MANDATORY - task incomplete without these):
  ```
  Scenario: hook/provider imports are lint-clean
    Tool:     bash
    Steps:    cd frontend && npm run lint
    Expected: command exits 0 with no react-refresh or hook dependency errors.
    Evidence: .omo/evidence/task-2-context-lint.txt

  Scenario: no duplicate context consumer path
    Tool:     bash
    Steps:    grep -R "useApp } from '../context/AppContext'\\|useApp } from './context/AppContext'" -n frontend/src --include='*.jsx' --include='*.js'; test $? -eq 1
    Expected: grep finds no stale `useApp` imports from `AppContext.jsx`.
    Evidence: .omo/evidence/task-2-context-imports.txt
  ```

  Commit: YES | Message: `refactor(frontend): keep app context hook stable across hero routes` | Files: [`frontend/src/context/appContext.js`, `frontend/src/context/AppContext.jsx`, `frontend/src/components/AppLayout.jsx`, `frontend/src/components/LoginWall.jsx`, `frontend/src/pages/Ask.jsx`, `frontend/src/pages/Start.jsx`, `frontend/src/pages/Settings.jsx`]

- [ ] 3. Main hero content constants

  What to do: Move hero tagline, trusted-source labels, proof stats, and category examples into `frontend/src/components/heroContent.js`; import them in `ChatInterface.jsx`.
  Must NOT do: Do not introduce new copy in English; do not add marketing CTAs that compete with the composer; do not add external data fetches for hero content.

  Parallelization: Can parallel: YES | Wave 1 | Blocks: [4, 5, 7] | Blocked by: []

  References (executor has NO interview context - be exhaustive):
  - Pattern:  `frontend/src/components/heroContent.js:1` - Korean safety/trust tagline.
  - Pattern:  `frontend/src/components/heroContent.js:4` - trusted source families.
  - Pattern:  `frontend/src/components/heroContent.js:6` - root hero proof points.
  - Pattern:  `frontend/src/components/heroContent.js:12` - category list and example questions.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:12` - content imported into hero surface.

  Acceptance criteria (agent-executable only):
  - [ ] `cd frontend && npm run test:main-hero` exits 0 and checks `HERO_STATS`.
  - [ ] `node -e "const s=require('fs').readFileSync('frontend/src/components/heroContent.js','utf8'); if(!s.includes('Stage 0') || !s.includes('열·체온') || !s.includes('AAP')) process.exit(1)"` exits 0.

  QA scenarios (MANDATORY - task incomplete without these):
  ```
  Scenario: hero proof content is present
    Tool:     bash
    Steps:    cd frontend && npm run test:main-hero
    Expected: command exits 0; the guard finds `HERO_STATS` and the explicit hero headline.
    Evidence: .omo/evidence/task-3-hero-content.txt

  Scenario: category content remains Korean and complete
    Tool:     bash
    Steps:    node -e "const s=require('fs').readFileSync('frontend/src/components/heroContent.js','utf8'); for (const t of ['열·체온','수면','먹이기','발달','기타']) if(!s.includes(t)) process.exit(1)"
    Expected: command exits 0; all five categories exist.
    Evidence: .omo/evidence/task-3-hero-content-error.txt
  ```

  Commit: YES | Message: `feat(frontend): centralize root hero content` | Files: [`frontend/src/components/heroContent.js`, `frontend/src/components/ChatInterface.jsx`]

- [ ] 4. Hero welcome composition and responsive visual styling

  What to do: Render brand kicker, H1, tagline, proof stats, trust strip, and a framed composer panel on the empty state. Use existing design tokens and responsive CSS so desktop shows proof stats while mobile keeps the hero compact.
  Must NOT do: Do not build a second landing page; do not introduce new hex colors; do not use decorative orbs or purely marketing layout inside the app surface.

  Parallelization: Can parallel: YES | Wave 2 | Blocks: [7] | Blocked by: [1, 3]

  References (executor has NO interview context - be exhaustive):
  - Pattern:  `frontend/src/components/ChatInterface.jsx:155` - welcome/hero render branch.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:160` - H1 text.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:162` - proof stats render.
  - Pattern:  `frontend/src/components/ChatInterface.css:137` - welcome layout.
  - Pattern:  `frontend/src/components/ChatInterface.css:171` - responsive hero title sizing.
  - Pattern:  `frontend/src/components/ChatInterface.css:189` - proof stats grid.
  - Pattern:  `frontend/src/components/ChatInterface.css:638` - mobile hero adjustments.

  Acceptance criteria (agent-executable only):
  - [ ] `cd frontend && npm run build` exits 0.
  - [ ] Browser screenshot `.omo/evidence/main-hero-root.png` contains the root hero H1 and framed composer.
  - [ ] Browser screenshot `.omo/evidence/main-hero-mobile.png` contains the mobile hero H1 and send button without overlap.

  QA scenarios (MANDATORY - task incomplete without these):
  ```
  Scenario: desktop root hero renders
    Tool:     playwright(real Chrome)
    Steps:    Start `cd frontend && npm run dev -- --host 127.0.0.1`; open `http://127.0.0.1:<vite-port>/`; mock `/api/auth/me`, `/api/auth/providers`, `/api/children`, and `/api/conversations` as empty/anonymous JSON; capture a full-page screenshot.
    Expected: H1 `부모 라운드테이블에 바로 물어보세요`, trust strip, category chips, and composer are visible.
    Evidence: .omo/evidence/main-hero-root.png

  Scenario: mobile root hero remains compact
    Tool:     playwright(real Chrome)
    Steps:    Use viewport `390x844`; clear `localStorage.pr_free_ask_used`; open `http://127.0.0.1:<vite-port>/`; capture a full-page screenshot.
    Expected: H1 and send button are visible; proof stats are hidden; no text overlaps bottom navigation.
    Evidence: .omo/evidence/main-hero-mobile.png
  ```

  Commit: YES | Message: `feat(frontend): frame the asking composer as the root hero action` | Files: [`frontend/src/components/ChatInterface.jsx`, `frontend/src/components/ChatInterface.css`]

- [ ] 5. Composer/category/child interaction behavior

  What to do: Ensure the root hero composer keeps child context above the textarea, categories update example chips, example chips fill/focus the textarea, Enter sends, Shift+Enter creates a newline, empty input disables send, and `maxLength` remains 5000.
  Must NOT do: Do not make categories required; do not auto-send example clicks; do not remove child-chip navigation to settings.

  Parallelization: Can parallel: YES | Wave 2 | Blocks: [7] | Blocked by: [2, 3]

  References (executor has NO interview context - be exhaustive):
  - Pattern:  `frontend/src/components/ChatInterface.jsx:43` - submit guard and outgoing content format.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:53` - Enter vs Shift+Enter handling.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:60` - example chip fill/focus.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:197` - hero composer form.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:198` - child chip before composer controls.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:202` - category pill group.
  - Pattern:  `frontend/src/components/ChatInterface.jsx:225` - textarea with 5000 max length.
  - Pattern:  `frontend/src/components/ChatInterface.css:371` - framed hero ask panel.
  - Pattern:  `frontend/src/components/ChatInterface.css:538` - category pill layout.

  Acceptance criteria (agent-executable only):
  - [ ] Browser smoke fills a question and observes `질문 보내기` disabled before input and enabled after input.
  - [ ] Browser smoke clicks `수면` and sees sleep example text.
  - [ ] `cd frontend && npm run lint` exits 0.

  QA scenarios (MANDATORY - task incomplete without these):
  ```
  Scenario: category updates examples and input enables send
    Tool:     playwright(real Chrome)
    Steps:    Open root with mocked API; click button `수면`; wait for text `밤에 자주 깨서 우는 아이, 어떻게 도와줄까요?`; assert button `질문 보내기` disabled; fill textarea placeholder `궁금한 점을 편하게 적어주세요…`; assert send enabled.
    Expected: category-specific example appears and send button state changes only after non-empty input.
    Evidence: .omo/evidence/main-hero-filled.png

  Scenario: child context is non-blocking
    Tool:     playwright(real Chrome)
    Steps:    Mock `/api/children` as `[]`; open root; inspect button text `아이 정보 추가하기`; click it.
    Expected: app navigates to `/settings`; no send-blocking validation appears before click.
    Evidence: .omo/evidence/task-5-child-chip-empty.png
  ```

  Commit: YES | Message: `feat(frontend): keep root composer interactions direct and child-aware` | Files: [`frontend/src/components/ChatInterface.jsx`, `frontend/src/components/ChatInterface.css`]

- [ ] 6. Conversation streaming/free-question/retry behavior under root

  What to do: Keep `Ask.jsx` as the local streaming owner, preserve `ownedIdRef`, send typed child age and child profile id, append user/assistant messages, render stage events, mark anonymous free ask only on `complete`, and keep retry reusing `lastSend`.
  Must NOT do: Do not create a new conversation on retry; do not mark free ask on error; do not reload over the locally created conversation after navigate.

  Parallelization: Can parallel: YES | Wave 2 | Blocks: [7] | Blocked by: [1, 2]

  References (executor has NO interview context - be exhaustive):
  - Pattern:  `frontend/src/pages/Ask.jsx:23` - `ownedIdRef` protects in-memory streaming state.
  - Pattern:  `frontend/src/pages/Ask.jsx:25` - route load/clear effect.
  - Pattern:  `frontend/src/pages/Ask.jsx:49` - SSE event reducer.
  - Pattern:  `frontend/src/pages/Ask.jsx:68` - completion handling and free-question marking.
  - Pattern:  `frontend/src/pages/Ask.jsx:81` - assistant placeholder setup.
  - Pattern:  `frontend/src/pages/Ask.jsx:91` - typed age/profile payload passed to stream API.
  - Pattern:  `frontend/src/pages/Ask.jsx:107` - create conversation and navigate to `/ask/:id`.
  - Pattern:  `frontend/src/pages/Ask.jsx:129` - retry reuses `lastSend`.
  - Pattern:  `frontend/src/pages/Ask.jsx:144` - anonymous lock only applies without route id.

  Acceptance criteria (agent-executable only):
  - [ ] Playwright mocked stream navigates from `/` to `/ask/qa-1`.
  - [ ] Playwright mocked stream renders user message, Stage 3 final answer, and `다른 질문 하기`.
  - [ ] After `complete`, revisiting empty root with `pr_free_ask_used=true` shows the login wall, not the composer.

  QA scenarios (MANDATORY - task incomplete without these):
  ```
  Scenario: mocked stream completes from root
    Tool:     playwright(real Chrome)
    Steps:    Mock POST `/api/conversations` to `{ "id": "qa-1" }`; mock POST `/api/conversations/qa-1/message/stream` with SSE events `stage0_complete`, `stage3_complete` where `data.response` is `아이 상태를 보며 수분 섭취와 휴식을 도와주세요.`, then `complete`; submit from `/`.
    Expected: URL becomes `/ask/qa-1`, user message appears, final answer appears, and `다른 질문 하기` appears.
    Evidence: .omo/evidence/main-hero-stream-complete.png

  Scenario: anonymous free-question lock after completion
    Tool:     playwright(real Chrome)
    Steps:    Complete the mocked stream as anonymous, then navigate to `/` with no route id.
    Expected: composer is replaced by `LoginWall`; existing `/ask/qa-1` remains readable.
    Evidence: .omo/evidence/task-6-free-lock.png
  ```

  Commit: YES | Message: `feat(frontend): preserve streaming flow from the root hero` | Files: [`frontend/src/pages/Ask.jsx`, `frontend/src/components/ChatInterface.jsx`]

- [ ] 7. End-to-end browser QA and evidence capture

  What to do: Run final static checks, lint/build, then browser QA through the root hero, category/input state, mocked stream, and mobile render. Save screenshots and command outputs under `.omo/evidence/`.
  Must NOT do: Do not rely only on screenshots; every screenshot must correspond to a binary assertion in the script or command output.

  Parallelization: Can parallel: NO | Wave 3 | Blocks: [] | Blocked by: [4, 5, 6]

  References (executor has NO interview context - be exhaustive):
  - Test:     `frontend/package.json:10` - `test:main-hero` script.
  - Test:     `frontend/scripts/check-main-hero.mjs:8` - route and hero static assertions.
  - Pattern:  `frontend/src/components/Stage3.jsx:52` - Stage 3 consumes `finalResponse.response`, so mocked SSE must use `data.response`.
  - External: `https://playwright.dev/docs/screenshots` - screenshot API for browser evidence.
  - External: `https://vite.dev/guide/cli` - Vite dev/build command reference.

  Acceptance criteria (agent-executable only):
  - [ ] `cd frontend && npm run test:main-hero` exits 0.
  - [ ] `cd frontend && npm run lint` exits 0.
  - [ ] `cd frontend && npm run build` exits 0.
  - [ ] `.omo/evidence/main-hero-root.png`, `.omo/evidence/main-hero-filled.png`, `.omo/evidence/main-hero-stream-complete.png`, and `.omo/evidence/main-hero-mobile.png` exist.

  QA scenarios (MANDATORY - task incomplete without these):
  ```
  Scenario: full static and production verification
    Tool:     bash
    Steps:    cd frontend && npm run test:main-hero && npm run lint && npm run build
    Expected: all three commands exit 0.
    Evidence: .omo/evidence/task-7-static-build.txt

  Scenario: full browser smoke with mocked API
    Tool:     playwright(real Chrome)
    Steps:    Start `cd frontend && npm run dev -- --host 127.0.0.1`; use Playwright Chromium to route `http://localhost:8001/**`; fulfill auth/providers/children/conversations as anonymous JSON; submit from `/`; fulfill stream with `stage0_complete`, `stage3_complete` using `data.response`, and `complete`; clear `pr_free_ask_used` before mobile empty-state screenshot.
    Expected: desktop root, filled composer, completed stream, and mobile root screenshots are captured with visible asserted text.
    Evidence: .omo/evidence/main-hero-root.png, .omo/evidence/main-hero-filled.png, .omo/evidence/main-hero-stream-complete.png, .omo/evidence/main-hero-mobile.png
  ```

  Commit: YES | Message: `test(frontend): cover root hero routing and browser smoke` | Files: [`frontend/scripts/check-main-hero.mjs`, `frontend/package.json`, `.omo/evidence/*`]

## Final verification wave (MANDATORY - after all implementation tasks)
> Runs in PARALLEL. ALL must APPROVE. Surface results to the caller and wait for an explicit "okay" before declaring complete.
- [ ] F1. Plan compliance audit - every task done, every acceptance criterion met
- [ ] F2. Code quality review - diagnostics clean, idioms match, no dead code
- [ ] F3. Real manual QA - every QA scenario executed with evidence captured
- [ ] F4. Scope fidelity - nothing extra shipped beyond Must-Have, nothing Must-NOT-Have introduced

## Commit strategy
- One logical change per commit. Conventional Commits (`<type>(<scope>): <subject>`) plus Lore trailers where useful.
- Atomic: every commit builds and passes tests on its own.
- No "WIP" / "fix typo squash later" commits on the final branch - clean up before merge.
- Reference the plan file path in the final commit footer: `Plan: .omo/plans/main-page-behavior.md`.

## Success criteria
- All Must-Have shipped; all QA scenarios pass with captured evidence; F1-F4 approved; commit history clean.
