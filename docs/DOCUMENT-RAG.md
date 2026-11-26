# Clinic document retrieval

Updated 26 November 2026. Older setup notes are archived in archive/handoffs/docs/DOCUMENT-RAG.md.

The shared library contains clinic guides readable by signed-in accounts. Patient medical records use a separate private pipeline described in PATIENT-DOCUMENTS.md. Keep credentials and patient files out of shared ingestion.

## Current implementation

Directory enumeration and PDF pages are lazy. Embedded PDF text uses pypdfium2; scanned pages and images use Tesseract OCR. Recursive chunks are embedded with OpenAI text-embedding-3-small at 512 dimensions. FAISS cosine retrieval and BM25+ rankings are combined by reciprocal rank fusion. GPT answers contain checked supporting quotes and page citations.

OpenAI settings belong in backend/.env. Defaults are gpt-5-mini for responses and text-embedding-3-small for embeddings. Rebuild indexes after changing the embedding model. OpenAI calls can incur usage charges. Redis is optional and caches duplicate questions for 30 minutes; keys include user, model, prompt and index revision.

Windows native FAISS is blocked on this laptop. Use Docker's Linux backend. Existing Compose mounts backend/app and backend/rag-local; restart rag-api after app/config edits. A new backend image must include current migrations and source data.

## Shared library refresh

The current library has eight guide PDFs plus wayfinding. Regenerate only guides with scripts/generate_training_sets.py's write_rag() function using an existing ReportLab runtime. Running the whole script also regenerates the regression workbook, so do not do that for text-only changes.

Build a current image, then run:

```powershell
docker compose --profile rag run --rm --no-deps rag-api python -m app.refresh_clinic_library
docker compose --profile rag restart rag-api
```

When using an older local image, mount the updated guide PDF directory and backend/rag-samples read-only, as well as the existing app mount. The refresh publishes atomically, preserves patient indexes and changes the revision to invalidate stale shared answers. Shared-answer Redis keys use terra:rag:v1:; private patient keys use terra:patient-rag:. Never flush all Redis data to refresh a clinic guide.

For a different approved shared directory, app.index_documents accepts that path and optional --force-ocr. This replaces the shared index; it does not append or alter patient libraries. The index file is backend/rag-local/index.json.

Limits include 12 MiB/file, 50 PDF pages, 30 files and 500 chunks. Failure before publishing preserves the previous index. Do not load untrusted pickle indexes. Prompt-injection defenses and checked quotes reduce specific risks; they do not prove every generated interpretation is correct.

After a refresh, test retrieval, page citations, originals, role permissions and repeated-question caching. Latest live check answered that account sessions last eight hours and cited privacy-and-access.pdf.
