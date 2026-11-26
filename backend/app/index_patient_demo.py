"""Publish synthetic prescription indexes for existing demo patients."""
import argparse
import hashlib
from app.config import BACKEND_DIR, get_settings
from app.index_documents import build, publish
from app.services.patient_documents import patient_path
from app.services.document_index import Artifact


DEMO_TITLES = {
    "doc-" + hashlib.sha256(title.encode()).hexdigest()[:24]: title
    for title in ("prescription.pdf", "visit.pdf")
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-access", action="store_true", help="Update demo sharing flags without embedding again.")
    args = parser.parse_args()
    settings = get_settings()
    if not args.refresh_access and not settings.openai_api_key.get_secret_value():
        raise SystemExit("Set OPENAI_API_KEY before indexing.")
    for fixture, email in (("P001", "maya.patel@terra.example"), ("P002", "jordan.lee@terra.example")):
        directory = BACKEND_DIR / "data/patient-rag-v1/documents" / fixture
        target = patient_path(email)
        if args.refresh_access:
            artifact = Artifact.model_validate_json(target.read_bytes())
        else:
            if target.exists():
                raise SystemExit(f"{fixture}: patient library already exists. Use --refresh-access to update its demo flags.")
            artifact = build(directory, settings)
        for slug, document in artifact.documents.items():
            # These are operator-owned demo fixtures, explicitly released as the current demo prescription.
            if DEMO_TITLES.get(slug) != document.title:
                continue
            current = document.title == "prescription.pdf"
            document.kind = "prescription" if current else "medical_record"
            document.status = "current" if current else "archived"
            document.receptionist_visible = current
        publish(artifact, target)
        print(f"Published {fixture}: {len(artifact.documents)} synthetic documents.")


if __name__ == "__main__":
    main()
