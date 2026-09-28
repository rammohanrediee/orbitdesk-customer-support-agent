"""HTTP boundary for the OrbitDesk support workflow."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from orbitdesk_support_agent.graph import build_graph
from orbitdesk_support_agent.indexer import build_evidence_records
from orbitdesk_support_agent.loader import (
    load_knowledge_base,
    load_resolved_cases,
)
from orbitdesk_support_agent.nodes import MAX_WORKFLOW_RETRIES
from orbitdesk_support_agent.openrouter_llm import (
    DEFAULT_OPENROUTER_MODEL,
    OpenRouterLanguageModel,
)
from orbitdesk_support_agent.retriever import KeywordRetriever
from orbitdesk_support_agent.schemas import EvidenceRecord
from orbitdesk_support_agent.trace import record_trace_event, request_trace


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


class SupportRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)
    retrieval: Literal["keyword", "semantic"] = "keyword"


class SupportResult(BaseModel):
    response: dict[str, Any]
    execution_log: list[str]
    retrieval_mode: str | None
    model: str
    trace: dict[str, Any]
    latency_seconds: float


class HealthResult(BaseModel):
    status: Literal["ready", "configuration_required"]
    model: str
    api_key_configured: bool


def _allowed_origins() -> list[str]:
    configured = os.getenv("ORBITDESK_ALLOWED_ORIGINS", "")
    if not configured.strip():
        return list(DEFAULT_ALLOWED_ORIGINS)
    return [
        origin.strip()
        for origin in configured.split(",")
        if origin.strip()
    ]


@lru_cache(maxsize=1)
def load_evidence_records() -> tuple[EvidenceRecord, ...]:
    documents = load_knowledge_base(PROJECT_ROOT / "knowledge_base")
    cases = load_resolved_cases(PROJECT_ROOT / "resolved_cases.json")
    return tuple(build_evidence_records(documents, cases))


def build_runtime(retrieval: str):
    records = list(load_evidence_records())
    if retrieval == "semantic":
        try:
            from orbitdesk_support_agent.semantic_retriever import (
                SemanticRetriever,
            )
        except ImportError as error:
            raise ValueError(
                "Semantic retrieval is not installed on this server."
            ) from error
        retriever = SemanticRetriever(records)
    else:
        retriever = KeywordRetriever(records)

    llm = OpenRouterLanguageModel()
    return records, llm, build_graph(llm=llm, semantic_retriever=retriever)


def run_support_workflow(payload: SupportRequest) -> SupportResult:
    timeout_seconds = float(
        os.getenv("ORBITDESK_WORKFLOW_TIMEOUT_SECONDS", "60")
    )
    if timeout_seconds <= 0:
        raise ValueError("Workflow timeout must be positive.")

    records, llm, graph = build_runtime(payload.retrieval)
    started_at = perf_counter()

    with request_trace(timeout_seconds=timeout_seconds) as trace:
        record_trace_event(
            "request.started",
            question_chars=len(payload.question),
            retrieval_mode=payload.retrieval,
        )
        final_state = graph.invoke(
            {
                "question": payload.question.strip(),
                "all_records": records,
                "retry_count": 0,
                "max_retries": MAX_WORKFLOW_RETRIES,
                "execution_log": [],
                "verification_issues": [],
            }
        )
        response = final_state.get("response")
        record_trace_event(
            "request.completed",
            classification=(
                response.classification if response is not None else "missing"
            ),
            retry_count=final_state.get("retry_count", 0),
        )

    if response is None:
        raise RuntimeError("The support workflow returned no response.")

    return SupportResult(
        response=response.model_dump(mode="json"),
        execution_log=list(final_state.get("execution_log", [])),
        retrieval_mode=final_state.get("retrieval_mode"),
        model=llm.config.model,
        trace=trace.to_dict(),
        latency_seconds=round(perf_counter() - started_at, 3),
    )


app = FastAPI(
    title="OrbitDesk Support API",
    version="0.3.0",
    docs_url="/api/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health", response_model=HealthResult)
def health() -> HealthResult:
    configured = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
    return HealthResult(
        status="ready" if configured else "configuration_required",
        model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        api_key_configured=configured,
    )


@app.post("/api/support", response_model=SupportResult)
def support(payload: SupportRequest) -> SupportResult:
    try:
        return run_support_workflow(payload)
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="The support workflow could not complete safely.",
        ) from error


def main() -> None:
    """Run the local API server through the installed console command."""
    import uvicorn

    uvicorn.run(
        "orbitdesk_support_agent.api:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
