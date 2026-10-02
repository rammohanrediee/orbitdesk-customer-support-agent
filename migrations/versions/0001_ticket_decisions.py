"""Create ticket, decision, citation, and review tables.

Revision ID: 0001_ticket_decisions
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_ticket_decisions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'edited', 'escalated')", name="ticket_status_valid"),
    )
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("ticket_id", sa.String(32), sa.ForeignKey("tickets.id"), unique=True, nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.String(50)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("requires_human", sa.Boolean(), nullable=False),
        sa.Column("clarification_question", sa.Text()),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("retrieval_strategy", sa.String(30)),
        sa.Column("retrieval_top_k", sa.Integer(), nullable=False),
        sa.Column("pipeline_version", sa.String(30), nullable=False),
        sa.Column("verification_passed", sa.Boolean(), nullable=False),
        sa.Column("execution_log", sa.JSON(), nullable=False),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.Column("latency_seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('ANSWER', 'ESCALATE', 'CLARIFY', 'SAFE_FAILURE')", name="decision_action_valid"),
    )
    op.create_table(
        "citations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("decision_id", sa.String(32), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("source_title", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("passage", sa.Text(), nullable=False),
        sa.Column("claim", sa.Text()),
    )
    op.create_index("ix_citations_decision_id", "citations", ["decision_id"])
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("ticket_id", sa.String(32), sa.ForeignKey("tickets.id"), unique=True, nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("final_answer", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('approve', 'edit', 'escalate')", name="review_action_valid"),
    )


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_index("ix_citations_decision_id", table_name="citations")
    op.drop_table("citations")
    op.drop_table("decisions")
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_table("tickets")
