# LLM Council

![llmcouncil](header.jpg)

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT 5.1, Google Gemini 3.0 Pro, Anthropic Claude Sonnet 4.5, xAI Grok 4, eg.c), you can group them into your "LLM Council". This repo is a simple, local web app that essentially looks like ChatGPT except it uses OpenRouter to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Chairman LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each individual LLM is given the responses of the other LLMs. Under the hood, the LLM identities are anonymized so that the LLM can't play favorites when judging their outputs. The LLM is asked to rank them in accuracy and insight.
3. **Stage 3: Final response**. The designated Chairman of the LLM Council takes all of the model's responses and compiles them into a single final answer that is presented to the user.

## Vibe Code Alert

This project was 99% vibe coded as a fun Saturday hack because I wanted to explore and evaluate a number of LLMs side by side in the process of [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438). It's nice and useful to see multiple responses side by side, and also the cross-opinions of all LLMs on each other's outputs. I'm not going to support it in any way, it's provided here as is for other people's inspiration and I don't intend to improve it. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

## Setup

### 1. Install Dependencies

**Backend (Node.js/TypeScript):**
```bash
cd server
npm install
cd ..
```

**Frontend (React/Vite):**
```bash
cd frontend
npm install
cd ..
```

**Mobile (Flutter) - Optional:**
```bash
cd mobile
flutter pub get
cd ..
```

### 2. Configure API Key

Create a `.env` file in the `server` directory:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
PORT=8001
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

### 3. Configure Models (Optional)

Edit `server/src/config.ts` to customize the council:

```typescript
export const config = {
  councilModels: [
    'openai/gpt-5.1',
    'google/gemini-3-pro-preview',
    'anthropic/claude-sonnet-4.5',
    'x-ai/grok-4',
  ],
  chairmanModel: 'google/gemini-3-pro-preview',
  // ...
};
```

## Running the Application

### Web Application

Terminal 1 (Backend):
```bash
cd server
npm run dev
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

### Mobile Application (Flutter)

Make sure the backend server is running, then:

```bash
cd mobile
flutter run
```

Update the API base URL in `mobile/lib/main.dart` if needed:
```dart
baseUrl: 'http://localhost:8001',  // For emulator/simulator
// or
baseUrl: 'http://YOUR_IP:8001',    // For physical device
```

## Tech Stack

### Backend
- **Framework:** Express.js with TypeScript
- **Runtime:** Node.js 18+
- **HTTP Client:** Native fetch API
- **Storage:** JSON files in `data/conversations/`
- **API:** OpenRouter for LLM access

### Web Frontend
- **Framework:** React 19 with Vite
- **UI Components:** Radix UI primitives
- **Styling:** Modern CSS with custom properties (light theme)
- **Markdown:** react-markdown for rendering responses
- **Design:** Clean white theme with black accents

### Mobile App
- **Framework:** Flutter 3.0+
- **State Management:** Provider pattern
- **UI:** Material Design 3 (dark theme)
- **HTTP:** http package with SSE support
- **API Integration:** RESTful endpoints with streaming
