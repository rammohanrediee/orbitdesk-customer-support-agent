from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel,Field

Classification = Literal[
    "answerable",
    "requires_clarification",
    "out_of_scope",
    "safe_failure",
    "requires_escalation",
]

TriageClassification = Literal[
    "answerable",
    "requires_clarification",
    "requires_escalation",
    "out_of_scope",
]

RetrievalMode = Literal["semantic", "keyword"]


class Source(TypedDict):
    source_id: str
    passage: str


class KnowledgeDocument(TypedDict):
    document_id: str
    title: str
    updated: str
    status: str
    tags: list[str]
    content: str
    source_file: str


class ResolvedCase(TypedDict):
    case_id: str
    status: str
    product_version: str
    title: str
    symptoms: list[str]
    resolution: list[str]
    source_documents: list[str]
    important_limit: NotRequired[str]
    superseded_reason: NotRequired[str]

class EvidenceRecord(TypedDict):
    source_id: str
    source_type:Literal["knowledge_base","resolved_case"]
    title:str
    text:str
    status:str

class SourceReference(BaseModel):
    source_id: str=Field(min_length=1, max_length=100)
    passage: str=Field(min_length=1, max_length=500)


class GeneratedAnswer(BaseModel):
    answer: str=Field(min_length=1, max_length=2_000)
    citations: list[SourceReference]=Field(min_length=1, max_length=4)
    confidence: float=Field(ge=0, le=1)

class SupportResponse(BaseModel):
    classification: Classification
    answer:str=Field(min_length=1)
    sources:list[SourceReference]
    confidence:float=Field(ge=0,le=1)
    requires_human:bool
    reason:str=Field(min_length=1)
    clarification_question:str|None=None
    warnings:list[str]=Field(default_factory=list)


class VerificationResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)

class TriageResult(BaseModel):
    classification: TriageClassification
    reason: str=Field(min_length=1)
    clarification_question: str | None = None
