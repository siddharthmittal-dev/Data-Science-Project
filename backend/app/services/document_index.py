"""Local artifact with an in-memory FAISS and BM25 index."""

import hashlib
import logging
import re
from functools import lru_cache
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.config import BACKEND_DIR, Settings, get_settings

DIMENSIONS = 512
MAX_CHUNKS = 500
MAX_INDEX_BYTES = 16 * 1024 * 1024
log = logging.getLogger(__name__)


class Page(BaseModel):
    number: int
    text: str


class Document(BaseModel):
    title: str
    pages: list[Page]
    pdf_base64: str | None = None
    kind: str = "medical_record"
    status: str = "archived"
    receptionist_visible: bool = False
    patient_case_id: str | None = None


class Chunk(BaseModel):
    source: str
    page: int
    text: str


class Artifact(BaseModel):
    version: int
    embedding_model: str
    documents: dict[str, Document]
    chunks: list[Chunk]
    vectors: list[list[float]]


def index_path(settings: Settings) -> Path:
    return BACKEND_DIR / settings.rag_index_path


def openai_post(settings: Settings, endpoint: str, payload: dict) -> dict:
    response = httpx.post(
        f"https://api.openai.com/v1/{endpoint}",
        headers={"Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}"},
        json=payload, timeout=httpx.Timeout(25, connect=5),
    )
    response.raise_for_status()
    return response.json()


def embed(settings: Settings, texts: list[str]) -> list[list[float]]:
    payload = openai_post(settings, "embeddings", {
        "model": settings.openai_embedding_model, "input": texts,
        "dimensions": DIMENSIONS, "encoding_format": "float",
    })
    rows = sorted(payload["data"], key=lambda row: row["index"])
    if [row["index"] for row in rows] != list(range(len(texts))):
        raise ValueError("Invalid embedding batch.")
    vectors = [row["embedding"] for row in rows]
    _normalized(vectors)
    return vectors


def _normalized(vectors):
    import numpy as np

    matrix = np.array(vectors, dtype=np.float32, order="C")
    if matrix.ndim != 2 or matrix.shape[1] != DIMENSIONS or not np.isfinite(matrix).all():
        raise ValueError("Invalid vector dimensions or values.")
    lengths = np.linalg.norm(matrix, axis=1)
    if not np.isfinite(lengths).all() or (lengths <= 0).any():
        raise ValueError("Invalid vector lengths.")
    return matrix / lengths[:, None]


def terms(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold())


class DocumentIndex:
    def __init__(self, artifact: Artifact, revision: str):
        import faiss
        from rank_bm25 import BM25Plus

        if artifact.version != 1 or not 1 <= len(artifact.chunks) <= MAX_CHUNKS:
            raise ValueError("Unsupported document index.")
        if len(artifact.vectors) != len(artifact.chunks):
            raise ValueError("Document index has mismatched chunks and vectors.")
        self.artifact = artifact
        self.revision = revision
        self.dense = faiss.IndexFlatIP(DIMENSIONS)
        self.dense.add(_normalized(artifact.vectors))
        corpus = [terms(f"{artifact.documents[chunk.source].title} {chunk.text}") for chunk in artifact.chunks]
        self.lexical = BM25Plus(corpus)
        self.words = [set(row) for row in corpus]

    def search(self, question: str, vector: list[float]) -> dict[str, Chunk]:
        count = min(8, len(self.artifact.chunks))
        similarities, indices = self.dense.search(_normalized([vector]), count)
        semantic = [
            int(index) for index, score in zip(indices[0], similarities[0], strict=True)
            if index >= 0 and score >= 0.22
        ]
        query = terms(question)
        query_words = set(query)
        scores = self.lexical.get_scores(query)
        lexical = sorted(
            (i for i, words in enumerate(self.words) if words & query_words),
            key=lambda i: (-scores[i], i),
        )[:count]
        fused: dict[int, float] = {}
        for ranking in (semantic, lexical):
            for rank, index in enumerate(ranking, start=1):
                fused[index] = fused.get(index, 0) + 1 / (60 + rank)
        ranked = sorted(fused, key=lambda i: (-fused[i], i))[:5]
        return {str(i): self.artifact.chunks[i] for i in ranked}

    def source(self, slug: str) -> dict | None:
        base, marker, number = slug.partition("-p")
        document = self.artifact.documents.get(base)
        if document is None:
            return None
        if marker:
            page = next((p for p in document.pages if str(p.number) == number), None)
            if page is None:
                return None
            return {"slug": slug, "title": f"{document.title} · p. {page.number}", "body": page.text}
        return {"slug": slug, "title": document.title,
                "body": "\n\n".join(f"Page {p.number}\n\n{p.text}" for p in document.pages)}


@lru_cache(maxsize=1)
def _load(path: Path, revision: tuple[int, int, int]) -> DocumentIndex:
    with path.open("rb") as source:
        raw = source.read(MAX_INDEX_BYTES + 1)
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError("Document index exceeds the size limit.")
    artifact = Artifact.model_validate_json(raw)
    return DocumentIndex(artifact, hashlib.sha256(raw).hexdigest())


def get_index() -> DocumentIndex | None:
    path = index_path(get_settings())
    try:
        stat = path.stat()
        return _load(path, (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, ImportError):
        log.warning("Document index could not be loaded.")
        return None
