import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from orbitdesk_support_agent.schemas import EvidenceRecord


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return {word for word in words if word not in ENGLISH_STOP_WORDS}


def calculate_score(
    question_tokens: set[str],
    record: EvidenceRecord,
) -> int:
    title_tokens = tokenize(record["title"])
    text_tokens = tokenize(record["text"])

    title_matches = question_tokens & title_tokens
    text_matches = question_tokens & text_tokens

    # Title matches are stronger indicators than body-text matches.
    return (len(title_matches) * 3) + len(text_matches)


def retrieve_evidence(
    question: str,
    records: list[EvidenceRecord],
    limit: int = 4,
) -> list[EvidenceRecord]:
    question_tokens = tokenize(question)

    if not question_tokens or limit <= 0:
        return []

    ranked_records: list[tuple[int, int, EvidenceRecord]] = []

    for record in records:
        if record["status"] == "superseded":
            continue

        score = calculate_score(question_tokens, record)

        if score <= 0:
            continue

        # Knowledge-base records win when relevance scores tie.
        source_priority = (
            1 if record["source_type"] == "knowledge_base" else 0
        )

        ranked_records.append(
            (score, source_priority, record)
        )

    ranked_records.sort(
        key=lambda item: (item[0], item[1]),
        reverse=True,
    )

    return [
        record
        for _, _, record in ranked_records[:limit]
    ]