# LLM Council & AI-Powered DevOps Platform

![llmcouncil](header.jpg)

This repository houses the **LLM Council**, a multi-model AI deliberation system, and the **Digital Connections** website, which serves as the frontend for our next-generation **AI-Powered DevOps Platform**.

## Overview

The core concept is to group multiple advanced LLMs (e.g., GPT-4, Claude 3.5 Sonnet, Gemini 1.5 Pro) into a "Council" that deliberates on complex problems. Instead of relying on a single model, the Council provides diverse perspectives, peer reviews each other's work, and synthesizes a superior final answer.

We are now evolving this concept into a fully automated DevOps platform where the Council acts as the central intelligence, orchestrating tools, writing code, and managing infrastructure.

### Key Features

1.  **Multi-Model Deliberation:**
    *   **Stage 1:** Individual models provide independent solutions.
    *   **Stage 2:** Models review and rank each other's solutions (anonymized).
    *   **Stage 3:** A "Chairman" model synthesizes the final, optimized solution.

2.  **Tool Integration (MCP):**
    *   Integrated with **Composio/Rube MCP Gateway** to access over 500 external tools (GitHub, Linear, Slack, etc.).
    *   Enables the Council to perform real-world actions, not just generate text.

3.  **Digital Connections Website:**
    *   A modern, business-focused frontend for the platform.
    *   Features a **Chat Interface** to the Council for strategic DevOps consultation.
    *   Showcases the "Connectedness through Technology" philosophy.

## AI-Powered DevOps Roadmap

We are building a comprehensive, end-to-end DevOps automation platform. See the detailed [**Implementation Plan**](docs/implementation_plan.md) for the full roadmap.

*   **Phase 1:** Customer Request Interface & Foundational Integration (Current Focus)
*   **Phase 2:** AI-Powered Development Automation (Claude Code Integration)
*   **Phase 3:** CI/CD and Automated Deployment
*   **Phase 4:** Monitoring and Automated Remediation
*   **Phase 5:** Design-to-Code Automation
*   **Phase 6:** Full Orchestration and Analytics

## Setup

### 1. Install Dependencies

**Backend (LLM Council):**

```bash
cd backend
pip install -r requirements.txt
cd ..
```

**Frontend (LLM Council Original):**

```bash
cd frontend
npm install
cd ..
```

**Digital Connections Website:**

```bash
cd digital-connections-web
pnpm install
cd ..
```

### 2. Configure API Keys

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Edit `.env` with your API keys for OpenRouter and Composio.

### 3. Running the Application

**LLM Council (Original):**
*   Backend: `python -m backend.main`
*   Frontend: `cd frontend && npm run dev`

**Digital Connections Website:**
*   `cd digital-connections-web && pnpm dev`

## Tech Stack

*   **Backend:** FastAPI (Python 3.10+), OpenRouter API, Composio SDK
*   **Frontend (Web):** React 19, Tailwind CSS 4, Shadcn UI, Framer Motion
*   **Orchestration:** n8n (planned), Rube MCP Server
*   **AI Models:** OpenAI, Anthropic, Google, xAI (via OpenRouter)
