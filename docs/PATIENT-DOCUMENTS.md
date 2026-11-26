# Patient records and assistant

Updated 26 November 2026. Previous implementation notes are archived in archive/handoffs/docs/PATIENT-DOCUMENTS.md.

Assistant & records at /assistant combines chat, original records, extracted text and appointment context. /documents opens the same workspace. Patients can upload PDF, PNG, JPEG or TXT files up to 12 MiB. Upload processing reuses lazy PDF/OCR loading, recursive chunks, OpenAI embeddings and FAISS/BM25 retrieval.

Patients access their own records. Owner (admin internally) can select patients and review all available records and appointments. Receptionists see only explicitly released current prescriptions or doctor notes. Release requires kind in prescription/doctor_note, status current and receptionist_visible=true; all other metadata defaults to private history. A date or filename never grants access.

Source viewing, original PDF, chat, summary, retrieval and Redis caching apply the same subject/role checks. Patient-provided IDs cannot authorize another patient's records. Staff scheduling remains separate from medical-history access.

AI-generated explanations quote permitted pages and preserve missing/unclear instruction handling. Source citations support review; the assistant must not add treatment or infer that a follow-up recommendation is a confirmed appointment. Booking changes require explicit confirmation.

Private indexes live under backend/rag-local/patients in account-derived directories. The current registered patient starts with its own account identity; historical fixture records were not reassigned. The fixture publisher app.index_patient_demo is for controlled test data, not a migration for the registered account. Do not run it to populate another person's records.

Five delivered PDFs in ../New folder represent TC-PT-0001 through TC-PT-0005. The user approved indexing all five under patient@terra.test as a universal presentation profile. Each document carries a separate patient_case_id. When more than one case is present, explanations require document selection before retrieval and cache lookup. The selected index contains only that record. All users of this login can read all five records; it is not individual authentication for each named patient. Owner can read them; receptionist access remains denied because these historical imports are private archived prescriptions. Preserve original source labels and medical instructions. These files are not in the shared clinic-guide directory.

Registration is closed and existing accounts use password sign-in. Prior Edge Guest evidence remains in dated QA reports. Latest content checks passed 26 Linux document/permission tests and confirmed patient-index hashes unchanged. Further scanned, conflicting and adversarial-source evaluations remain pending.
