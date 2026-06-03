<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# components

## Purpose
Reusable React components for the Parenting Roundtable web UI. Three groups: (1) **layout/nav** — the signed-in app shell, sidebar, and mobile bottom tabs; (2) **council stage renderers** — `Stage0`–`Stage3`, which display the 4-stage pipeline output (sources/evidence → panelist answers → peer rankings → final synthesized answer with a pinned EMERGENCY banner); (3) **UI primitives** — progress, child-context chip, emergency interstitial, landing example, the shared SVG icon set, the login wall, and the safety-critical markdown link sanitizer. The interface language is Korean. Most `.jsx` files are paired with a same-named `.css` (e.g. `Stage3.jsx` + `Stage3.css`); `Icons.jsx` and `markdownComponents.jsx` are the two exceptions (no CSS).

## Key Files

| File | Description |
| --- | --- |
| `AppLayout.jsx` | Signed-in shell for `/ask` and `/settings`: persistent `Sidebar` (desktop) + drawer/`BottomTabBar` (mobile), mobile topbar, transient error `banner` (with optional retry), and a router `<Outlet />`. Pulls conversations/user/providers from `useApp()`. |
| `Sidebar.jsx` | Brand header, "새 질문하기" button, conversation list (active highlight, message count), settings link, and account block (logged-in avatar/logout, or Kakao/Naver login buttons). Controlled `open` prop drives the mobile drawer. |
| `BottomTabBar.jsx` | Mobile-only bottom nav (홈 / 기록 / 설정). 홈→`/ask`, 설정→`/settings` via `useNavigate`; 기록 calls `onOpenHistory` to open the conversation drawer. Hidden on desktop via CSS. |
| `ChatInterface.jsx` | The main conversation surface. Renders welcome state with category pills + example chips, or the message thread. Composes the outgoing query string `[category] 아이 나이: …. 질문: …`. Tucks Stage0/1/2 behind a "근거 보기" `<details>`, shows `Stage3` prominently, `EmergencyBanner`, early sources, `CalmProgress`, and the thread-done disclaimer footer. |
| `Stage0.jsx` | Collapsible "확인한 자료 · 근거 요약" panel: evidence brief (ReactMarkdown, safe components) + consulted source links. Renders `null` when there is neither brief nor sources. |
| `Stage1.jsx` | Tabbed panelist answers (tab label = model name after `/`). Each tab renders the model's response via safe markdown plus per-model source chips. |
| `Stage2.jsx` | Tabbed peer-ranking view. `deAnonymizeText()` is **client-side display only** — replaces "Response A/B/C" with bolded model names. Shows "추출된 순위" (parsed) and "종합 순위" (aggregate, lower avg = better). |
| `Stage3.jsx` | Final answer card. `parseAnswer()` extracts a `> EMERGENCY:`/`> 응급:` callout and pins it (high-contrast, `role="alert"`) at the **top**, removing it from the body so it isn't duplicated. Renders body via safe markdown + a deterministic "참고한 출처" source list. |
| `CalmProgress.jsx` | One calm `role="status"` indicator with a tip rotating every 3.8s (reassurance + how-to-use hints), replacing four technical stage spinners. |
| `ChildChip.jsx` | Persistent child-context chip above the composer; shows name + derived age (`ageLabel(birthdate)`) or an "아이 정보 추가하기" empty state. Tap fires `onClick` (edit). |
| `EmergencyBanner.jsx` | Deterministic high-contrast triage interstitial driven by the backend `emergency` event; `role="alert"`, renders title/message and tappable `tel:` emergency numbers. |
| `ExampleCard.jsx` | Static landing-page example of one real question → emergency note → answer → source chips. Pure presentational, no props. |
| `Icons.jsx` | Shared Lucide-style stroke SVG set (`currentColor`, 1.75 stroke) via the internal `Svg` wrapper, plus Kakao/Naver glyphs and the gradient brand `Logo`. SVG only, never emoji. |
| `LoginWall.jsx` | Shown after an anonymous parent's one free question: trust reasons + Kakao/Naver login links, or a demo-mode "데모로 계속하기" fallback when no providers are enabled. Uses `useApp()`. |
| `markdownComponents.jsx` | **Safety-critical.** `makeSafeMarkdownComponents(sources)` returns a ReactMarkdown `components` map whose `<a>` renderer keeps a link clickable **only** when its trimmed href exactly matches a verified source URL; everything else degrades to a `.blocked-link` `<span>`. |

## For AI Agents

### Working In This Directory

- **Safe markdown is mandatory for model-authored text.** Any ReactMarkdown that renders council/chairman output (Stage0 evidence brief, Stage1 responses, Stage3 body) MUST pass `components={makeSafeMarkdownComponents(sources)}`. Without it, a hallucinated/mis-cited URL becomes a live clickable link. The allowlist match is **exact-string on trimmed href** — do not relax it to substring/hostname matching. (Stage2 ranking text intentionally renders plain `ReactMarkdown` because it has no source links.)
- **Emergency banner parsing in `Stage3.jsx` is load-bearing.** `parseAnswer()` deliberately matches `^(?:EMERGENCY|응급)[\s:：]+` and does **not** use a regex word boundary (`\b`) — `\b` is ASCII-only and never fires after a Hangul syllable, which previously left the Korean "응급:" callout un-pinned (see project memory `korean-regex-emergency-gotcha`). Keep the explicit separator class (includes the fullwidth colon `：`). It also gathers continuation `>` lines.
- **De-anonymization is display-only.** `Stage2.deAnonymizeText()` rewrites "Response A/B/C" → model names purely for the reader; the models genuinely ranked anonymously. Don't move this logic server-side or imply the panel saw real names.
- **Stage tabs key off model name after `/`.** `resp.model.split('/')[1] || resp.model` is the standard short-name pattern used across Stage1/Stage2 (OpenRouter `vendor/model` ids).
- **Sidebar/BottomTabBar are presentational + router-driven.** `AppLayout` owns `sidebarOpen` state and derives `activeConversationId` from the `/ask/:id` path; child nav components receive callbacks/props rather than reading context directly (except `LoginWall`, which uses `useApp()`).
- **CSS pairing convention:** add a same-named `.css` next to a new `.jsx` and `import './Name.css'` at the top. Reuse the global `.markdown-content` wrapper class (defined in `../index.css`) around ReactMarkdown blocks, and `.blocked-link` styling lives there too.
- **UI strings are Korean.** Keep new copy consistent in tone (warm, reassuring) and language unless the task says otherwise. Use icons from `Icons.jsx`, never emoji.

### Testing Requirements

From `frontend/`:

```
npm run build      # Vite production build — must succeed
npm run lint       # ESLint
```

Manual safety spot-checks (run the app, port 5173 → backend 8001): a newborn-fever query MUST surface the pinned red emergency banner in `Stage3` with real trusted-domain sources; a benign query (e.g. toddler nap) must NOT show an emergency banner yet still list sources. Verify a model-authored URL that is not in `sources` renders as inert `.blocked-link` text.

### Common Patterns

- Stage components return `null` early when their data is empty (`Stage0`/`Stage1`/`Stage2` guard on missing brief/responses/rankings).
- Source links always use `target="_blank" rel="noopener noreferrer"`.
- Icon components accept a `size` prop and inherit `currentColor`; pass them as `<Icon size={n} />` and theme via surrounding text color.
- `aria-*` / `role="alert"` / `role="status"` are used intentionally on banners and progress for screen-reader announcement — preserve them.

## Dependencies

### Internal

- `../context/AppContext` (`useApp`) — conversations, user, providers, banner, `enabledProviders`, `clearFreeAsk`, `logout`.
- `../api` (`api.loginUrl`, etc.) — auth/login URLs.
- `../lib/age` (`ageLabel`, `childDisplayName`) — derives child age from birthdate.
- `../App.css`, `../index.css` — app shell + global `.markdown-content` / `.blocked-link` styles.
- `./Icons` — shared across nearly every component here.
- `./markdownComponents` — consumed by `Stage0`, `Stage1`, `Stage3`.

### External

- `react` (hooks: `useState`, `useEffect`, `useRef`).
- `react-router-dom` (`Outlet`, `useNavigate`, `useLocation`).
- `react-markdown` — all rendered markdown (always with safe components for model text).

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
