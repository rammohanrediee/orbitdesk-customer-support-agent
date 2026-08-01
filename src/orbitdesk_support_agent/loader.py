import json
from pathlib import Path
import yaml

from orbitdesk_support_agent.schemas import KnowledgeDocument, ResolvedCase


def load_knowledge_base(directory: Path) -> list[KnowledgeDocument]:
    if not directory.is_dir():
        raise FileNotFoundError(
            f"Knowledge-base directory not found: {directory}"
        )

    documents: list[KnowledgeDocument] = []

    for file_path in sorted(directory.glob("*.md")):
        raw_text = file_path.read_text(encoding="utf-8")

        parts = raw_text.split("---", maxsplit=2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid front matter in {file_path.name}"
            )

        metadata = yaml.safe_load(parts[1])
        content = parts[2].strip()

        document_id = metadata.get("document_id")
        if not document_id:
            raise ValueError(
                f"Missing document_id in {file_path.name}"
            )

        document: KnowledgeDocument = {
            "document_id": document_id,
            "title": metadata.get("title", ""),
            "updated": str(metadata.get("updated", "")),
            "status": metadata.get("status", ""),
            "tags": metadata.get("tags", []),
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

    data = json.loads(file_path.read_text(encoding="utf-8"))
    cases = data.get("cases")

    if not isinstance(cases, list):
        raise ValueError(
            f"Expected a 'cases' list in {file_path.name}"
        )

    return cases