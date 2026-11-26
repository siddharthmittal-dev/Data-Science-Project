# Terra Family Clinic

The public home page shows clinic information and a sign-in section below it.
Patient, Receptionist and Owner buttons fill the corresponding email address;
passwords must be entered manually. Signed-in visitors retain their existing dashboards.

Terra brings appointment management, patient records and a cited AI assistant into one clinic workspace. The application uses Next.js, React, Tailwind CSS, FastAPI and PostgreSQL, with OpenAI embeddings, FAISS/BM25 retrieval and Redis answer caching.

## Workspaces

| Workspace | Access |
|---|---|
| Patient | Shared presentation records, account appointments, uploads and cited explanations |
| Receptionist | Clinic scheduling, aggregate Insights and explicitly shared current notes/prescriptions |
| Owner | All patient records, appointment details, follow-up tasks and detailed model evaluations |

Owner is the existing backend `admin` role. Registration is closed; the three configured accounts sign in with email and password. Passwords and API keys are not documented in the repository.

## Run locally

Docker Desktop must be running. From the repository root:

For a fresh checkout, follow the initialization section below first.

```powershell
docker compose --profile rag up -d db redis
```

Apply migrations from `backend` before starting a fresh installation:

```powershell
..\.venv\Scripts\python.exe -B -m alembic upgrade head
```

Then, from the repository root:

```powershell
docker compose --profile rag up -d rag-api
Set-Location frontend
npm.cmd run build
npm.cmd start
```

Use the installed project Node directory on PATH if Node is not installed globally. Existing Windows Python dependencies are in `.venv`; pinned requirements are in `requirements.txt` and `backend/requirements.txt`. Configure OpenAI and database settings in the ignored `backend/.env`; never commit it. A fresh checkout requires dependency installation and initial clinic scheduling data; these commands do not create accounts or populate an empty database. Do not run the destructive seed against an existing database.

- Public home: http://localhost:3000/
- Sign-in section: http://localhost:3000/login#sign-in
- API health: http://localhost:8000/health
- API reference: http://localhost:8000/docs

## Analytics and records

Insights separates current appointment aggregates, a weekday baseline, a separately trained workload model and uploaded-CSV evaluations. Count forecasts include OLS coefficients, prediction calculations and errors. Individual no-show evaluation includes ROC/AUC, precision-recall and calibration. Generated-data results have documented provenance; they are not evidence of accuracy at an operating clinic.

Patient records use account-scoped retrieval and source permissions. AI explanations cite permitted records and flag unclear instructions for prescriber review.

## Current status and documentation

The approved local, non-data completion scope is finished. Five patient-case PDFs use the shared patient login with selected-record explanations. Insights includes approximate OLS uncertainty graphs and calculations. Independent retention evaluation and stronger no-show evidence await additional history. Authentication extras, Assistant & records additions and deployment remain deferred. Repository packaging is being prepared for review; pushing requires approval.

- [Known limitations](docs/known-issues.md)
- [Model evaluation status](docs/INSIGHTS-ML-STATUS.txt)
- [API contract](docs/api-contract.md)
- [Patient records](docs/PATIENT-DOCUMENTS.md)
- [RAG operations](docs/DOCUMENT-RAG.md)
- [Data provenance](docs/DATA-SOURCES.md)
- [Account access](docs/ACCOUNT-SETUP.txt)

Historical plans, handoffs and unused starter assets are kept locally in ignored documentation archives. They are not required to run the application and are not included in a fresh checkout. The approved source dataset is included under `backend/data/presentation/`; private uploads and generated retrieval indexes are excluded.

## Repository layout

| Path | Purpose |
|---|---|
| `frontend/app`, `frontend/components`, `frontend/lib` | Pages, interface components and API clients |
| `frontend/tests` | Frontend contract and markup checks |
| `backend/app` | API, authorization, retrieval and model evaluation |
| `backend/migrations`, `backend/tests` | Database migrations and isolated backend tests |
| `backend/data/presentation` | Approved source PDFs and appointment/calendar CSVs |
| `backend/data/patient-rag-v1`, `backend/data/synthetic-v1` | Separate generated test corpora and training sources |
| `scripts` | Development tools and data generators |
| `docs` | Operational instructions, API contract and model limitations |

## Fresh-checkout initialization

Use Docker Desktop with Linux containers and Node.js 24. Copy `.env.example` to
`backend/.env` and `frontend/.env.local.example` to `frontend/.env.local` only if
those destinations do not already exist. Add your OpenAI key in `backend/.env`.
Never overwrite an existing environment file or commit credentials.

From the repository root:

```powershell
docker compose --profile rag build rag-api
docker compose --profile rag up -d db redis
docker compose --profile rag run --rm --no-deps rag-api python -m alembic upgrade head
```

Only on an empty installation, initialize scheduling data with:

```powershell
docker compose --profile rag run --rm --no-deps rag-api python -m app.seed
```

**The seed truncates application tables. Never run it on an existing database.**
Registration remains closed and database users/passwords are deliberately not
shipped. Existing accounts require the existing local database or a private backup.
Creating accounts for a new installation is a separate operator step; copying
this repository alone does not reproduce existing account access. Do not enable
public registration to work around that limitation.

With the intended patient account already provisioned, rebuild the shared and
private retrieval indexes from the approved sources (OpenAI usage may be charged):

```powershell
docker compose --profile rag run --rm --no-deps rag-api python -m app.refresh_clinic_library
docker compose --profile rag run --rm --no-deps rag-api python -m app.import_shared_patient_records data/presentation --email patient@terra.test
docker compose --profile rag up -d rag-api
Set-Location frontend
npm.cmd ci
npm.cmd run build
npm.cmd start
```

Source PDF bytes are unchanged. All five cases share the explicitly approved
presentation login; this does not provide an individual account for each patient.
See `backend/data/presentation/manifest.json` for SHA-256 checksums. The CSVs can
be evaluated from `backend` using `python -m app.check_clinic_csv data/presentation
--output data/clinic-csv-evaluation.json`; this replaces the saved evaluation, so
review it before committing. Additional retention history is still required.

## Checks

From `frontend`, run `node --test tests/*.test.mjs`, `npm.cmd run lint` and
`npm.cmd run build`. Frontend tests that inspect markup expect this working directory.
Backend tests require PostgreSQL and a separate database whose name ends in `_test`;
the suite truncates and reseeds that test database. Never point it at application
data. Run `python -m pytest tests -q -p no:cacheprovider` from `backend` in the
Linux dependency environment. The Docker build excludes tests, so mount
`backend/tests` at `/app/tests` when running them inside the API image; tests also
inspect `frontend/app/globals.css`, which must be mounted at `/frontend/app/globals.css`.
