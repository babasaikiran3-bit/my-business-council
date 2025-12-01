"""FastAPI backend for LLM Council."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from .council import (
    stage1_collect_responses,
    stage2_collect_evaluations,
    calculate_scoreboard
)

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Stage1Request(BaseModel):
    question: str


class Stage2Request(BaseModel):
    question: str
    stage1_results: List[Dict[str, Any]]


class Stage3Request(BaseModel):
    stage2_results: List[Dict[str, Any]]
    label_to_model: Dict[str, str]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.post("/api/evaluate/stage1")
async def evaluate_stage1(request: Stage1Request):
    """Stage 1: Collect individual responses."""
    results = await stage1_collect_responses(request.question)
    return {"stage1": results}


@app.post("/api/evaluate/stage2")
async def evaluate_stage2(request: Stage2Request):
    """Stage 2: Peer evaluations."""
    results, label_to_model = await stage2_collect_evaluations(
        request.question,
        request.stage1_results
    )
    return {
        "stage2": results,
        "metadata": {"label_to_model": label_to_model}
    }


@app.post("/api/evaluate/stage3")
async def evaluate_stage3(request: Stage3Request):
    """Stage 3: Scoreboard aggregation."""
    scoreboard = calculate_scoreboard(
        request.stage2_results,
        request.label_to_model
    )
    return {"stage3": scoreboard}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
