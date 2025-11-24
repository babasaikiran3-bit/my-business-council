# LLM Council - Refactored Edition

A modern 3-stage deliberation system where multiple LLMs collaboratively answer user questions through anonymized peer review.

## Architecture

### Tech Stack
- **Backend**: Node.js + Express + TypeScript
- **Frontend**: React + Vite + Radix UI
- **API**: OpenRouter for LLM access

### Design Philosophy
- **Stage 1**: Individual responses from council members
- **Stage 2**: Anonymized peer evaluation (prevents bias)
- **Stage 3**: Chairman synthesizes final answer

## Getting Started

### Prerequisites
- Node.js 18+
- npm or yarn
- OpenRouter API key

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ai-council
```

2. **Install server dependencies**
```bash
cd server
npm install
```

3. **Install frontend dependencies**
```bash
cd ../frontend
npm install
```

4. **Configure environment**
Create `server/.env`:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
PORT=8001
```

### Running the Application

**Development Mode** (recommended):

Terminal 1 - Backend:
```bash
cd server
npm run dev
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8001

## Project Structure

```
ai-council/
├── server/                 # Node.js/TypeScript backend
│   ├── src/
│   │   ├── services/      # Business logic
│   │   │   ├── council.ts # 3-stage council logic
│   │   │   ├── openrouter.ts # API client
│   │   │   └── storage.ts # JSON storage
│   │   ├── types/         # TypeScript types
│   │   ├── config.ts      # Configuration
│   │   └── index.ts       # Express server
│   ├── package.json
│   └── tsconfig.json
│
├── frontend/              # React + Vite frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   │   ├── ChatInterface.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   ├── Stage1.jsx
│   │   │   ├── Stage2.jsx
│   │   │   └── Stage3.jsx
│   │   ├── App.jsx
│   │   ├── api.js         # API client
│   │   └── index.css      # Global styles
│   └── package.json
│
└── data/                  # Conversation storage
    └── conversations/     # JSON files
```

## API Endpoints

### Conversations
- `GET /api/conversations` - List all conversations
- `POST /api/conversations` - Create new conversation
- `GET /api/conversations/:id` - Get conversation by ID
- `POST /api/conversations/:id/message` - Send message (blocking)
- `POST /api/conversations/:id/message/stream` - Send message (streaming SSE)

### Mobile App Integration

The API is designed to be mobile-friendly with:
- RESTful endpoints
- JSON responses
- Streaming support via Server-Sent Events (SSE)
- CORS enabled for cross-origin requests

Example mobile integration:
```typescript
// Fetch conversations
const response = await fetch('http://localhost:8001/api/conversations');
const conversations = await response.json();

// Send message with streaming
const eventSource = new EventSource(
  'http://localhost:8001/api/conversations/123/message/stream',
  {
    method: 'POST',
    body: JSON.stringify({ content: 'Your question' })
  }
);

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  // Handle stage1_complete, stage2_complete, stage3_complete events
});
```

## Design System

The application uses a modern dark theme with:
- **Colors**: Indigo accent (#6366f1) on dark backgrounds
- **Typography**: Inter font family
- **Components**: Radix UI primitives
- **Layout**: Responsive with sidebar navigation

## Configuration

### Council Models
Edit `server/src/config.ts` to change:
- `councilModels`: Array of OpenRouter model identifiers
- `chairmanModel`: Model that synthesizes final answer
- `port`: Server port (default: 8001)

### Model Selection
Current defaults:
- Council: GPT-5.1, Gemini-3-Pro, Claude-Sonnet-4.5, Grok-4
- Chairman: Gemini-3-Pro

## Data Storage

Conversations are stored as JSON files in `data/conversations/`:
- Each conversation has a unique UUID
- Messages include full stage1, stage2, stage3 data
- Metadata (label mappings, rankings) only in API responses

## Development

### Backend
```bash
cd server
npm run dev    # Start dev server with hot reload
npm run build  # Compile TypeScript
npm start      # Run compiled JS
```

### Frontend
```bash
cd frontend
npm run dev    # Start Vite dev server
npm run build  # Build for production
npm run preview # Preview production build
```

## Features

- ✅ Real-time streaming responses
- ✅ Anonymous peer evaluation
- ✅ Aggregate ranking system
- ✅ Modern dark theme UI
- ✅ Mobile-ready API
- ✅ Conversation history
- ✅ Automatic title generation

## Future Enhancements

- [ ] User authentication
- [ ] Custom model configuration via UI
- [ ] Export conversations (PDF/Markdown)
- [ ] Model performance analytics
- [ ] Support for reasoning models (o1, etc.)
- [ ] Database storage (PostgreSQL/MongoDB)

## License

MIT
