# Terra API contract

Updated 26 November 2026. The former contract is archived in archive/handoffs/docs/api-contract.md. The running API's /docs and /openapi.json describe exact request/response schemas.

## Identity and access

POST /api/auth/login accepts email and password and returns id, name, email and role. The eight-hour session cookie is HttpOnly and SameSite=Lax; enable COOKIE_SECURE for HTTPS. POST /api/auth/logout invalidates the current session; GET /api/auth/me returns its identity. The former role-only /api/auth/demo-login route is removed.

POST /api/auth/signup is disabled by default and returns 403 registration_closed. GET /api/auth/available-roles returns an empty list while closed. The database permits one password account per role. Existing non-registered records remain separate. Owner is serialized as admin.

Patients access their own records and appointments. Receptionists manage scheduling and view only explicitly shared current prescriptions/doctor notes; historical medical records and clinical reasons are restricted. Owner can select patients, review records and access follow-up/evaluation endpoints. Aggregate Insights is available to both staff roles.

## Main resources

- /api/doctors and /api/doctors/{id}/slots: clinician discovery and availability.
- /api/appointments: list/create; /patients: staff selector; /{id}/reschedule, /cancel and /outcome: controlled state transitions.
- /api/assistant/message: answers and proposed actions; /actions/{id}/confirm and /dismiss: owner-of-action confirmation.
- /api/guides and /api/guides/{slug}: shared clinic sources. The legacy privacy slug remains stable; its displayed title is Privacy and account access.
- /api/patient-documents: authorized library; /summary and /chat: patient-scoped context; /{slug}/pdf and source routes: authorized originals/evidence.
- POST /api/patient-documents/upload?filename=...: patient-only raw application/octet-stream, maximum 12 MiB; not multipart.
- /api/insights: staff aggregates, current-record baseline and separate model_demo workload data.
- /api/insights/csv-evaluation: owner-only uploaded-data report.
- /api/insights/replay: staff historical forecast evaluation.
- /api/retention and its /tasks routes: owner-only review and internal follow-up.
- /health: database health, outside the /api prefix.

## State and compatibility

PostgreSQL stores identities, sessions, appointments, events and tasks. Private document/index files live under backend/rag-local. FAISS/BM25 indexes and Redis keys are scoped before retrieval. Booking uses database uniqueness and transaction guards; changes proposed by chat require confirmation.

Keep existing JSON keys, artifact filenames and source slugs compatible unless a separately tested contract migration is requested. model_demo is a legacy key for the separate workload model, not an instruction to relabel current records.

Errors use detail.code and detail.message. Validation returns 422; unauthenticated access 401; denied access 403; conflicts 409. Never expose password hashes or provider secrets in responses.
