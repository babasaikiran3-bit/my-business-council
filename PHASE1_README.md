# Phase 1: Customer Request Interface & Foundational Integration

This document describes the Phase 1 implementation of the AI-Powered DevOps Platform.

## What's New in Phase 1

Phase 1 establishes the foundation for the fully automated DevOps platform by implementing:

1. **Rube MCP Server Integration** - Replaces the Composio SDK with direct MCP protocol integration
2. **Customer Request API** - New endpoint for submitting feature requests and bug reports
3. **LLM Council Analysis** - Automated analysis of customer requests
4. **Linear Integration** - Automatic creation of Linear issues
5. **Customer Notifications** - Automated email confirmations

## Architecture

```
Customer Request (Web Form)
    ↓
FastAPI Endpoint (/api/customer-request)
    ↓
LLM Council Deliberation
    ├─ Stage 1: First Opinions (multiple models)
    ├─ Stage 2: Cross-Review
    └─ Stage 3: Synthesis
    ↓
Rube MCP Server
    ├─ Create Linear Issue
    └─ Send Email Notification
    ↓
Customer Receives Confirmation
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Backend dependencies
uv sync

# Frontend dependencies (unchanged)
cd frontend
npm install
cd ..
```

### 2. Configure Environment Variables

Copy the Phase 1 environment template:

```bash
cp .env.example.phase1 .env
```

Edit `.env` and add your API keys:

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...
RUBE_API_KEY=...
LINEAR_TEAM_ID=...
```

### 3. Set Up Rube MCP Server

1. Visit [https://rube.app](https://rube.app) and create an account
2. Generate an API key
3. Connect the following apps:
   - **Linear** (for issue creation)
   - **Gmail** (for customer notifications)
4. Copy your API key to the `.env` file

### 4. Set Up Linear

1. Log in to Linear
2. Go to Settings → Teams
3. Copy your team ID
4. Add it to the `.env` file

### 5. Run the Application

```bash
# Option 1: Use the start script
./start.sh

# Option 2: Run manually
# Terminal 1 (Backend)
uv run python -m backend.main

# Terminal 2 (Frontend)
cd frontend
npm run dev
```

## API Usage

### Submit a Customer Request

**Endpoint:** `POST /api/customer-request`

**Request Body:**
```json
{
  "email": "customer@example.com",
  "name": "John Doe",
  "request_type": "feature",
  "title": "Add dark mode",
  "description": "I would like to have a dark mode option in the app",
  "priority": "medium"
}
```

**Response:**
```json
{
  "success": true,
  "council_analysis": {
    "title": "Implement Dark Mode Theme Toggle",
    "description": "Add a dark mode theme...",
    "complexity": "medium",
    "assignment": "ai",
    "reasoning": "This is a well-defined UI feature..."
  },
  "linear_issue": {
    "success": true,
    "result": {
      "id": "issue-123",
      "url": "https://linear.app/..."
    }
  },
  "email_sent": {
    "success": true
  }
}
```

## Testing

### Test the Customer Request Flow

1. Start the backend and frontend
2. Use curl or Postman to submit a request:

```bash
curl -X POST http://localhost:8000/api/customer-request \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "Test User",
    "request_type": "feature",
    "title": "Test Feature",
    "description": "This is a test feature request",
    "priority": "medium"
  }'
```

3. Check:
   - The LLM Council analyzes the request
   - A new issue is created in Linear
   - An email is sent to the customer

## What's Next

Phase 2 will add:
- Automated task assignment (AI vs human)
- Claude Code integration for autonomous coding
- Automated PR creation
- LLM Council code review

## Troubleshooting

### "RUBE_API_KEY must be set"
- Make sure you've created a `.env` file
- Add your Rube API key to the file

### "Could not create Linear issue"
- Check that you've connected Linear in Rube
- Verify your Linear team ID is correct
- Make sure you have the necessary permissions

### "Could not send email"
- Check that you've connected Gmail in Rube
- Verify the recipient email address is valid
