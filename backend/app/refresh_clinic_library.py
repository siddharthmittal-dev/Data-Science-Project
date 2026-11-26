"""Publish approved clinic guides and wayfinding without touching patient indexes."""
from app.config import BACKEND_DIR, get_settings
from app.index_documents import build, publish
from app.services.document_index import Artifact, index_path


def main():
    settings = get_settings()
    guides = build(BACKEND_DIR / "data/synthetic-v1/rag/documents", settings)
    wayfinding = build(BACKEND_DIR / "rag-samples", settings)
    artifact = Artifact(
        version=1, embedding_model=settings.openai_embedding_model,
        documents={**guides.documents, **wayfinding.documents},
        chunks=[*guides.chunks, *wayfinding.chunks],
        vectors=[*guides.vectors, *wayfinding.vectors],
    )
    publish(artifact, index_path(settings))
    print(f"Published {len(artifact.documents)} clinic guides. Patient indexes unchanged.")


if __name__ == "__main__":
    main()
