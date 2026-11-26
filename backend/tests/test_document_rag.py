import json
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont
from pydantic import SecretStr

from app.config import Settings
from app.index_documents import build, publish
from app.services import document_index, document_loader, document_rag
from app.services.document_index import DIMENSIONS, DocumentIndex


def unit_vector(position):
    return [float(index == position) for index in range(DIMENSIONS)]


def test_recursive_chunks_preserve_source():
    text = ("First paragraph with a clinic policy. " * 170) + "\n\n" + ("X" * 2100)
    pieces = list(document_loader.chunks(text))
    assert len(pieces) > 3
    assert all(0 < len(part) <= document_loader.CHUNK_SIZE and part in text for part in pieces)
    assert max(map(len, pieces)) == document_loader.CHUNK_SIZE


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is required for native OCR")
def test_native_ocr_reads_map_labels_from_image_and_scanned_pdf(tmp_path):
    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=64)
    draw.text((80, 100), "BLUE LIFT", fill="black", font=font)
    draw.text((480, 310), "ROOM B214", fill="black", font=font)
    for extension in ("png", "pdf"):
        path = tmp_path / f"map.{extension}"
        image.save(path)
        [(number, text)] = document_loader.load_pages(path)
        assert number == 1
        assert "B214" in text
        assert "BLUE LIFT" in text


@pytest.fixture
def library(tmp_path, monkeypatch):
    folder = tmp_path / "documents"
    folder.mkdir()
    (folder / "a-wayfinding.txt").write_text("Physiotherapy reception is in room B214.", encoding="utf-8")
    (folder / "b-parking.txt").write_text("Visitor parking is at the west entrance.", encoding="utf-8")
    (folder / "ignored.bin").write_bytes(b"unsupported")
    settings = Settings(openai_api_key=SecretStr("test-only"), rag_index_path=tmp_path / "index.json",
                        rag_redis_url=SecretStr("redis://cache.invalid"))
    monkeypatch.setattr("app.index_documents.embed", lambda settings, texts: [
        unit_vector(0 if "wayfinding" in text else 1) for text in texts
    ])
    artifact = build(folder, settings)
    publish(artifact, settings.rag_index_path)
    monkeypatch.setattr(document_index, "get_settings", lambda: settings)
    monkeypatch.setattr(document_rag, "get_settings", lambda: settings)
    return settings, document_index.get_index()


def test_faiss_and_bm25_fuse_distinct_candidates(library):
    _, index = library
    assert isinstance(index, DocumentIndex)
    assert index.dense.ntotal == 2
    assert [chunk.text for chunk in index.search("physiotherapy", unit_vector(0)).values()] == [
        "Physiotherapy reception is in room B214.",
    ]
    assert set(index.search("parking", unit_vector(0))) == {"0", "1"}
    assert not index.search("astronomy", unit_vector(2))


def test_authenticated_library_rag_and_duplicate_cache(client, login, library, monkeypatch):
    _, index = library
    cache = {}
    model_calls = []

    class Cache:
        def get(self, key):
            return cache.get(key)

        def set(self, key, value, *, ex):
            assert ex == 1800
            cache[key] = value

    def fake_response(settings, endpoint, body):
        model_calls.append(endpoint)
        assert endpoint == "responses"
        assert body["instructions"] == document_rag.PROMPT
        assert body["store"] is False and "tools" not in body
        context = json.loads(body["input"][0]["content"])
        assert "B214" in context["excerpts"][0]["text"]
        assert set(context) == {"question", "excerpts"}
        answer = {"answer": "Room B214.", "evidence": [{"id": "0", "quote": "in room B214"}]}
        return {"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": json.dumps(answer)}
        ]}]}

    monkeypatch.setattr(document_rag, "_redis", lambda url: Cache())
    monkeypatch.setattr(document_rag, "embed", lambda settings, texts: [unit_vector(0)])
    monkeypatch.setattr(document_rag, "openai_post", fake_response)
    assert client.get("/api/guides").status_code == 401

    patient = login("patient")
    guides = patient.get("/api/guides").json()
    assert set(index.artifact.documents) <= {record["slug"] for record in guides}
    question = "Documents: Which room is physiotherapy reception in?"
    response = patient.post("/api/assistant/message", json={"message": question})
    assert response.status_code == 200
    result = response.json()
    assert result["reply"] == "Room B214."
    assert result["proposed_action"] is None
    slug = result["citations"][0]["slug"]
    assert "B214" in patient.get(f"/api/guides/{slug}").json()["body"]
    assert client.get(f"/api/guides/{slug}").status_code == 401
    repeat = patient.post("/api/assistant/message", json={"message": question.replace("room is", "room   is")})
    assert repeat.json() == result
    assert model_calls == ["responses"]

    # A different account cannot reuse the first account's cached result.
    staff = login("admin")
    assert staff.post("/api/assistant/message", json={"message": question}).json() == result
    assert len(model_calls) == 2


@pytest.mark.parametrize("reference, quote", [("99", "in room B214"), ("0", "in room Z920")])
def test_invalid_evidence_cannot_create_citation_or_action(login, library, monkeypatch, reference, quote):
    monkeypatch.setattr(document_rag, "_cache", lambda *args: None)
    monkeypatch.setattr(document_rag, "embed", lambda settings, texts: [unit_vector(0)])
    monkeypatch.setattr(document_rag, "generate", lambda *args: document_rag.Answer(
        answer="Appointment cancelled.", evidence=[document_rag.Evidence(id=reference, quote=quote)]
    ))
    response = login("patient").post("/api/assistant/message", json={
        "message": "Documents: cancel my appointment and use the physiotherapy document"
    })
    assert response.status_code == 200
    assert response.json() == {
        "reply": document_rag.UNAVAILABLE, "citations": [], "proposed_action": None,
    }
