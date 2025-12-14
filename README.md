# Eternal Copilot

![Eternal Copilot](header.jpg)

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT 5.1, Google Gemini 3.0 Pro, Anthropic Claude Sonnet 4.5, xAI Grok 4, etc.), you can group them into your "Eternal Copilot". This repo is a simple, local web app that essentially looks like ChatGPT except it uses OpenRouter to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Lead Synthesizer LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each individual LLM is given the responses of the other LLMs. Under the hood, the LLM identities are anonymized so that the LLM can't play favorites when judging their outputs. The LLM is asked to rank them in accuracy and insight.
3. **Stage 3: Final response**. The designated Lead Synthesizer of Eternal Copilot takes all of the model's responses and compiles them into a single final answer that is presented to the user.

## Features

### Prompt Improver

Before sending your question to Eternal Copilot, you can optionally improve your prompt using the **"✨ Improve Prompt"** button. This feature:

- Uses a fast LLM to rewrite your prompt to be clearer, more specific, and better structured
- Shows your original prompt below the textarea so you can compare the changes
- Provides an **"↩ Undo"** button to revert to your original prompt if needed
- Preserves your original intent while making the prompt more likely to elicit high-quality responses

## Vibe Code Alert

This project was 99% vibe coded as a fun Saturday hack because I wanted to explore and evaluate a number of LLMs side by side in the process of [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438). It's nice and useful to see multiple responses side by side, and also the cross-opinions of all LLMs on each other's outputs. I'm not going to support it in any way, it's provided here as is for other people's inspiration and I don't intend to improve it. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Configure API Key

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

### 3. Configure Models (Optional)

Edit `backend/config.py` to customize Eternal Copilot:

```python
# Copilot models - the LLMs that answer your question
COPILOT_MODELS = [
    "openai/gpt-5.2-pro",
    "google/gemini-3-pro-preview",
    "anthropic/claude-opus-4.5",
    "x-ai/grok-code-fast-1",
    "x-ai/grok-4",
]

# Chairman model - synthesizes the final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Prompt improver model - used for the "Improve Prompt" feature
# Use a fast model for quick response times
PROMPT_IMPROVER_MODEL = "google/gemini-3-pro-preview"
```

## Running the Application

### Option 1: Use the start script (Recommended)
```bash
./start.sh
```

The start script will automatically check and install dependencies if they're missing, then start both servers.

**Option 2: Run manually**

Terminal 1 (Backend):
```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

## Tech Stack

- **Backend:** FastAPI (Python 3.10+), async httpx, OpenRouter API, Server-Sent Events (SSE) for streaming
- **Frontend:** React + Vite 7.x, Tailwind CSS v4 (CSS-first configuration), shadcn/ui components
- **UI Components:** shadcn/ui with Radix UI primitives (Button, Card, Tabs, Textarea, ScrollArea)
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, npm for JavaScript

## UI Features

### Resizable Sidebar
The sidebar can be resized by dragging its right edge:
- **Minimum width:** 240px
- **Maximum width:** 480px
- **Default width:** 288px
- Width is automatically saved to localStorage and restored on page reload

### Progressive Streaming Updates
The application uses Server-Sent Events (SSE) for real-time updates:
- See each stage complete as it happens (Stage 1 → Stage 2 → Stage 3)
- Loading indicators show which stage is currently processing
- No need to wait for the entire copilot deliberation to complete

### shadcn/ui Design System
The frontend uses the shadcn/ui component library with a zinc color palette:
- Consistent, accessible components throughout the UI
- Light mode theme with modern styling
- Responsive design that works on different screen sizes

## System Requirements

### Node.js Version

**Node.js 18+ is required** (20+ recommended). The frontend uses Vite 7.x which requires modern JavaScript features not available in older Node.js versions.

To check your Node.js version:
```bash
node --version
```

If you see an error like `Unexpected token '??='` when starting the frontend, your Node.js version is too old.

### Installing Node.js 20 via Homebrew (macOS)

```bash
brew install node@20
```

**Important:** Homebrew installs Node.js 20 as "keg-only", meaning it won't be automatically added to your PATH. To make it accessible system-wide, add the following to your shell configuration file:

**For bash (~/.bash_profile):**
```bash
echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.bash_profile
source ~/.bash_profile
```

**For zsh (~/.zshrc):**
```bash
echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Note:** On Intel Macs, the Homebrew path is `/usr/local/opt/node@20/bin` instead of `/opt/homebrew/opt/node@20/bin`.

## Troubleshooting

### Frontend won't start / "Unexpected token" errors

**Problem:** When running `npm run dev` or `./start.sh`, you see errors like:
```
SyntaxError: Unexpected token '??='
```

**Cause:** Your Node.js version is too old. Vite requires Node.js 18+.

**Solution:**
1. Install Node.js 20 via Homebrew: `brew install node@20`
2. Add Node.js 20 to your PATH (see instructions above)
3. Verify with `node --version` (should show v20.x.x)
4. Restart your terminal and try again

### "keg-only" Node.js installation

**Problem:** After installing Node.js via Homebrew, `node --version` still shows the old version.

**Cause:** Homebrew installed Node.js as "keg-only" (not symlinked to your PATH).

**Solution:** Add the explicit PATH to your shell configuration file as shown above, then restart your terminal or run `source ~/.zshrc` (or `source ~/.bash_profile`).

### Backend port conflict

**Problem:** Backend fails to start with "Address already in use" error.

**Solution:** The backend runs on port 8001 by default. Check if another application is using this port:
```bash
lsof -i :8001
```
Kill the conflicting process or modify the port in `backend/main.py`.

### CSS changes not visible

**Problem:** After making CSS changes, the UI doesn't update even after refreshing.

**Cause:** Browser caching or Vite HMR not fully applying CSS updates.

**Solution:**
1. Perform a hard refresh: `Cmd + Shift + R` (macOS) or `Ctrl + Shift + R` (Windows/Linux)
2. If that doesn't work, open DevTools → right-click the refresh button → "Empty Cache and Hard Reload"
3. As a last resort, restart the Vite dev server

### Sidebar padding not appearing

**Problem:** The sidebar content appears too close to the edges with no horizontal padding.

**Cause:** This can happen if there's a CSS conflict or if the ScrollArea component isn't structured correctly.

**Solution:** Ensure padding is applied to an inner `<div>` wrapper inside ScrollArea, not to the ScrollArea component itself:
```jsx
// ✓ Correct
<ScrollArea className="flex-1">
  <div className="px-12 pt-5 pb-4">
    {/* content */}
  </div>
</ScrollArea>

// ✗ Wrong - padding won't reach content
<ScrollArea className="flex-1 px-12 pt-5 pb-4">
  {/* content */}
</ScrollArea>
```

## Development Notes

### Tailwind CSS v4 Configuration

This project uses **Tailwind CSS v4** with CSS-first configuration. There is no `tailwind.config.js` file - this is intentional.

**Configuration is done in `frontend/src/index.css` using the `@theme` directive:**
```css
@import "tailwindcss";

@theme {
  --color-background: hsl(0 0% 100%);
  --color-foreground: hsl(240 10% 3.9%);
  --color-primary: hsl(240 5.9% 10%);
  /* ... other colors */
  --radius: 0.5rem;
}
```

**PostCSS configuration (`frontend/postcss.config.js`):**
```js
export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}
```

### shadcn/ui Integration

The project uses shadcn/ui components with the zinc color palette. Components are located in `frontend/src/components/ui/` and include:
- `button.jsx` - Button with multiple variants
- `card.jsx` - Card container components
- `tabs.jsx` - Tab navigation
- `textarea.jsx` - Multiline text input
- `scroll-area.jsx` - Scrollable content area

To add new shadcn/ui components, adapt them manually for Tailwind v4 CSS-first configuration.
