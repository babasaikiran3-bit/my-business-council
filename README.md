# Parenting Roundtable

![parenting roundtable](header.jpg)

Born from a real 2am panic — an infant with a 38.1°C fever, parents Googling frantically, every result disagreeing, and a single LLM just regurgitating the internet. **Parenting Roundtable** is a local web app that answers pediatric/parenting questions by first gathering the *latest, scientifically-proven sources* and then having a panel of LLMs reason from that shared evidence. The goal: balanced, evidence-based answers **with the sources**, and a Chairman that is careful but decisive — safety first, then one clear action.

The decisive difference from a generic multi-LLM tool is **Stage 0**: a dedicated source-of-truth web-search agent (Exa, restricted to a strict allowlist of trusted medical domains — AAP, WHO, CDC, NHS, Cochrane, PubMed, Mayo, …) runs *first*. Its real citations become the canonical **Sources**, and the council cites only those — no "citing from memory," no fabricated health links.

In a bit more detail, here is what happens when you submit a question (and your child's age):

0. **Stage 0: Source of truth**. A single searcher model queries the web (Exa) restricted to trusted medical/scientific domains and produces a neutral, advice-free **evidence brief** plus a deduped, allowlist-filtered list of real **sources**.
1. **Stage 1: First opinions**. Each council LLM answers the question grounded *only* in the Stage 0 evidence (no web access of its own), citing those real sources. Responses are shown in a tab view.
2. **Stage 2: Review**. Each LLM ranks the others' (anonymized) answers on scientific accuracy, source quality, safety/red-flag handling, age-appropriateness, and clarity for a worried parent.
3. **Stage 3: Final answer**. The Chairman synthesizes one careful-but-decisive answer — leading with a `> EMERGENCY:` callout when warranted (e.g. an infant under 3 months with a fever), explicit watch-wait vs. call-doctor vs. ER thresholds, and the consolidated, verified Sources.

> ⚕️ This is general information from AI based on cited medical sources — not a diagnosis or a substitute for professional care. Safety is enforced primarily through prompts plus one deterministic backstop (newborn + fever → emergency callout); it is not a certified medical device.

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

Edit `backend/config.py` to customize the searcher, council, chairman, and trusted domains:

```python
# Stage 0 researcher (web search). Perplexity Sonar is an alternative.
SEARCH_MODEL = "openai/gpt-5.1"

COUNCIL_MODELS = [
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Stage 0 web search is restricted to this allowlist of trusted medical domains.
TRUSTED_DOMAINS = ["healthychildren.org", "aap.org", "who.int", "cdc.gov", "nhs.uk", ...]
```

> Stage 0 uses OpenRouter's Exa web-search plugin (~$0.005/question) restricted to `TRUSTED_DOMAINS`. Citations are taken from the response `annotations` and allowlist-filtered server-side, so only trusted-domain URLs are ever shown.

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

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

- **Backend:** FastAPI (Python 3.10+), async httpx, OpenRouter API
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, npm for JavaScript
