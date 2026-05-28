# Frontend

This directory contains the React and Vite single-page application for LLM Council.

## Purpose

The frontend renders the conversation history and exposes the three-stage council pipeline:

- user message input
- stage 1 model tabs
- stage 2 peer ranking details, aggregate rankings, and heatmap
- stage 3 final synthesis
- conversation delete and clear-history actions
- copy actions for key message outputs

## Commands

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Build for production:

```bash
npm run build
```

Preview the production bundle locally:

```bash
npm run preview
```

## Environment

The frontend reads one optional environment variable:

```bash
VITE_API_BASE=http://localhost:8001
```

Behavior:

- unset: local development defaults to `http://localhost:8001`
- set to a full URL: the app targets that backend directly
- set to an empty string at build time: the app uses relative `/api/...` requests, which is what the production container expects behind Nginx

## Production Container

The production image is built with [Dockerfile.frontend](../Dockerfile.frontend).

Runtime behavior:

- the React app is built once during image creation
- Nginx serves the static files
- Nginx proxies `/api/*` to `BACKEND_UPSTREAM`
- `try_files` falls back to `index.html` for SPA routing

The Nginx template lives at [nginx.conf.template](nginx.conf.template).

## Key Files

- [src/App.jsx](src/App.jsx): top-level conversation state and streaming orchestration
- [src/api.js](src/api.js): browser API client and streaming event reader
- [src/components/ChatInterface.jsx](src/components/ChatInterface.jsx): message list and prompt input
- [src/components/Sidebar.jsx](src/components/Sidebar.jsx): conversation list and management actions
- [src/components/Stage1.jsx](src/components/Stage1.jsx): stage 1 tabs
- [src/components/Stage2.jsx](src/components/Stage2.jsx): stage 2 rankings and heatmap integration
- [src/components/Stage3.jsx](src/components/Stage3.jsx): final synthesis display
- [src/components/RankingHeatmap.jsx](src/components/RankingHeatmap.jsx): stage 2 ranking matrix
