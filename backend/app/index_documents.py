"""Build the searchable shared library from an approved directory."""

import argparse
import base64
import hashlib
import tempfile
from pathlib import Path

import httpx

from app.config import Settings, get_settings
from app.services.document_index import (
    MAX_CHUNKS, MAX_INDEX_BYTES, Artifact, Chunk, Document, DocumentIndex, Page, embed, index_path,
)
from app.services.document_loader import MAX_PAGE_TEXT, chunks, directory_files, load_document_pages, read_document


def prepare_document(data: bytes, title: str, slug: str, settings: Settings,
                     force_ocr: bool = False, chunk_limit: int = MAX_CHUNKS) -> tuple[Document, list[Chunk]]:
    extension = Path(title).suffix.lower()
    pages: list[Page] = []
    records: list[Chunk] = []
    try:
        for number, raw in load_document_pages(
            data, extension, settings.rag_ocr_executable, settings.rag_ocr_language, force_ocr,
        ):
            clean = raw.replace("\r\n", "\n").replace("\x00", "").strip()
            if not clean:
                continue
            if len(clean) > MAX_PAGE_TEXT:
                raise ValueError(f"Page {number} exceeds the text limit.")
            pages.append(Page(number=number, text=clean))
            for part in chunks(clean):
                if len(records) >= chunk_limit:
                    raise ValueError(f"Corpus exceeds {MAX_CHUNKS} chunks.")
                records.append(Chunk(source=slug, page=number, text=part))
        if not records:
            raise ValueError("No readable text. Check the scan or select another OCR language.")
    except Exception as exc:
        # Native PDF and image decoders raise different exceptions.
        detail = str(exc) if isinstance(exc, ValueError) else "Document could not be decoded."
        raise ValueError(detail) from exc
    document = Document(title=title, pages=pages,
                        pdf_base64=base64.b64encode(data).decode() if extension == ".pdf" else None)
    return document, records


def build(directory: Path, settings: Settings, force_ocr: bool = False) -> Artifact:
    import faiss

    if not hasattr(faiss, "IndexFlatIP"):
        raise ImportError("FAISS IndexFlatIP is required.")
    documents: dict[str, Document] = {}
    records: list[Chunk] = []
    for path in directory_files(directory):
        title = path.relative_to(directory).as_posix()
        slug = "doc-" + hashlib.sha256(title.encode()).hexdigest()[:24]
        try:
            document, document_chunks = prepare_document(
                read_document(path), title, slug, settings, force_ocr, MAX_CHUNKS - len(records),
            )
        except (ValueError, OSError) as exc:
            detail = str(exc) if isinstance(exc, ValueError) else "Document could not be read."
            raise ValueError(f"{path.name}: {detail}") from exc
        documents[slug] = document
        records.extend(document_chunks)
    if not records:
        raise ValueError("No supported documents found.")
    vectors = []
    for start in range(0, len(records), 32):
        batch = records[start:start + 32]
        vectors.extend(embed(settings, [f"{documents[c.source].title}\n{c.text}" for c in batch]))
    return Artifact(version=1, embedding_model=settings.openai_embedding_model,
                    documents=documents, chunks=records, vectors=vectors)


def publish(artifact: Artifact, path: Path) -> None:
    raw = artifact.model_dump_json().encode()
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError("Document index exceeds the size limit.")
    DocumentIndex(artifact, "validation")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".index-", delete=False) as staging:
        pending = Path(staging.name)
    try:
        pending.write_bytes(raw)
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--force-ocr", action="store_true", help="OCR every PDF page, including maps with a text layer.")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.openai_api_key.get_secret_value():
        parser.exit(2, "Set OPENAI_API_KEY in backend/.env before indexing.\n")
    try:
        artifact = build(args.directory, settings, args.force_ocr)
        publish(artifact, index_path(settings))
    except httpx.HTTPStatusError as exc:
        parser.exit(1, f"OpenAI rejected embedding request (HTTP {exc.response.status_code}). Existing index preserved.\n")
    except (httpx.RequestError, ImportError, OSError, ValueError, TypeError, KeyError) as exc:
        detail = str(exc) if isinstance(exc, (ValueError, ImportError)) else "Check provider and local index access."
        parser.exit(1, f"Indexing failed. {detail}\n")
    print(f"Indexed {len(artifact.documents)} documents and {len(artifact.chunks)} chunks using FAISS.")


if __name__ == "__main__":
    main()
