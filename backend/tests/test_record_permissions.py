"""Record permissions must apply before retrieval, PDFs and cache lookup."""

import base64
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.config import Settings
from app.index_documents import publish
from app.models import User
from app.services import patient_documents as service
from app.services.document_index import Artifact, Chunk, Document, Page, DIMENSIONS
from app.services.document_rag import Answer, Evidence


@pytest.fixture
def records(tmp_path, monkeypatch, db):
    monkeypatch.setattr(service, "patient_path", lambda email: tmp_path / email / "index.json")
    documents = {}
    for slug, kind, status, shared in (
        ("history", "medical_record", "archived", False),
        ("rx", "prescription", "current", True),
        ("note", "doctor_note", "current", True),
        ("unreleased", "prescription", "current", False),
        ("old-rx", "prescription", "archived", True),
    ):
        documents[slug] = Document(
            title=slug, kind=kind, status=status, receptionist_visible=shared,
            pages=[Page(number=1, text=f"Record {slug}. Timing needs clarification.")],
            pdf_base64=base64.b64encode(f"%PDF-{slug}".encode()).decode(),
        )
    artifact = Artifact(
        version=1, embedding_model="text-embedding-3-small", documents=documents,
        chunks=[Chunk(source=slug, page=1, text=doc.pages[0].text) for slug, doc in documents.items()],
        vectors=[[1.0] + [0.0] * (DIMENSIONS - 1) for _ in documents],
    )
    patient = db.scalar(select(User).where(User.email == "maya.patel@terra.example"))
    path = service.patient_path(patient.email)
    publish(artifact, path)
    monkeypatch.setattr(service, "get_settings", lambda: Settings(openai_api_key=SecretStr("dummy")))
    monkeypatch.setattr(service, "embed", lambda *args: [[1.0] + [0.0] * (DIMENSIONS - 1)])
    monkeypatch.setattr(service, "_cache", lambda *args: None)
    return patient.id, artifact, path


@pytest.mark.parametrize("role,expected", [
    ("patient", {"history", "rx", "note", "unreleased", "old-rx"}),
    ("admin", {"history", "rx", "note", "unreleased", "old-rx"}),
    ("receptionist", {"rx", "note"}),
])
def test_record_access_matrix(login, records, role, expected):
    patient_id, _, _ = records
    client = login(role)
    query = f"?patient_id={patient_id}"
    response = client.get("/api/patient-documents" + query)
    assert response.status_code == 200
    assert {d["slug"] for d in response.json()} == expected
    for slug in ("history", "rx", "note", "unreleased", "old-rx"):
        for suffix in ("", "-p1", "/pdf"):
            result = client.get(f"/api/patient-documents/{slug}{suffix}{query}")
            assert result.status_code == (200 if slug in expected else 404)


def test_subject_validation_precedes_lookup(login, records):
    patient_id, _, _ = records
    patient = login("patient")
    for route in ("", "/summary", "/history", "/history/pdf"):
        assert patient.get(f"/api/patient-documents{route}?patient_id={patient_id + 100}").status_code == 403
    assert patient.post("/api/patient-documents/chat", json={
        "question": "Read records", "patient_id": patient_id + 100,
    }).status_code == 403
    for role in ("admin", "receptionist"):
        staff = login(role)
        assert staff.get("/api/patient-documents").status_code == 403
        assert staff.get("/api/patient-documents?patient_id=999999").status_code == 404
        assert staff.get("/api/patient-documents?patient_id=2").status_code == 404


@pytest.mark.parametrize("unified", [False, True])
def test_private_chat_denied_before_model_or_cache(login, records, monkeypatch, unified):
    patient_id, _, _ = records
    monkeypatch.setattr(service, "embed", lambda *args: pytest.fail("Unauthorized embedding"))
    monkeypatch.setattr(service, "generate", lambda *args: pytest.fail("Unauthorized generation"))
    monkeypatch.setattr(service, "_cache", lambda *args: pytest.fail("Unauthorized cache access"))
    body = {"patient_id": patient_id, "document_id": "history"}
    if unified:
        endpoint = "/api/assistant/message"
        body.update(workspace=True, context="documents", message="Explain this")
    else:
        endpoint = "/api/patient-documents/chat"
        body["question"] = "Explain this"
    assert login("receptionist").post(endpoint, json=body).status_code == 404


def test_receptionist_retrieval_and_revocation(login, records, monkeypatch):
    patient_id, artifact, path = records
    cache_keys = []
    monkeypatch.setattr(service, "_cache", lambda settings, key, *args: cache_keys.append(key))

    def generate(settings, question, candidates, prompt):
        assert {c.source for c in candidates.values()} <= {"rx", "note"}
        key = next(iter(candidates))
        return Answer(answer="Timing needs clarification.", evidence=[Evidence(id=key, quote="Timing needs clarification.")])

    monkeypatch.setattr(service, "generate", generate)
    staff = login("receptionist")
    body = {"patient_id": patient_id, "question": "Explain timing", "document_id": "rx"}
    assert staff.post("/api/patient-documents/chat", json=body).status_code == 200
    first = cache_keys[0]
    artifact.documents["rx"].receptionist_visible = False
    publish(artifact, path)
    cache_keys.clear()
    assert staff.post("/api/patient-documents/chat", json=body).status_code == 404
    assert cache_keys == []
    # Other roles cannot reuse a receptionist-scoped cached answer.
    assert login("admin").post("/api/patient-documents/chat", json=body).status_code == 200
    assert cache_keys[0] != first


def test_summary_and_appointment_reasons_are_scoped(login, records):
    patient_id, _, _ = records
    admin = login("admin")
    full = admin.get(f"/api/patient-documents/summary?patient_id={patient_id}").json()
    assert full["access"] == "full"
    assert full["patient"]["email"] == "maya.patel@terra.example"
    assert full["appointments"]
    reception = login("receptionist")
    limited = reception.get(f"/api/patient-documents/summary?patient_id={patient_id}").json()
    assert limited["access"] == "current_shared"
    assert limited["patient"]["email"] is None
    assert all(a["status"] == "booked" and not a["reason"] for a in limited["appointments"])
    assert all(datetime.fromisoformat(a["slot"]["starts_at"]) > datetime.now(UTC) for a in limited["appointments"])
    assert all(not a["reason"] for a in reception.get("/api/appointments").json())
    assert any(a["reason"] for a in admin.get("/api/appointments").json())
    assert reception.get("/api/retention").status_code == 403
    assert reception.post("/api/retention/tasks", json={"patient_id": patient_id, "note": "No access"}).status_code == 403
    assert reception.post("/api/retention/tasks/1/complete", json={"outcome": "No access"}).status_code == 403


def test_old_metadata_defaults_to_private(records, db):
    patient_id, artifact, path = records
    raw = artifact.model_dump()
    for document in raw["documents"].values():
        for field in ("kind", "status", "receptionist_visible"):
            document.pop(field)
    publish(Artifact.model_validate(raw), path)
    actor = db.scalar(select(User).where(User.role == "receptionist"))
    subject = db.get(User, patient_id)
    assert service.permitted_index(actor, subject) is None


def test_upload_preserves_existing_records_and_stays_private(login, records, monkeypatch):
    patient_id, _, _ = records
    path = "/api/patient-documents/upload"
    headers = {"Content-Type": "application/octet-stream"}
    data = b"New synthetic patient record. Follow up with the clinic."
    for role in ("admin", "receptionist"):
        assert login(role).post(path, params={"filename": "record.txt"}, content=data, headers=headers).status_code == 403
    patient = login("patient")
    assert patient.post(path, params={"filename": "broken.pdf"}, content=data, headers=headers).status_code == 422
    assert patient.post(path, params={"filename": "../record.txt"}, content=data, headers=headers).status_code == 422
    response = patient.post(path, params={"filename": "record.txt"}, content=data, headers=headers)
    assert response.status_code == 201
    slug = response.json()["slug"]
    retry = patient.post(path, params={"filename": "renamed.txt"}, content=data, headers=headers)
    assert retry.json()["slug"] == slug
    endpoint = "/api/patient-documents"
    assert len(patient.get(endpoint).json()) == 6
    assert data.decode() in patient.get(f"{endpoint}/{slug}").json()["body"]
    assert login("admin").get(f"{endpoint}/{slug}", params={"patient_id": patient_id}).status_code == 200
    assert login("receptionist").get(f"{endpoint}/{slug}", params={"patient_id": patient_id}).status_code == 404

    def answer(settings, question, candidates, prompt):
        assert all(c.source == slug for c in candidates.values())
        key = next(iter(candidates))
        return Answer(answer="Follow up with the clinic.", evidence=[Evidence(id=key, quote="Follow up with the clinic.")])

    monkeypatch.setattr(service, "generate", answer)
    result = patient.post("/api/assistant/message", json={
        "workspace": True, "context": "documents", "document_id": slug, "message": "What does the record say?",
    })
    assert result.status_code == 200
    assert result.json()["citations"][0]["slug"] == f"{slug}-p1"


@pytest.mark.parametrize("role,allowed", [("admin", {"history", "rx", "note", "unreleased", "old-rx"}),
                                        ("receptionist", {"rx", "note"})])
def test_all_record_rag_retrieval_respects_role(login, records, monkeypatch, role, allowed):
    patient_id, _, _ = records

    def generate(settings, question, candidates, prompt):
        assert {c.source for c in candidates.values()} == allowed
        key = next(iter(candidates))
        return Answer(answer="Timing needs clarification.", evidence=[Evidence(id=key, quote="Timing needs clarification.")])

    monkeypatch.setattr(service, "generate", generate)
    result = login(role).post("/api/assistant/message", json={
        "workspace": True, "context": "documents", "patient_id": patient_id,
        "message": "Explain timing in these records",
    })
    assert result.status_code == 200
    assert all(c["patient_id"] == patient_id and c["scope"] == "patient" for c in result.json()["citations"])
