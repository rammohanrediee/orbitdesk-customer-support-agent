"""HTTP boundary for the OrbitDesk support workflow."""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
import hmac
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import inspect, text

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
from orbitdesk_support_agent.tickets import TicketAlreadyReviewed, TicketNotFound, TicketStore


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
DEFAULT_RETRIEVAL_MODE = "keyword"


class SupportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=2_000)


class SupportResult(BaseModel):
    response: dict[str, Any]
    execution_log: list[str]
    retrieval_mode: str | None
    model: str
    trace: dict[str, Any]
    latency_seconds: float


class HealthResult(BaseModel):
    status: Literal["ready", "configuration_required", "unavailable"]
    model: str
    api_key_configured: bool
    retrieval_mode: str
    demo_mode: bool = False
    database_ready: bool
    auth_required: bool


class EvidenceResult(BaseModel):
    source_id: str
    source_type: str
    title: str
    text: str
    status: str


class TicketResult(BaseModel):
    id: str
    question: str
    generated_result: SupportResult
    status: Literal["pending", "approved", "edited", "escalated"]
    final_answer: str | None
    review_note: str | None
    created_at: str
    reviewed_at: str | None
    updated_at: str
    decision: dict[str, Any]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "edit", "escalate"]
    answer: str | None = Field(default=None, max_length=2_000)
    note: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_decision(self) -> "ReviewRequest":
        if self.action == "edit" and not (self.answer or "").strip():
            raise ValueError("An edited answer is required.")
        if self.action == "escalate" and not (self.note or "").strip():
            raise ValueError("An escalation note is required.")
        return self


def ticket_store() -> TicketStore:
    configured = os.getenv("ORBITDESK_DATABASE_URL")
    if configured:
        return TicketStore(configured)
    path = Path(os.getenv("ORBITDESK_TICKET_DB", PROJECT_ROOT / "artifacts" / "orbitdesk-v2.sqlite3"))
    return TicketStore(path)


class DemoQuestionNotFound(ValueError):
    pass


def demo_mode() -> bool:
    return os.getenv("ORBITDESK_DEMO_MODE", "").strip() == "1"


def validate_startup_config() -> None:
    """Fail before serving requests when production secrets or storage are absent."""
    _configured_retrieval_mode()
    environment = os.getenv("ORBITDESK_ENV", "development").strip().lower()
    if environment not in {"development", "production"}:
        raise ValueError("ORBITDESK_ENV must be development or production.")
    if environment == "production":
        url = os.getenv("ORBITDESK_DATABASE_URL", "")
        if not url.startswith(("postgresql+psycopg://", "postgresql://")):
            raise ValueError("Production requires a PostgreSQL ORBITDESK_DATABASE_URL.")
        if demo_mode():
            raise ValueError("ORBITDESK_DEMO_MODE must be disabled in production.")
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key or key == "replace-me":
            raise ValueError("Production requires OPENROUTER_API_KEY.")
        if not os.getenv("ORBITDESK_ALLOWED_ORIGINS", "").strip():
            raise ValueError("Production requires ORBITDESK_ALLOWED_ORIGINS.")
        if len(os.getenv("ORBITDESK_OPERATOR_TOKEN", "")) < 24:
            raise ValueError("Production requires ORBITDESK_OPERATOR_TOKEN with at least 24 characters.")
        retention_days = os.getenv("ORBITDESK_RETENTION_DAYS", "")
        if not retention_days.isdigit() or int(retention_days) <= 0:
            raise ValueError("Production requires a positive ORBITDESK_RETENTION_DAYS.")


def require_operator_token(x_orbitdesk_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("ORBITDESK_OPERATOR_TOKEN", "")
    if expected and not hmac.compare_digest(x_orbitdesk_token or "", expected):
        raise HTTPException(status_code=401, detail="Operator access required.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_startup_config()
    with ticket_store().engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        if not inspect(connection).has_table("tickets"):
            raise RuntimeError("Database schema missing; run alembic upgrade head.")
    yield


@lru_cache(maxsize=1)
def recorded_demo_outputs() -> list[dict[str, Any]]:
    return json.loads((PROJECT_ROOT / "sample_outputs.json").read_text(encoding="utf-8"))


def _allowed_origins() -> list[str]:
    configured = os.getenv("ORBITDESK_ALLOWED_ORIGINS", "")
    if not configured.strip():
        return list(DEFAULT_ALLOWED_ORIGINS)
    return [
        origin.strip()
        for origin in configured.split(",")
        if origin.strip()
    ]


def _configured_retrieval_mode() -> Literal["keyword", "semantic"]:
    """Return the operator-selected retrieval strategy.

    Retrieval is an application concern, not an end-user decision. Keeping the
    choice server-side also prevents unsupported modes from reaching runtime.
    """
    mode = os.getenv(
        "ORBITDESK_RETRIEVAL_MODE",
        DEFAULT_RETRIEVAL_MODE,
    ).strip().lower()
    if mode not in {"keyword", "semantic"}:
        raise ValueError(
            "ORBITDESK_RETRIEVAL_MODE must be 'keyword' or 'semantic'."
        )
    return cast(Literal["keyword", "semantic"], mode)


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
    if demo_mode():
        for output in recorded_demo_outputs():
            if output["question"] == payload.question.strip():
                return SupportResult(
                    response=output["response"],
                    execution_log=output["execution_log"],
                    retrieval_mode=output["retrieval_mode"],
                    model="recorded-demo",
                    trace={"trace_id": f"demo-{output['question_id']}", "events": []},
                    latency_seconds=0.0,
                )
        raise DemoQuestionNotFound("Choose one of the recorded demo questions.")

    timeout_seconds = float(
        os.getenv("ORBITDESK_WORKFLOW_TIMEOUT_SECONDS", "60")
    )
    if timeout_seconds <= 0:
        raise ValueError("Workflow timeout must be positive.")

    retrieval_mode = _configured_retrieval_mode()
    records, llm, graph = build_runtime(retrieval_mode)
    started_at = perf_counter()

    with request_trace(timeout_seconds=timeout_seconds) as trace:
        record_trace_event(
            "request.started",
            question_chars=len(payload.question),
            retrieval_mode=retrieval_mode,
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
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-OrbitDesk-Token"],
)


@app.get("/api/health", response_model=HealthResult)
def health(response: Response) -> HealthResult:
    is_demo = demo_mode()
    api_key_configured = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
    try:
        retrieval_mode = _configured_retrieval_mode()
        retrieval_configured = True
    except ValueError:
        retrieval_mode = "invalid"
        retrieval_configured = False
    try:
        with ticket_store().engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            database_ready = inspect(connection).has_table("tickets")
    except Exception:
        database_ready = False
        response.status_code = 503
    return HealthResult(
        status=(
            "unavailable" if not database_ready
            else "ready" if (api_key_configured or is_demo) and retrieval_configured
            else "configuration_required"
        ),
        model="recorded-demo" if is_demo else os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        api_key_configured=api_key_configured,
        retrieval_mode=retrieval_mode,
        demo_mode=is_demo,
        database_ready=database_ready,
        auth_required=bool(os.getenv("ORBITDESK_OPERATOR_TOKEN", "")),
    )


@app.get("/api/demo-questions")
def demo_questions() -> list[dict[str, str]]:
    if not demo_mode():
        return []
    return [
        {"question_id": output["question_id"], "question": output["question"]}
        for output in recorded_demo_outputs()
    ]


@app.post("/api/support", response_model=SupportResult, dependencies=[Depends(require_operator_token)])
def support(payload: SupportRequest) -> SupportResult:
    try:
        return run_support_workflow(payload)
    except DemoQuestionNotFound as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="The support workflow could not complete safely.",
        ) from error


@app.post("/api/tickets", response_model=TicketResult, status_code=201, dependencies=[Depends(require_operator_token)])
def create_ticket(payload: SupportRequest) -> dict:
    try:
        result = run_support_workflow(payload)
        return ticket_store().create(
            payload.question.strip(),
            result.model_dump(mode="json"),
            list(load_evidence_records()),
        )
    except DemoQuestionNotFound as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="The ticket could not be created safely.") from error


@app.get("/api/tickets", response_model=list[TicketResult], dependencies=[Depends(require_operator_token)])
def list_tickets() -> list[dict]:
    return ticket_store().list_recent()


@app.get("/api/evidence/{source_id}", response_model=EvidenceResult, dependencies=[Depends(require_operator_token)])
def get_evidence(source_id: str) -> EvidenceRecord:
    for record in load_evidence_records():
        if record["source_id"] == source_id and record["status"] != "superseded":
            return record
    raise HTTPException(status_code=404, detail="Evidence source not found.")


@app.get("/api/tickets/{ticket_id}", response_model=TicketResult, dependencies=[Depends(require_operator_token)])
def get_ticket(ticket_id: str) -> dict:
    try:
        return ticket_store().get(ticket_id)
    except TicketNotFound as error:
        raise HTTPException(status_code=404, detail="Ticket not found.") from error


@app.get("/api/tickets/{ticket_id}/decision", dependencies=[Depends(require_operator_token)])
def get_ticket_decision(ticket_id: str) -> dict:
    try:
        return ticket_store().decision(ticket_id)
    except TicketNotFound as error:
        raise HTTPException(status_code=404, detail="Ticket not found.") from error


@app.patch("/api/tickets/{ticket_id}/review", response_model=TicketResult, dependencies=[Depends(require_operator_token)])
def review_ticket(ticket_id: str, payload: ReviewRequest) -> dict:
    try:
        return ticket_store().review(
            ticket_id,
            payload.action,
            payload.answer.strip() if payload.answer else None,
            payload.note.strip() if payload.note else None,
        )
    except TicketNotFound as error:
        raise HTTPException(status_code=404, detail="Ticket not found.") from error
    except TicketAlreadyReviewed as error:
        raise HTTPException(status_code=409, detail="This ticket has already been reviewed.") from error


frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


def main() -> None:
    """Run the local API server through the installed console command."""
    import uvicorn

    uvicorn.run(
        "orbitdesk_support_agent.api:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
