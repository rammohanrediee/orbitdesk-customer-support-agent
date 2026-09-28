import json
from pathlib import Path
import yaml

from orbitdesk_support_agent.schemas import KnowledgeDocument, ResolvedCase


ALLOWED_DOCUMENT_STATUSES = frozenset({"current", "superseded"})
ALLOWED_CASE_STATUSES = frozenset(
    {"current", "resolved", "escalated", "superseded"}
)
MAX_DOCUMENT_BYTES = 64 * 1024
MAX_DOCUMENTS = 500
MAX_CASE_FILE_BYTES = 2 * 1024 * 1024
MAX_CASES = 1_000


def _read_bounded_text(file_path: Path, max_bytes: int) -> str:
    size = file_path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"{file_path.name} exceeds the {max_bytes}-byte size limit."
        )
    return file_path.read_text(encoding="utf-8")


def _required_text(
    value: object,
    *,
    field_name: str,
    source_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{source_name} requires a non-empty {field_name}."
        )
    return value.strip()


def _string_list(
    value: object,
    *,
    field_name: str,
    source_name: str,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(
            f"{source_name} field {field_name} must be a list of strings."
        )
    if not allow_empty and not value:
        raise ValueError(
            f"{source_name} field {field_name} must not be empty."
        )
    return [item.strip() for item in value]


def _status(
    value: object,
    source_name: str,
    allowed_statuses: frozenset[str],
) -> str:
    status = _required_text(
        value,
        field_name="status",
        source_name=source_name,
    )
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ValueError(
            f"Invalid status in {source_name}; expected one of: {allowed}."
        )
    return status


def load_knowledge_base(directory: Path) -> list[KnowledgeDocument]:
    if not directory.is_dir():
        raise FileNotFoundError(
            f"Knowledge-base directory not found: {directory}"
        )

    file_paths = sorted(directory.glob("*.md"))
    if len(file_paths) > MAX_DOCUMENTS:
        raise ValueError(
            f"Knowledge base exceeds the {MAX_DOCUMENTS}-document limit."
        )

    documents: list[KnowledgeDocument] = []
    seen_ids: set[str] = set()

    for file_path in file_paths:
        raw_text = _read_bounded_text(file_path, MAX_DOCUMENT_BYTES)

        parts = raw_text.split("---", maxsplit=2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid front matter in {file_path.name}"
            )

        metadata = yaml.safe_load(parts[1])
        if not isinstance(metadata, dict):
            raise ValueError(
                f"Front matter in {file_path.name} must be an object."
            )
        content = parts[2].strip()
        if not content:
            raise ValueError(f"Document content is empty in {file_path.name}.")

        document_id = _required_text(
            metadata.get("document_id"),
            field_name="document_id",
            source_name=file_path.name,
        )
        if document_id in seen_ids:
            raise ValueError(f"Duplicate document_id: {document_id}")
        seen_ids.add(document_id)

        document: KnowledgeDocument = {
            "document_id": document_id,
            "title": _required_text(
                metadata.get("title"),
                field_name="title",
                source_name=file_path.name,
            ),
            "updated": _required_text(
                str(metadata.get("updated", "")),
                field_name="updated",
                source_name=file_path.name,
            ),
            "status": _status(
                metadata.get("status"),
                file_path.name,
                ALLOWED_DOCUMENT_STATUSES,
            ),
            "tags": _string_list(
                metadata.get("tags"),
                field_name="tags",
                source_name=file_path.name,
                allow_empty=True,
            ),
            "content": content,
            "source_file": file_path.name,
        }

        documents.append(document)

    return documents


def load_resolved_cases(file_path: Path) -> list[ResolvedCase]:
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Resolved-cases file not found: {file_path}"
        )

    data = json.loads(
        _read_bounded_text(file_path, MAX_CASE_FILE_BYTES)
    )
    if not isinstance(data, dict):
        raise ValueError(f"Expected an object in {file_path.name}")
    cases = data.get("cases")

    if not isinstance(cases, list):
        raise ValueError(
            f"Expected a 'cases' list in {file_path.name}"
        )

    if len(cases) > MAX_CASES:
        raise ValueError(
            f"Resolved cases exceed the {MAX_CASES}-case limit."
        )

    validated_cases: list[ResolvedCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(cases):
        source_name = f"{file_path.name} case {index + 1}"
        if not isinstance(raw_case, dict):
            raise ValueError(f"{source_name} must be an object.")

        case_id = _required_text(
            raw_case.get("case_id"),
            field_name="case_id",
            source_name=source_name,
        )
        if case_id in seen_ids:
            raise ValueError(f"Duplicate case_id: {case_id}")
        seen_ids.add(case_id)

        validated: ResolvedCase = {
            "case_id": case_id,
            "status": _status(
                raw_case.get("status"),
                source_name,
                ALLOWED_CASE_STATUSES,
            ),
            "product_version": _required_text(
                raw_case.get("product_version"),
                field_name="product_version",
                source_name=source_name,
            ),
            "title": _required_text(
                raw_case.get("title"),
                field_name="title",
                source_name=source_name,
            ),
            "symptoms": _string_list(
                raw_case.get("symptoms"),
                field_name="symptoms",
                source_name=source_name,
            ),
            "resolution": _string_list(
                raw_case.get("resolution"),
                field_name="resolution",
                source_name=source_name,
            ),
            "source_documents": _string_list(
                raw_case.get("source_documents"),
                field_name="source_documents",
                source_name=source_name,
            ),
        }
        if important_limit := raw_case.get("important_limit"):
            validated["important_limit"] = _required_text(
                important_limit,
                field_name="important_limit",
                source_name=source_name,
            )
        if superseded_reason := raw_case.get("superseded_reason"):
            validated["superseded_reason"] = _required_text(
                superseded_reason,
                field_name="superseded_reason",
                source_name=source_name,
            )
        validated_cases.append(validated)

    return validated_cases
