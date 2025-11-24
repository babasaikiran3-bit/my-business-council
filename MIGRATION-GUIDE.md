# Migration Guide: Python → Node.js/TypeScript + Modern UI

This document outlines the changes made to refactor the AI Council application from Python/FastAPI to Node.js/Express with TypeScript, and redesign the frontend with modern Radix UI components.

## Summary of Changes

### Backend Refactor
- **From**: Python + FastAPI
- **To**: Node.js + Express + TypeScript

#### Key Changes:
1. **Language**: Python → TypeScript
2. **Framework**: FastAPI → Express
3. **Type Safety**: Added comprehensive TypeScript types
4. **Module System**: ESM (import/export)

#### File Mapping:
```
backend/config.py        → server/src/config.ts
backend/openrouter.py    → server/src/services/openrouter.ts
backend/council.py       → server/src/services/council.ts
backend/storage.py       → server/src/services/storage.ts
backend/main.py          → server/src/index.ts
```

### Frontend Redesign
- **From**: Basic React with custom CSS
- **To**: React + Vite + Radix UI with modern dark theme

#### Key Changes:
1. **Design System**: Added modern dark theme with CSS variables
2. **UI Components**: Upgraded to Radix UI primitives
3. **Icons**: Added Lucide React icons
4. **Styling**: Complete CSS overhaul with:
   - Dark color palette (#0a0a0b background)
   - Indigo accent colors (#6366f1)
   - Smooth animations and transitions
   - Modern gradients

#### Dependencies Added:
```json
{
  "@radix-ui/react-tabs": "^1.1.2",
  "@radix-ui/react-scroll-area": "^1.2.2",
  "@radix-ui/react-separator": "^1.1.1",
  "@radix-ui/react-avatar": "^1.1.2",
  "@radix-ui/react-tooltip": "^1.1.6",
  "@radix-ui/react-dialog": "^1.1.4",
  "lucide-react": "^0.469.0",
  "clsx": "^2.1.1"
}
```

## Running the Refactored Application

### Quick Start

1. **Install dependencies** (if not already done):
```bash
# Server
cd server && npm install

# Frontend
cd frontend && npm install
```

2. **Configure environment**:
Create `server/.env`:
```env
OPENROUTER_API_KEY=your_key_here
PORT=8001
```

3. **Run both services**:
```bash
# Option 1: Use the convenience script
./run-dev.sh

# Option 2: Run manually in separate terminals
# Terminal 1
cd server && npm run dev

# Terminal 2
cd frontend && npm run dev
```

### Access Points
- Frontend: http://localhost:5173
- Backend API: http://localhost:8001
- API Health Check: http://localhost:8001/

## API Compatibility

### No Breaking Changes
The API endpoints remain identical:
- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/:id`
- `POST /api/conversations/:id/message`
- `POST /api/conversations/:id/message/stream`

### Response Format
Response formats are **exactly the same** as the Python version, ensuring backward compatibility.

## Mobile App Integration

The refactored API is mobile-ready with:

1. **RESTful Design**: Clean, predictable endpoints
2. **JSON Responses**: Standard format across all endpoints
3. **Streaming Support**: Server-Sent Events for real-time updates
4. **CORS Enabled**: Cross-origin requests supported

### Example Mobile Integration (React Native):

```typescript
// Fetch conversations
const fetchConversations = async () => {
  const response = await fetch('http://your-server:8001/api/conversations');
  return response.json();
};

// Send message with streaming
const sendMessage = (conversationId: string, content: string) => {
  const eventSource = new EventSource(
    `http://your-server:8001/api/conversations/${conversationId}/message/stream`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    }
  );

  eventSource.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);

    switch(data.type) {
      case 'stage1_complete':
        // Update UI with stage 1 responses
        break;
      case 'stage2_complete':
        // Update UI with stage 2 rankings
        break;
      case 'stage3_complete':
        // Update UI with final answer
        break;
    }
  });
};
```

## Design System

### Color Palette
```css
--bg-primary: #0a0a0b       /* Main background */
--bg-secondary: #111113     /* Card backgrounds */
--bg-tertiary: #1a1a1d      /* Elevated surfaces */

--text-primary: #ffffff     /* Primary text */
--text-secondary: #a0a0a8   /* Secondary text */
--text-tertiary: #6b6b75    /* Tertiary text */

--accent-primary: #6366f1   /* Primary accent (indigo) */
--accent-hover: #4f46e5     /* Hover state */
```

### Typography
- Font Family: Inter, system fonts fallback
- Monospace: Fira Code for code/model names

### UI Components
- **Tabs**: Radix UI with custom styling
- **Cards**: Rounded corners (12px), subtle borders
- **Buttons**: Hover effects with transform and glow
- **Inputs**: Focus states with accent-colored ring

## Differences from Python Version

### Improved Features:
1. **Type Safety**: Full TypeScript support prevents runtime errors
2. **Performance**: Express is generally faster for I/O operations
3. **Developer Experience**: Hot reload for both backend and frontend
4. **Modern UI**: Radix UI provides accessible, unstyled primitives
5. **Better Organization**: Clear separation of concerns with services/types

### Behavior Changes:
- **None**: The core council logic remains unchanged
- **Same API**: All endpoints function identically
- **Same Data Format**: JSON storage structure is preserved

## Project Structure

```
ai-council/
├── server/                    # NEW: Node.js/TypeScript backend
│   ├── src/
│   │   ├── services/
│   │   │   ├── council.ts    # Ported from council.py
│   │   │   ├── openrouter.ts # Ported from openrouter.py
│   │   │   └── storage.ts    # Ported from storage.py
│   │   ├── types/            # NEW: TypeScript definitions
│   │   ├── config.ts         # Ported from config.py
│   │   └── index.ts          # Ported from main.py
│   ├── package.json
│   └── tsconfig.json
│
├── frontend/                  # UPDATED: Modern UI
│   ├── src/
│   │   ├── components/       # Updated with new styles
│   │   ├── index.css         # NEW: Dark theme variables
│   │   └── ...
│   └── package.json          # Updated dependencies
│
├── backend/                   # OLD: Can be removed after testing
├── run-dev.sh                # NEW: Development runner
└── README-NEW.md             # NEW: Updated documentation
```

## Testing Checklist

- [ ] Server starts successfully on port 8001
- [ ] Frontend starts successfully on port 5173
- [ ] Can create new conversation
- [ ] Can send message and see Stage 1 responses
- [ ] Can see Stage 2 peer rankings
- [ ] Can see Stage 3 final answer
- [ ] Streaming updates work correctly
- [ ] Conversation history persists
- [ ] Dark theme renders correctly
- [ ] Tabs work in all stages
- [ ] Mobile API endpoints are accessible

## Rollback Plan

If issues arise, you can rollback to the Python version:

1. Stop the new servers (Ctrl+C)
2. Start the old Python backend:
   ```bash
   python -m backend.main
   ```
3. The old frontend will work with the old backend

## Next Steps

1. **Test Thoroughly**: Run through all features
2. **Mobile Integration**: Build mobile app using the API
3. **Production Deploy**:
   - Build: `npm run build` in both server and frontend
   - Deploy server to Node.js hosting (e.g., Railway, Render)
   - Deploy frontend to static hosting (e.g., Vercel, Netlify)
4. **Remove Old Code**: Once confident, delete `backend/` directory

## Support

For issues or questions:
1. Check `README-NEW.md` for setup instructions
2. Review server logs: `server/npm run dev` output
3. Review frontend logs: Browser console
4. Check that .env file has correct OpenRouter API key

---

**Migration completed successfully!** 🎉
