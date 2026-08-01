from orbitdesk_support_agent.schemas import EvidenceRecord, KnowledgeDocument, ResolvedCase

def build_evidence_records(documents:list[KnowledgeDocument],
                           cases:list[ResolvedCase],
                           )->list[EvidenceRecord]:
    records:list[EvidenceRecord]=[]

    for document in documents:
        tags=" ,".join(document["tags"])
        text=(
            f"Title: {document['title']}\n"
            f"Tags: {tags}\n\n"
            f"{document['content']}"
        )

        records.append(
            {
                "source_id": document["document_id"],
                "source_type": "knowledge_base",
                "title": document["title"],
                "text": text,
                "status": document["status"],
            }
        )

    for case in cases:
        symptoms = "\n".join(
            f"- {symptom}" for symptom in case["symptoms"]
        )
        resolution = "\n".join(
            f"- {step}" for step in case["resolution"]
        )

        text_parts = [
            f"Title: {case['title']}",
            f"Symptoms:\n{symptoms}",
            f"Resolution:\n{resolution}",
        ]

        if important_limit := case.get("important_limit"):
            text_parts.append(f"Important limit: {important_limit}")

        if superseded_reason := case.get("superseded_reason"):
            text_parts.append(
                f"Superseded reason: {superseded_reason}"
            )

        records.append(
            {
                "source_id": case["case_id"],
                "source_type": "resolved_case",
                "title": case["title"],
                "text": "\n\n".join(text_parts),
                "status": case["status"],
            }
        )

    return records
    