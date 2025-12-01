# Architecture

## Overview
Cross-LLM evaluation system using peer review to score models on toxicity, bias, hallucinations, and political tilt.

## System Flow
```
User Query → Backend API → 3-Stage Process → Results
```

## Three Stages

### Stage 1: Collect Responses
- Send query to all models in parallel
- Each model generates independent response
- Returns: `[{model, response, error?}]`

### Stage 2: Peer Evaluation
- Anonymize responses (Response A, B, C...)
- Each model scores others on 4 criteria (0-10 scale):
  - **Toxicity**: 0=Safe, 10=Toxic
  - **Bias**: 0=Neutral, 10=Biased
  - **Hallucination**: 0=Factual, 10=Hallucinated
  - **Political Leaning**: 0=Neutral, 10=Extreme
- Models don't evaluate themselves
- Returns: `[{model, evaluation{}}]`

### Stage 3: Scoreboard
- De-anonymize evaluations
- Calculate average scores per model
- Sort by average (lower is better)
- Returns: `[{model, scores{}, average_score}]`

## Tech Stack

**Backend** (`/backend`)
- `main.py`: FastAPI server with 3 endpoints (`/api/evaluate/stage1`, `/stage2`, `/stage3`)
- `council.py`: Orchestration logic for 3 stages
- `openrouter.py`: HTTP client for OpenRouter API
- `config.py`: Model list and API settings

**Frontend** (`/frontend/src`)
- `App.jsx`: Progressive loading (stages appear as they complete)
- `CollapsibleSection.jsx`: Minimize/expand sections
- `Stage1.jsx`: Tabbed model responses
- `Stage2.jsx`: Peer evaluation scorecards
- `Stage3.jsx`: Final scoreboard table

## Key Design Principles

1. **Anonymization**: Prevents self-scoring bias
2. **Democratic**: No single judge model
3. **Progressive**: Results stream in stage-by-stage
4. **Transparent**: All raw evaluations visible
5. **Diverse**: 3+ models from different providers

## API Endpoints

```
POST /api/evaluate/stage1
Body: {question: string}
Returns: {stage1: [{model, response, error?}]}

POST /api/evaluate/stage2
Body: {question: string, stage1_results: [...]}
Returns: {stage2: [...], metadata: {label_to_model}}

POST /api/evaluate/stage3
Body: {stage2_results: [...], label_to_model: {}}
Returns: {stage3: [{model, scores, average_score}]}
```

## Configuration

**Models** (`backend/config.py`)
```python
COUNCIL_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "x-ai/grok-4.1-fast:free",
    "openai/gpt-oss-20b:free",
]
```

**Environment** (`.env`)
```
OPENROUTER_API_KEY=your_key_here
```

## Error Handling

- Models that fail show error message in UI
- Other models continue evaluation
- Stage 2 skips failed models
- Clear HTTP error messages (429, 503, etc.)
