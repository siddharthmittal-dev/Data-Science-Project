# Current known issues

Updated 26 November 2026. Earlier dated notes are preserved in archive/handoffs/docs/known-issues.md.

- Windows Application Control blocks native FAISS on this laptop. Run the backend in the existing Linux Docker container.
- Docker Desktop must be running before database/API tests. Database tests target only a database ending in _test and reseed that isolated database.
- app.seed truncates application tables. Never use it to apply a migration or refresh guides in the populated application.
- The current dataset is generated. October has only four no-shows; the classifier underperformed its baseline. Additional history and follow-up are needed for independent 90-day retention evaluation.
- New accounts have separate identities. Existing fixture records are not automatically transferred to the registered patient.
- Five case PDFs share the patient presentation account by explicit user choice. Explanations require a selected record. This account is not individual authentication for the five named people; never claim separate-person privacy within it.
- Published source slugs and legacy artifact filenames remain stable for compatibility. Some internal identifiers contain historical terms; these are not product claims.
- Workload artifacts have a seven-day freshness limit. Missing published schedules are not proof of clinic closure.
- Production frontend builds may need access to the configured Google font. No dependency change was needed for verified builds.
- Registration is closed by default. Password recovery, email verification, MFA and login rate limiting are not implemented.
- The final sign-in-only screen and corrected role navigation were verified in Edge Guest on 26 November, along with the existing-data uncertainty graph and interval details. The Guest session was left signed out.
- Railway deployment, backup/restore verification and operational monitoring remain pending.
- A fresh checkout includes approved source documents and CSVs but excludes existing account access, private database contents and retrieval indexes. Rebuild indexes with your own OpenAI key; account provisioning remains a separate operator step.
