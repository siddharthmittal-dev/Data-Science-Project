# Synthetic patient document fixtures

This initial test set contains six single-page PDFs for three fictional patients,
21 evaluation questions, and two appointment fixtures. Medicine labels are invented.
The simulated instructions are suitable only for application testing.

Use manifest.json to map documents to fixture owners. Application user IDs must be
resolved separately when importing test fixtures. All scenarios use the fixed
reference time 24 November 2026 at 12:00 IST.

Patient P003 has an unclear timing instruction and missing duration, a recommended
return date, and no booking. P001 and P002 have separate prescription instructions
and confirmed appointment fixtures. Appointment fixtures need an isolated test
database or adapter before they can be queried by the app.

The application now implements account-scoped private indexes, source permissions
and role-scoped answer caching. This fixture set remains a reproducible test
corpus, not the current registered patient's library. The registered patient
presentation account contains five separately identified TC-PT case PDFs at the
user's request. Their originals and research-only labels remain unchanged.

Run scripts/generate_prescription_fixtures.py with the bundled ReportLab Python
runtime to reproduce the files. The broader generation prompt in
docs/PATIENT-RAG-DATASET-PROMPT.txt requests additional scanned, conflicting-version,
and adversarial fixtures for a second evaluation pass.
