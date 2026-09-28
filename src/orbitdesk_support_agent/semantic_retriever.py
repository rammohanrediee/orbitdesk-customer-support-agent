from time import perf_counter

import numpy as np
from sentence_transformers import SentenceTransformer

from orbitdesk_support_agent.model_config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    MAX_RETRIEVED_RECORDS,
    get_device,)
from orbitdesk_support_agent.schemas import EvidenceRecord


class SemanticRetriever:
    retrieval_mode = "semantic"

    def __init__(
        self,
        records: list[EvidenceRecord],
        model: SentenceTransformer | None = None,
    ) -> None:
        self.records = [
            record
            for record in records
            if record["status"] != "superseded"
        ]

        if model is None:
            load_started = perf_counter()

            self.model = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                revision=EMBEDDING_MODEL_REVISION,
                device=get_device(),
            )

            self.model_load_seconds = perf_counter() - load_started
        else:
            self.model = model
            self.model_load_seconds = 0.0

        indexing_started = perf_counter()

        if self.records:
            texts = [record["text"] for record in self.records]

            self.embeddings = np.asarray(
                self.model.encode(
                    texts,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )
            )
        else:
            self.embeddings = np.empty((0, 0), dtype=np.float32)

        self.indexing_seconds = perf_counter() - indexing_started

    def retrieve(
        self,
        question: str,
        limit: int = MAX_RETRIEVED_RECORDS,
    ) -> list[EvidenceRecord]:
        if not question.strip() or limit <= 0 or not self.records:
            return []

        question_embedding = np.asarray(
            self.model.encode(
                [question],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        )[0]

        # Normalized vectors make their dot product equal cosine similarity.
        similarity_scores = self.embeddings @ question_embedding

        ranked_records: list[
            tuple[float, int, EvidenceRecord]
        ] = []

        for score, record in zip(
            similarity_scores,
            self.records,
            strict=True,
        ):
            source_priority = (
                1
                if record["source_type"] == "knowledge_base"
                else 0
            )

            ranked_records.append(
                (float(score), source_priority, record)
            )

        ranked_records.sort(
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )

        return [
            record
            for _, _, record in ranked_records[:limit]
        ]
