<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# lib

## Purpose
Small, framework-agnostic helpers (plain ES module exports, no React) shared across the frontend. Currently this is the child-age layer: it converts between the stored birthdate format and the human-readable Korean age labels the UI shows, and derives a fallback `age_days`. These helpers feed the child profile / age selector and the "child age" context that accompanies a parent's question. Per the file header, the server is the source of truth for the safety-relevant `age_days`; the client values here are display and fallback only.

## Key Files
| File | Description |
| --- | --- |
| `age.js` | Birthdate <-> age helpers. Stores birthdate at year+month granularity (`YYYY-MM-01`) and derives a warm Korean age label, whole-months, and a fallback `age_days`. |

## For AI Agents

### Working In This Directory
- **Storage format is load-bearing**: a child's birthdate is always `YYYY-MM-01` (day pinned to `01`). `toBirthdate(year, month)` produces it and `fromBirthdate(birthdate)` parses it back to `{ year, month }`. Keep both in sync if you ever change the format, and remember consumers/back-end parse this exact shape.
- **`month` is 1-12** in this module's public API (human month). `toBirthdate` zero-pads it; `ageDays` converts to a JS `Date` with `month - 1` because the `Date` constructor is 0-indexed. Don't drop the `- 1`.
- **`age_days` is a fallback, not the truth**: the header comment is explicit that the server computes the safety-relevant `age_days` from the birthdate. `ageDays()` here exists only as a client fallback; do not start gating safety/emergency logic on it.
- **Labels are Korean and intentional**: `ageLabel` emits `"3개월"`, `"11개월"`, `"2세 4개월"`, `"5세"` (months under 12, otherwise years + remaining months, dropping the months part when zero). `childDisplayName` falls back to `우리 아이` ("our child") when no name is set. If you touch these strings, mind the broader Korean-text gotchas noted in project memory (e.g. JS `\b` word boundaries do not fire after Hangul).
- **Null-safety**: `fromBirthdate(null/'')` returns `{ year: null, month: null }`; `monthsOld` returns `0` and `ageDays` returns `null` for a missing/invalid birthdate. Preserve these guards — callers rely on them rather than try/catch.
- **`monthsOld` is "now"-relative** (uses `new Date()` / `Date.now()`), so its output is time-dependent and not pure. Keep that in mind for tests and memoization.
- Pure ES module, no JSX/React imports. Keep it that way so it stays trivially importable from both components and any non-React utility.

### Testing Requirements
- This directory has no dedicated test runner; verify via the frontend build/lint from the `frontend/` dir:
  - `cd frontend && npm run build`
  - `cd frontend && npm run lint`
- Spot-check label output mentally/at the REPL for the boundary cases: `< 12` months -> `"N개월"`, exactly `12`/`24` months -> `"N세"` (no months suffix), and a remainder -> `"N세 M개월"`.

### Common Patterns
- One exported helper per concern, each documented with a one-line JSDoc above it.
- Defensive numeric coercion (`Number(...)`, `Math.max(0, ...)`, `padStart`) over throwing.
- Korean user-facing strings live inline in these helpers (this is a Korean-facing product).

## Dependencies

### Internal
- None. This module has no imports; it is a leaf utility that other parts of `frontend/src` (child profile / age selector UI and the question-composition flow) import from.

### External
- None. Uses only built-in `Date` / `String` / `Math`.

<!-- MANUAL: Notes added below this line are preserved on regeneration -->
