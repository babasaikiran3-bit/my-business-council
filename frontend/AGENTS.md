<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# frontend

## Purpose
React 19 + Vite single-page app for Parenting Roundtable. It renders the chat UI, the child-age safety triage controls, auth/onboarding flows, and the four-stage council output (Stage 0 evidence base → Stage 1 panelists → Stage 2 rankings → Stage 3 final answer). The build is a static SPA (`dist/`) deployed to Vercel or Netlify; at runtime it talks to the FastAPI backend over `fetch` with `credentials: 'include'` (session cookies) and consumes Server-Sent Events for streaming stage updates. The UI is Korean-first (`<html lang="ko">`, Korean copy + PWA manifest). This directory holds only build/config/deploy plumbing; all application code lives in `src/`.

## Key Files
| File | Description |
| --- | --- |
| `index.html` | Vite entry HTML. Korean `lang="ko"`, mobile-web-app meta (`viewport-fit=cover`, `apple-mobile-web-app-*`), `theme-color #de5c86`, preconnect to `cdn.jsdelivr.net` (Pretendard font CDN), links `/manifest.webmanifest`, mounts `#root`, loads `/src/main.jsx`. |
| `package.json` | Scripts (`dev`/`build`/`lint`/`preview`) and deps. React 19.2, react-dom 19.2, react-markdown 10, react-router-dom 7.16. ESM (`"type": "module"`). No test runner is configured. |
| `vite.config.js` | Vite config: `@vitejs/plugin-react`, `outDir: 'dist'`, `sourcemap: false` (source maps are intentionally NOT shipped to production). |
| `eslint.config.js` | Flat ESLint config. Ignores `dist`, applies to `**/*.{js,jsx}`, extends `js.recommended` + react-hooks + react-refresh (vite). Key rule: `no-unused-vars` errors but ignores names matching `^[A-Z_]` (allows unused PascalCase/CONSTANT imports). |
| `netlify.toml` | Netlify deploy: `command = "npm run build"`, `publish = "dist"`, SPA fallback redirect `/* -> /index.html` (200). Set `VITE_API_BASE` in the site build env. |
| `vercel.json` | Vercel deploy: `buildCommand npm run build`, `outputDirectory dist`, SPA rewrite `/(.*) -> /index.html`. Set `VITE_API_BASE` in Vercel project env. |
| `README.md` | Stock Vite "React + Vite" template readme — not project-specific; safe to ignore for app behavior. |

Lockfiles (`package-lock.json`) and `node_modules/` are present but not documented here. The build output (`dist/`) is generated and git-ignored.

## Subdirectories
| Directory | Purpose |
| --- | --- |
| `src/` | All application code: React components, routes, API client, design system, safety/markdown utilities (see `src/AGENTS.md`). |
| `public/` | Static assets copied verbatim into `dist/`: `manifest.webmanifest` (PWA: Korean name/description, `standalone`, `theme_color #de5c86`, `background_color #fff9f6`, `/vite.svg` icon) and `vite.svg`. No own AGENTS.md — edit files here directly. |

## For AI Agents

### Working In This Directory
- **API base URL is env-driven.** `src/api.js` reads `import.meta.env.VITE_API_BASE` and falls back to `http://localhost:8001` for local dev. The backend runs on **port 8001, not 8000**. Production builds (Vercel/Netlify) MUST have `VITE_API_BASE` set at build time, or the SPA will call localhost. Vite inlines env vars at build, so changing it requires a rebuild, not just a redeploy of the same `dist/`.
- **Only `VITE_`-prefixed env vars are exposed** to client code (Vite rule). Never put secrets in env vars here — everything shipped is public.
- **SPA fallback is required on every host.** Deep links (e.g. `/conversations/abc`) are handled client-side by react-router-dom 7; both `netlify.toml` and `vercel.json` already rewrite all paths to `/index.html`. If you add a new host config, replicate that rewrite or deep links 404.
- **Auth uses cross-site cookies + a CSRF header.** `src/api.js` sends `credentials: 'include'` and a custom `X-Requested-With: parenting-roundtable` header on state-changing requests (its CSRF defense under `SameSite=None`). The backend CORS allowlist must include the frontend origin or all requests fail; keep the two in sync when changing the deploy URL.
- **Korean is the product language.** `index.html`, the manifest, and user-facing strings are Korean. Keep `lang="ko"`, the `theme-color`/manifest colors consistent (`#de5c86` accent, `#fff9f6` background), and remember the Korean-regex emergency-callout gotcha noted in project memory when touching anything that parses Korean text.
- **`sourcemap: false` is deliberate** in `vite.config.js` — do not enable production source maps without reason.
- **ESLint `no-unused-vars` ignores `^[A-Z_]`** — an unused `import SomeComponent` (PascalCase) or `CONSTANT` will NOT lint-error; only lowercase unused vars do. Don't rely on lint to catch unused PascalCase imports.

### Testing Requirements
There is no unit-test runner in this package. Verify changes with:
```
cd frontend && npm install   # first time only
cd frontend && npm run lint   # eslint . — must pass clean
cd frontend && npm run build  # vite build → dist/ — must succeed
```
For local manual QA: `npm run dev` (Vite dev server on 5173) with the backend running on 8001, or `npm run preview` to serve a production `dist/` build. Confirm SSE streaming, the emergency-banner safety spot-checks (newborn + fever surfaces the red banner), and that source links render only for verified trusted-domain URLs.

### Common Patterns
- Static SPA: no SSR, no API routes here — this package builds a `dist/` bundle and nothing more.
- Deploy config is duplicated across `netlify.toml` and `vercel.json` (same build command, output dir, and SPA rewrite). Edit both together so the app deploys identically on either host.
- Flat-config ESLint (`eslint.config.js`, ESLint 9) — no legacy `.eslintrc`. Add new rules/overrides inside the exported array.
- The root `README.md` is the unmodified Vite scaffold; project-specific guidance lives in these AGENTS.md files, not the README.

## Dependencies

### Internal
- `src/` — the actual React application (entry `src/main.jsx`, API client `src/api.js`).
- `public/` — static assets and the PWA manifest folded into the build.
- Runtime dependency on the sibling FastAPI backend (`../backend`) at `VITE_API_BASE` (default `http://localhost:8001`) for conversations, streaming, auth/OAuth, child profiles, and consents.

### External
- `react` / `react-dom` ^19.2 — UI runtime.
- `react-router-dom` ^7.16 — client-side routing (requires the SPA host rewrites).
- `react-markdown` ^10 — renders model/markdown output (paired with safe link components in `src/`).
- `vite` ^7 + `@vitejs/plugin-react` ^5 — dev server, build, HMR (Babel Fast Refresh).
- `eslint` ^9 with `@eslint/js`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, `globals` — linting.
- Pretendard font loaded at runtime from `cdn.jsdelivr.net` (preconnected in `index.html`), not bundled.

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
