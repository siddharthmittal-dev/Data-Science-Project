import base64
import httpx

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.index_documents import publish
from app.services import patient_documents as service
from app.services.document_index import Artifact, Chunk, Document, Page, DIMENSIONS
from app.services.document_rag import Answer, Evidence


@pytest.fixture
def patient_libraries(tmp_path, monkeypatch):
    def path(email):
        return tmp_path / email / "index.json"
    monkeypatch.setattr(service, "patient_path", path)
    for email, label, slug in (
        ("maya.patel@terra.example", "MAYA-ONLY", "doc-maya"),
        ("jordan.lee@terra.example", "JORDAN-ONLY", "doc-jordan"),
    ):
        text = f"Medicine {label}. Timing is unreadable. Duration is missing."
        artifact = Artifact(
            version=1, embedding_model="text-embedding-3-small",
            documents={slug: Document(title="Prescription.pdf", pages=[Page(number=1, text=text)],
                                      pdf_base64=base64.b64encode(b"%PDF-test").decode())},
            chunks=[Chunk(source=slug, page=1, text=text)],
            vectors=[[1.0] + [0.0] * (DIMENSIONS-1)],
        )
        publish(artifact, path(email))
    monkeypatch.setattr(service, "get_settings", lambda: Settings(openai_api_key=SecretStr("dummy")))
    monkeypatch.setattr(service, "_cache", lambda *args: None)
    monkeypatch.setattr(service, "embed", lambda *args: [[1.0] + [0.0] * (DIMENSIONS-1)])


def test_shared_cases_require_selection_and_retrieve_only_selected_case(login, patient_libraries, db, monkeypatch):
    from app.models import User
    user = db.get(User, 1)
    first = service.patient_index(user).artifact.model_copy(deep=True)
    first.documents["doc-maya"].patient_case_id = "TC-PT-0001"
    first.documents["doc-second"] = Document(title="Second patient", patient_case_id="TC-PT-0002",
                                             pages=[Page(number=1, text="OTHER PATIENT ONLY")])
    first.chunks.append(Chunk(source="doc-second", page=1, text="OTHER PATIENT ONLY"))
    first.vectors.append(first.vectors[0])
    publish(first, service.patient_path(user.email))
    client = login("patient")
    reply = client.post("/api/patient-documents/chat", json={"question": "Explain my prescription"})
    assert reply.status_code == 200
    assert "Select a document" in reply.json()["reply"]
    assert reply.json()["citations"] == []

    def generated(settings, context, candidates, prompt):
        assert all(chunk.source == "doc-maya" for chunk in candidates.values())
        key, chunk = next(iter(candidates.items()))
        return Answer(answer="Timing is unreadable.", evidence=[Evidence(id=key, quote=chunk.text)])

    monkeypatch.setattr(service, "generate", generated)
    selected = client.post("/api/patient-documents/chat", json={"question": "Explain", "document_id": "doc-maya"})
    assert selected.status_code == 200
    assert selected.json()["citations"]
    assert all(c["slug"].startswith("doc-maya") for c in selected.json()["citations"])


@pytest.mark.parametrize("failure", ["timeout", "evidence"])
def test_explanation_recovers_once_without_relaxing_evidence(login, patient_libraries, monkeypatch, failure):
    calls = []

    def generated(settings, context, candidates, prompt):
        calls.append(1)
        if len(calls) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("test timeout")
            return Answer(answer="Unsupported dose", evidence=[Evidence(id="0", quote="Never written in source")])
        return Answer(answer="Timing is unreadable.", evidence=[Evidence(id="0", quote="Timing is unreadable.")])

    monkeypatch.setattr(service, "generate", generated)
    result = login("patient").post("/api/patient-documents/chat", json={"question": "Explain this", "document_id": "doc-maya"})
    assert result.status_code == 200
    assert result.json()["citations"]
    assert "Unsupported dose" not in result.text
    assert len(calls) == 2


def test_permanent_provider_failure_is_not_retried(login, patient_libraries, monkeypatch):
    calls = []

    def generated(*args):
        calls.append(1)
        response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        raise httpx.HTTPStatusError("Unauthorized", request=response.request, response=response)

    monkeypatch.setattr(service, "generate", generated)
    result = login("patient").post("/api/patient-documents/chat", json={"question": "Explain this"})
    assert result.status_code == 503
    assert len(calls) == 1


def test_patient_access_before_pdf_citation_and_chat(client, login, db, patient_libraries):
    assert client.get("/api/patient-documents").status_code == 401
    maya = login("patient")
    assert [d["slug"] for d in maya.get("/api/patient-documents").json()] == ["doc-maya"]
    assert "MAYA-ONLY" in maya.get("/api/patient-documents/doc-maya-p1").json()["body"]
    assert maya.get("/api/patient-documents/doc-maya/pdf").content == b"%PDF-test"
    for endpoint in ("doc-jordan", "doc-jordan-p1", "doc-jordan/pdf"):
        assert maya.get(f"/api/patient-documents/{endpoint}").status_code == 404
    assert maya.post("/api/patient-documents/chat", json={
        "question": "Show it", "document_id": "doc-jordan",
    }).status_code == 404
    assert login("admin").get("/api/patient-documents").status_code == 403


def test_explanation_uses_only_authorized_excerpts(login, patient_libraries, monkeypatch):
    def generated(settings, question, candidates, prompt):
        text = " ".join(c.text for c in candidates.values())
        assert "MAYA-ONLY" in text and "JORDAN-ONLY" not in text
        assert "Never guess a missing instruction" in prompt
        return Answer(answer="Timing needs clarification from your pharmacist. Duration is missing.",
                      evidence=[Evidence(id="0", quote="Timing is unreadable.")])
    monkeypatch.setattr(service, "generate", generated)
    result = login("patient").post("/api/patient-documents/chat", json={
        "question": "Explain my prescription", "document_id": "doc-maya",
    })
    assert result.status_code == 200
    assert result.json()["ai_notice"] == service.NOTICE
    assert result.json()["citations"][0]["slug"] == "doc-maya-p1"


def test_invalid_citation_fails_closed(login, patient_libraries, monkeypatch):
    monkeypatch.setattr(service, "generate", lambda *args: Answer(
        answer="Invented dose", evidence=[Evidence(id="0", quote="Unwritten dose")]))
    result = login("patient").post("/api/patient-documents/chat", json={"question": "Explain this"})
    assert result.status_code == 503
    assert "Invented dose" not in result.text


def test_appointment_answer_uses_database_even_without_documents(login, monkeypatch):
    monkeypatch.setattr(service, "patient_index", lambda user: None)
    monkeypatch.setattr(service, "generate", lambda *args: pytest.fail("Model should not supply booking status"))
    result = login("patient").post("/api/patient-documents/chat", json={"question": "When is my next confirmed appointment?"})
    assert result.status_code == 200
    assert result.json()["origin"] == "appointments"
    assert result.json()["ai_notice"] is None


def test_unified_workspace_prescription_rag_and_booking_proposals(login, patient_libraries, monkeypatch):
    monkeypatch.setattr(service, "generate", lambda *args: Answer(
        answer="Timing needs clarification.", evidence=[Evidence(id="0", quote="Timing is unreadable.")]))
    client = login("patient")
    result = client.post("/api/assistant/message", json={
        "workspace": True, "context": "documents", "message": "Explain this", "document_id": "doc-maya",
    })
    assert result.status_code == 200
    assert result.json()["citations"][0]["scope"] == "patient"
    assert result.json()["ai_notice"] == service.NOTICE
    assert result.json()["proposed_action"] is None
    denied = client.post("/api/assistant/message", json={
        "workspace": True, "context": "documents", "message": "Explain it", "document_id": "doc-jordan",
    })
    assert denied.status_code == 404
    proposed = client.post("/api/assistant/message", json={
        "workspace": True, "message": "Book me with a pediatrician",
    })
    assert proposed.status_code == 200
    assert proposed.json()["proposed_action"]["type"] == "book"


@pytest.mark.parametrize("role", ["admin", "receptionist"])
def test_unified_staff_insights_retrieval(login, monkeypatch, role):
    from app.services import workspace
    workspace._snapshot_index.cache_clear()
    seen = []
    def vectors(settings, texts):
        return [[1.0] + [0.0] * (DIMENSIONS-1) for _ in texts]
    monkeypatch.setattr(workspace, "get_settings", lambda: Settings(openai_api_key=SecretStr("dummy")))
    monkeypatch.setattr(workspace, "embed", vectors)
    def answer(settings, question, candidates, prompt):
        seen.extend(chunk.text for chunk in candidates.values())
        assert all("maya.patel@" not in chunk.text and "Jordan Lee" not in chunk.text for chunk in candidates.values())
        key = next(iter(candidates))
        return Answer(answer="These figures cover the supplied reporting window.",
                      evidence=[Evidence(id=key, quote=candidates[key].text[:40])])
    monkeypatch.setattr(workspace, "generate", answer)
    response = login(role).post("/api/assistant/message", json={
        "workspace": True, "context": "insights", "message": "Summarize clinic activity",
    })
    assert response.status_code == 200
    assert response.json()["citations"][0]["scope"] == "insights"
    assert response.json()["proposed_action"] is None
    assert seen
    workspace._snapshot_index.cache_clear()


def test_unified_patient_cannot_request_insights(login):
    result = login("patient").post("/api/assistant/message", json={
        "workspace": True, "context": "insights", "message": "Show clinic performance",
    })
    assert result.status_code == 403
