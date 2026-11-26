# Data sources and interpretation

Updated 26 November 2026.

| Source | Meaning and scope |
|---|---|
| Current PostgreSQL appointments | Application records, initially populated by fixtures and later local actions; not verified real-clinic activity |
| Uploaded appointments/calendar CSVs | User-supplied generated history; 376 appointments, 122 patients, May-October 2026 and November planned capacity |
| demand-demo-v1.json | Separate generated workload scenario with training metadata and baseline evaluation |
| retention-demo-v1.json | Generated longitudinal patient population used by the existing follow-up model |
| synthetic-v1 clinic PDFs | Generated clinic-information corpus; operational assumptions are not independently verified clinic facts |
| patient-rag-v1 PDFs | Fictional prescription/visit fixtures with invented medicine labels, separate from registered-account uploads |
| Five newly delivered Terra PDFs | Distinct TC-PT patient identities with original research-only/invalid-for-dispensing labels; imported under the user-approved universal patient login with selected-record explanations |

Keep the source flags, generator seeds, hashes, model metrics and original prescription labels. Neutral product headings do not change provenance. Original source documents must not be rewritten to imply real prescriptions or clinical validation.

The approved five Terra PDFs and both CSVs are bundled in `backend/data/presentation/`.
Its `manifest.json` records the original filenames and SHA-256 checksums. These
are generated research sources, not actual patient records. The source bytes are
unchanged; private uploads, account credentials and generated FAISS indexes are
excluded from version control. The existing separate test corpora remain separate.

The monthly-cutoff 90-day retention target differs from a label generated after every visit. Unknown follow-up stays censored. Future outcomes must not appear in predictors. Model success on generated data does not establish real-clinic accuracy.

Shared clinic information and patient medical records have separate access scopes. Never publish private records in the shared guide index. Do not assume an index belongs to a newly registered account simply because its patient role matches.
