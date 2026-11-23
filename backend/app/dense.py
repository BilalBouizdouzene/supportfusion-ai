from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .config import ROOT_DIR
from .models import EmbeddingMetadata


EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
INDEX_DIR = ROOT_DIR / "data" / "indexes"
INDEX_PATH = INDEX_DIR / "knowledge.faiss"
METADATA_PATH = INDEX_DIR / "knowledge.metadata.json"


@dataclass
class DenseResult:
    key: str
    score: float


@dataclass
class ModelStatus:
    embedding_loaded: bool = False
    reranker_loaded: bool = False
    embedding_model: str | None = None
    reranker_model: str | None = None
    dense_backend: str = "not loaded"
    error: str | None = None


class DenseIndexService:
    """Lazy, process-cached Sentence-Transformers + FAISS service."""

    def __init__(self) -> None:
        self._embedder: Any = None
        self._reranker: Any = None
        self._index: Any = None
        self._index_items: list[dict[str, Any]] = []
        self._status = ModelStatus()
        self._lock = threading.RLock()

    @property
    def status(self) -> ModelStatus:
        return self._status

    def _load_embedder(self) -> Any:
        with self._lock:
            if self._embedder is not None:
                return self._embedder
            try:
                from sentence_transformers import SentenceTransformer

                self._embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
                self._status.embedding_loaded = True
                self._status.embedding_model = EMBEDDING_MODEL
                self._status.dense_backend = "FAISS CPU + Sentence-Transformers"
                return self._embedder
            except (
                Exception
            ) as error:  # model installation/cache is intentionally optional
                self._status.error = f"Embedding model unavailable: {error}"
                raise RuntimeError(self._status.error) from error

    def _load_reranker(self) -> Any:
        with self._lock:
            if self._reranker is not None:
                return self._reranker
            try:
                from sentence_transformers import CrossEncoder

                self._reranker = CrossEncoder(RERANKER_MODEL, device="cpu")
                self._status.reranker_loaded = True
                self._status.reranker_model = RERANKER_MODEL
                return self._reranker
            except Exception as error:
                self._status.error = f"Cross-Encoder unavailable: {error}"
                raise RuntimeError(self._status.error) from error

    def build_index(
        self, db: Session, records: list[Any], force: bool = False
    ) -> dict[str, Any]:
        started = time.perf_counter()
        if INDEX_PATH.exists() and METADATA_PATH.exists() and not force:
            return self.load_index()
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        try:
            import faiss
            import numpy as np

            embedder = self._load_embedder()
            texts = [record.title + "\n" + record.content for record in records]
            vectors = embedder.encode(
                texts,
                batch_size=8,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            vectors = np.asarray(vectors, dtype="float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(INDEX_PATH))
            items = [
                {
                    "key": record.key,
                    "source_type": record.source_type,
                    "source_id": record.source_id,
                    "title": record.title,
                    "source_url": record.source_url,
                    "metadata": record.metadata,
                }
                for record in records
            ]
            METADATA_PATH.write_text(
                json.dumps(
                    {
                        "embedding_model": EMBEDDING_MODEL,
                        "dimension": int(vectors.shape[1]),
                        "items": items,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            db.execute(
                delete(EmbeddingMetadata).where(EmbeddingMetadata.backend == "faiss")
            )
            for record in records:
                db.add(
                    EmbeddingMetadata(
                        object_type=record.source_type,
                        object_id=record.source_id,
                        backend="faiss",
                        model_name=EMBEDDING_MODEL,
                        index_path=str(INDEX_PATH),
                        dimension=int(vectors.shape[1]),
                    )
                )
            db.commit()
            self._index = index
            self._index_items = items
            return {
                "status": "built",
                "items": len(items),
                "dimension": int(vectors.shape[1]),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "model": EMBEDDING_MODEL,
                "backend": "FAISS CPU",
            }
        except Exception:
            self._status.error = self._status.error or "Dense index build failed"
            raise

    def load_index(self) -> dict[str, Any]:
        import faiss

        if not INDEX_PATH.exists() or not METADATA_PATH.exists():
            raise FileNotFoundError("Dense index has not been built")
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        if metadata.get("embedding_model") != EMBEDDING_MODEL:
            raise RuntimeError(
                "Persisted index was built with a different embedding model"
            )
        self._index = faiss.read_index(str(INDEX_PATH))
        self._index_items = metadata.get("items", [])
        return {
            "status": "loaded",
            "items": len(self._index_items),
            "dimension": metadata.get("dimension"),
            "model": EMBEDDING_MODEL,
            "backend": "FAISS CPU",
        }

    def search(
        self, db: Session, records: list[Any], query: str, limit: int = 20
    ) -> list[DenseResult]:
        try:
            embedder = self._load_embedder()
            if self._index is None:
                if INDEX_PATH.exists() and METADATA_PATH.exists():
                    self.load_index()
                else:
                    self.build_index(db, records, force=True)
            import numpy as np

            vector = embedder.encode(
                [query],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            scores, positions = self._index.search(
                np.asarray(vector, dtype="float32"),
                min(max(limit * 4, limit), len(self._index_items)),
            )
            return [
                DenseResult(self._index_items[position]["key"], float(score))
                for score, position in zip(scores[0], positions[0], strict=False)
                if position >= 0
            ]
        except Exception as error:
            self._status.error = str(error)
            return []

    def rerank(
        self, query: str, candidates: list[tuple[str, str]]
    ) -> list[tuple[str, float]]:
        if not candidates:
            return []
        try:
            model = self._load_reranker()
            scores = model.predict(
                [(query, text) for _, text in candidates],
                batch_size=4,
                show_progress_bar=False,
            )
            return sorted(
                [
                    (key, float(score))
                    for (key, _), score in zip(candidates, scores, strict=False)
                ],
                key=lambda item: -item[1],
            )
        except Exception as error:
            self._status.error = str(error)
            return []


dense_service = DenseIndexService()
