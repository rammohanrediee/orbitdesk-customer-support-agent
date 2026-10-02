"""Relational persistence for support tickets, RAG decisions, and reviews."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import create_engine, inspect, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload, Session

from orbitdesk_support_agent.model_config import MAX_RETRIEVED_RECORDS
from orbitdesk_support_agent.schemas import EvidenceRecord


class TicketNotFound(Exception):
    pass


class TicketAlreadyReviewed(Exception):
    pass


class Base(DeclarativeBase):
    pass


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'edited', 'escalated')", name="ticket_status_valid"),
        Index("ix_tickets_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decision: Mapped[Decision] = relationship(back_populates="ticket", uselist=False, cascade="all, delete-orphan")
    review: Mapped[Review | None] = relationship(back_populates="ticket", uselist=False, cascade="all, delete-orphan")


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint("action IN ('ANSWER', 'ESCALATE', 'CLARIFY', 'SAFE_FAILURE')", name="decision_action_valid"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), unique=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    requires_human: Mapped[bool] = mapped_column(Boolean, nullable=False)
    clarification_question: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    retrieval_strategy: Mapped[str | None] = mapped_column(String(30))
    retrieval_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(30), nullable=False)
    verification_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_log: Mapped[list] = mapped_column(JSON, nullable=False)
    trace: Mapped[dict] = mapped_column(JSON, nullable=False)
    latency_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ticket: Mapped[Ticket] = relationship(back_populates="decision")
    citations: Mapped[list[Citation]] = relationship(back_populates="decision", cascade="all, delete-orphan", order_by="Citation.position")


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (Index("ix_citations_decision_id", "decision_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    passage: Mapped[str] = mapped_column(Text, nullable=False)
    claim: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[Decision] = relationship(back_populates="citations")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("action IN ('approve', 'edit', 'escalate')", name="review_action_valid"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), unique=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    final_answer: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ticket: Mapped[Ticket] = relationship(back_populates="review")


def _database_url(value: str | Path) -> str:
    return f"sqlite:///{value}" if isinstance(value, Path) else value


@lru_cache(maxsize=16)
def _engine(url: str):
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        from alembic import command
        from alembic.config import Config

        inspector = inspect(engine)
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        config.attributes["explicit_url"] = True
        if inspector.has_table("tickets") and not inspector.has_table("alembic_version"):
            columns = {column["name"] for column in inspector.get_columns("tickets")}
            if "generated_result" in columns:
                raise ValueError(
                    "Legacy SQLite ticket database detected. Keep this file as a backup "
                    "and use a new ORBITDESK_DATABASE_URL; the old schema is not auto-migrated."
                )
            command.stamp(config, "head")
        else:
            command.upgrade(config, "head")
    return engine


class TicketStore:
    def __init__(self, database_url: str | Path):
        self.engine = _engine(_database_url(database_url))

    @staticmethod
    def _decision(decision: Decision) -> dict:
        return {
            "id": decision.id,
            "action": decision.action,
            "classification": decision.classification,
            "answer": decision.answer,
            "reason_code": decision.reason_code,
            "reason": decision.reason,
            "model_name": decision.model_name,
            "retrieval_strategy": decision.retrieval_strategy,
            "retrieval_top_k": decision.retrieval_top_k,
            "pipeline_version": decision.pipeline_version,
            "verification_passed": decision.verification_passed,
            "created_at": decision.created_at.isoformat(),
            "citations": [
                {
                    "source_id": citation.source_id,
                    "source_title": citation.source_title,
                    "source_type": citation.source_type,
                    "passage": citation.passage,
                    "claim": citation.claim,
                }
                for citation in decision.citations
            ],
        }

    @classmethod
    def _ticket(cls, ticket: Ticket) -> dict:
        decision = ticket.decision
        review = ticket.review
        citations = cls._decision(decision)["citations"]
        return {
            "id": ticket.id,
            "question": ticket.question,
            "status": ticket.status,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "reviewed_at": review.created_at.isoformat() if review else None,
            "final_answer": review.final_answer if review else None,
            "review_note": review.note if review else None,
            "decision": cls._decision(decision),
            "generated_result": {
                "response": {
                    "classification": decision.classification,
                    "answer": decision.answer,
                    "sources": citations,
                    "confidence": decision.confidence,
                    "requires_human": decision.requires_human,
                    "reason_code": decision.reason_code,
                    "reason": decision.reason,
                    "clarification_question": decision.clarification_question,
                    "warnings": decision.warnings,
                },
                "execution_log": decision.execution_log,
                "retrieval_mode": decision.retrieval_strategy,
                "model": decision.model_name,
                "trace": decision.trace,
                "latency_seconds": decision.latency_seconds,
            },
        }

    @staticmethod
    def _statement():
        return select(Ticket).options(
            selectinload(Ticket.decision).selectinload(Decision.citations),
            selectinload(Ticket.review),
        )

    def create(self, question: str, generated_result: dict, records: list[EvidenceRecord] | None = None) -> dict:
        now = datetime.now(UTC)
        response = generated_result["response"]
        classification = response["classification"]
        action = (
            "ANSWER" if classification == "answerable"
            else "ESCALATE" if classification == "requires_escalation"
            else "CLARIFY" if classification == "requires_clarification"
            else "SAFE_FAILURE"
        )
        ticket_id = uuid4().hex
        record_by_id = {record["source_id"]: record for record in records or []}
        citations = []
        for position, source in enumerate(response["sources"]):
            record = record_by_id.get(source["source_id"])
            citations.append(Citation(
                id=uuid4().hex,
                position=position,
                source_id=source["source_id"],
                source_title=record["title"] if record else source.get("source_title", source["source_id"]),
                source_type=record["source_type"] if record else source.get("source_type", "unknown"),
                passage=source["passage"],
                claim=source.get("claim"),
            ))
        decision = Decision(
            id=uuid4().hex,
            action=action,
            classification=classification,
            answer=response["answer"],
            reason_code=response.get("reason_code"),
            reason=response["reason"],
            confidence=response["confidence"],
            requires_human=response["requires_human"],
            clarification_question=response.get("clarification_question"),
            warnings=response.get("warnings", []),
            model_name=generated_result["model"],
            retrieval_strategy=generated_result["retrieval_mode"],
            retrieval_top_k=MAX_RETRIEVED_RECORDS,
            pipeline_version="v1",
            verification_passed="verify:passed" in generated_result["execution_log"],
            execution_log=generated_result["execution_log"],
            trace=generated_result["trace"],
            latency_seconds=generated_result["latency_seconds"],
            created_at=now,
            citations=citations,
        )
        with Session(self.engine) as session:
            session.add(Ticket(id=ticket_id, question=question, status="pending", created_at=now, updated_at=now, decision=decision))
            session.commit()
        return self.get(ticket_id)

    def list_recent(self, limit: int = 50) -> list[dict]:
        with Session(self.engine) as session:
            tickets = session.scalars(
                self._statement().order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(limit)
            ).all()
            return [self._ticket(ticket) for ticket in tickets]

    def get(self, ticket_id: str) -> dict:
        with Session(self.engine) as session:
            ticket = session.scalar(self._statement().where(Ticket.id == ticket_id))
            if ticket is None:
                raise TicketNotFound(ticket_id)
            return self._ticket(ticket)

    def decision(self, ticket_id: str) -> dict:
        return self.get(ticket_id)["decision"]

    def review(self, ticket_id: str, action: str, answer: str | None, note: str | None) -> dict:
        status = "approved" if action == "approve" else "edited" if action == "edit" else "escalated"
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            changed = session.execute(
                update(Ticket).where(Ticket.id == ticket_id, Ticket.status == "pending")
                .values(status=status, updated_at=now)
            ).rowcount
            if not changed:
                if session.get(Ticket, ticket_id) is None:
                    raise TicketNotFound(ticket_id)
                raise TicketAlreadyReviewed(ticket_id)
            decision = session.scalar(select(Decision).where(Decision.ticket_id == ticket_id))
            final_answer = decision.answer if action == "approve" else answer if action == "edit" else None
            session.add(Review(
                id=uuid4().hex,
                ticket_id=ticket_id,
                action=action,
                final_answer=final_answer,
                note=note,
                created_at=now,
            ))
            session.commit()
        return self.get(ticket_id)

    def prune_reviewed_before(self, cutoff: datetime, *, apply: bool) -> dict[str, int]:
        """Select expired reviewed tickets; pending tickets are never pruned."""
        with Session(self.engine) as session:
            expired = session.scalars(
                select(Ticket).where(Ticket.status != "pending", Ticket.updated_at < cutoff)
            ).all()
            eligible_count = len(expired)
            if apply:
                for ticket in expired:
                    session.delete(ticket)
                session.commit()
            return {
                "eligible_count": eligible_count,
                "deleted_count": eligible_count if apply else 0,
            }
