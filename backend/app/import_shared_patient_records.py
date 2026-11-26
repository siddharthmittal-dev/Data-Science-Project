"""Import explicitly approved case PDFs into one shared presentation account."""
import argparse
import hashlib
import re
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.index_documents import prepare_document, publish
from app.models import User
from app.services.document_index import Artifact, embed
from app.services.document_loader import read_document
from app.services.patient_documents import patient_index, patient_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    settings = get_settings()
    prepared = []
    for path in sorted(args.directory.glob("Terra_*.pdf")):
        data = read_document(path)
        slug = "doc-" + hashlib.sha256(data).hexdigest()[:24]
        doc, chunks = prepare_document(data, path.name, slug, settings)
        cases = set(re.findall(r"TC-PT-\d{4}", "\n".join(p.text for p in doc.pages)))
        if len(cases) != 1:
            raise ValueError(f"Exactly one patient case ID is required in {path.name}.")
        doc.patient_case_id = next(iter(cases))
        doc.title = f"{doc.patient_case_id} - {path.name}"
        doc.kind = "prescription"
        # Imported historical sources are private unless separately released.
        vectors = embed(settings, [f"{doc.title}\n{c.text}" for c in chunks])
        prepared.append((slug, doc, chunks, vectors))
    if not prepared:
        raise ValueError("No Terra prescription PDFs found.")
    with SessionLocal.begin() as db:
        user = db.scalar(select(User).where(User.email == args.email, User.role == "patient").with_for_update())
        if user is None:
            raise ValueError("Patient account not found.")
        current = patient_index(user)
        artifact = current.artifact.model_copy(deep=True) if current else Artifact(
            version=1, embedding_model=settings.openai_embedding_model, documents={}, chunks=[], vectors=[])
        if artifact.embedding_model != settings.openai_embedding_model:
            raise ValueError("Embedding model changed; reindex before import.")
        for slug, doc, chunks, vectors in prepared:
            if slug in artifact.documents:
                if artifact.documents[slug].patient_case_id != doc.patient_case_id:
                    raise ValueError("Existing record case metadata differs; review before replacing.")
                continue
            artifact.documents[slug] = doc
            artifact.chunks.extend(chunks)
            artifact.vectors.extend(vectors)
        publish(artifact, patient_path(user.email))
    print(f"Imported {len(prepared)} separate case records into the approved shared account.")


if __name__ == "__main__":
    main()
