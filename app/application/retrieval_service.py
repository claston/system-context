from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from app.repositories import RetrievalRepository


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class LocalHashEmbeddingProvider:
    dimensions: int = 64

    def embed(self, text: str) -> list[float]:
        tokens = [token.strip().lower() for token in text.split() if token.strip()]
        if not tokens:
            return [0.0] * self.dimensions
        vector = [0.0] * self.dimensions
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], byteorder="big") % self.dimensions
            weight = ((digest[2] / 255.0) * 2.0) - 1.0
            vector[index] += weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return [0.0] * self.dimensions
        return [value / norm for value in vector]


class RetrievalService:
    def __init__(
        self,
        retrieval_repository: RetrievalRepository,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.retrieval_repository = retrieval_repository
        self.embedding_provider = embedding_provider or LocalHashEmbeddingProvider()

    def semantic_search(
        self,
        *,
        system_component_name: str,
        query: str,
        environment: str | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        normalized_component = system_component_name.strip()
        normalized_query = query.strip()
        if not normalized_component:
            raise ValueError("argument 'name' is required")
        if not normalized_query:
            raise ValueError("argument 'query' is required")

        self._refresh_component_chunks(
            system_component_name=normalized_component,
            environment=environment,
        )

        candidates = self.retrieval_repository.list_context_chunks(
            system_component_name=normalized_component,
            environment=environment,
        )
        query_embedding = self.embedding_provider.embed(normalized_query)

        scored: list[dict[str, Any]] = []
        for item in candidates:
            item_embedding = self._normalize_embedding(
                getattr(item, "embedding", None),
                expected_dimensions=len(query_embedding),
            )
            score = self._cosine_similarity(query_embedding, item_embedding)
            if score <= 0:
                continue
            scored.append(
                {
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "text": item.chunk_text,
                    "environment": item.environment,
                    "score": round(score, 6),
                    "captured_at": item.captured_at,
                    "metadata": item.metadata_json or {},
                }
            )

        scored.sort(key=lambda row: row["score"], reverse=True)
        hits = scored[: max(1, min(int(top_k), 20))]

        return {
            "system_component": normalized_component,
            "environment": environment,
            "query": normalized_query,
            "result_count": len(hits),
            "results": hits,
        }

    def _refresh_component_chunks(
        self,
        *,
        system_component_name: str,
        environment: str | None,
    ) -> None:
        sources: list[dict[str, Any]] = []
        sources.extend(
            self.retrieval_repository.list_pull_request_chunks_source(system_component_name)
        )
        sources.extend(
            self.retrieval_repository.list_commit_chunks_source(system_component_name)
        )
        sources.extend(
            self.retrieval_repository.list_operational_issue_chunks_source(
                system_component_name,
                environment=environment,
            )
        )

        for item in sources:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            source_type = str(item.get("source_type") or "").strip()
            source_id = str(item.get("source_id") or "").strip()
            if not source_type or not source_id:
                continue
            item_environment = item.get("environment")
            if item_environment is None:
                item_environment = environment
            captured_at = item.get("captured_at")
            if not isinstance(captured_at, datetime):
                captured_at = datetime.now(timezone.utc)
            embedding = self.embedding_provider.embed(text)
            chunk_hash = self._build_chunk_hash(
                source_type=source_type,
                source_id=source_id,
                text=text,
            )
            self.retrieval_repository.upsert_context_chunk(
                source_type=source_type,
                source_id=source_id,
                system_component_name=system_component_name,
                environment=item_environment,
                chunk_text=text,
                chunk_hash=chunk_hash,
                embedding=embedding,
                metadata_json=item.get("metadata"),
                captured_at=captured_at,
            )

    def _build_chunk_hash(self, *, source_type: str, source_id: str, text: str) -> str:
        raw = f"{source_type}:{source_id}:{text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _normalize_embedding(
        self,
        raw_embedding: Any,
        *,
        expected_dimensions: int,
    ) -> list[float]:
        if not isinstance(raw_embedding, list):
            return [0.0] * expected_dimensions
        values: list[float] = []
        for value in raw_embedding[:expected_dimensions]:
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                values.append(0.0)
        if len(values) < expected_dimensions:
            values.extend([0.0] * (expected_dimensions - len(values)))
        norm = math.sqrt(sum(v * v for v in values))
        if norm == 0:
            return [0.0] * expected_dimensions
        return [v / norm for v in values]

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(a * b for a, b in zip(left, right))

