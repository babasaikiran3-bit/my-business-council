# Eternal Copilot Frontend

React frontend for the Eternal Copilot application, built with Vite and Tailwind CSS v4.

## Tech Stack

- **React** - UI framework
- **Vite 7.x** - Build tool and dev server (requires Node.js 18+)
- **Tailwind CSS v4** - CSS-first configuration (no `tailwind.config.js`)
- **shadcn/ui** - Component library with Radix UI primitives
- **react-markdown** - Markdown rendering for model responses

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

The app runs at http://localhost:5173 by default.

## Tailwind CSS v4 Configuration

This project uses CSS-first Tailwind configuration. All theme settings are in `src/index.css`:

```css
@import "tailwindcss";

@theme {
  --color-background: hsl(0 0% 100%);
  --color-foreground: hsl(240 10% 3.9%);
  /* ... */
}
```

There is **no `tailwind.config.js` file** - this is intentional for Tailwind v4.

## Component Structure

```
src/
├── components/
│   ├── ui/          # shadcn/ui components (Button, Card, Tabs, etc.)
│   ├── Sidebar.jsx  # Resizable sidebar with conversation list
│   ├── ChatInterface.jsx  # Main chat input and message display
│   ├── Stage1.jsx   # Individual model responses
│   ├── Stage2.jsx   # Peer evaluations and rankings
│   └── Stage3.jsx   # Final synthesized answer
├── lib/
│   └── utils.js     # cn() utility for class merging
├── api.js           # API client with SSE streaming support
├── App.jsx          # Main application component
└── index.css        # Tailwind theme and global styles
```

## Common Issues

### CSS changes not appearing
Run a hard refresh: `Cmd + Shift + R` (macOS) or `Ctrl + Shift + R` (Windows/Linux)

### Node.js version error
Vite 7.x requires Node.js 18+. Install Node.js 20: `brew install node@20`

### Adding new shadcn/ui components
Manually adapt components for Tailwind v4 CSS-first configuration.
