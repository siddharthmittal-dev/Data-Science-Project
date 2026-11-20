# Agentic Clinic — Phase 0 prerequisites and verification

## Current progress — 4 November 2026 (IST)

This record supersedes the earlier installation history below.

- WSL 3.0.3 installed successfully on 2 November. WSL 2 is the default, and the `docker-desktop` distribution was verified running under version 2.
- Docker Desktop 4.97.0, Docker client/server 29.9.2 and Compose 5.6.1 passed verification after startup.
- GitHub CLI authentication completed for `siddharthmittal-dev`. On 4 November, `gh repo view` confirmed `ADMIN` access to `siddharthmittal-dev/Data-Science-Project`.
- Cloudflare OAuth authentication completed and `wrangler whoami` passed again on 4 November. Authenticated catalog queries returned `@cf/meta/llama-3.1-8b-instruct-fp8` with a 32,000-token context window. A `chronos` catalog search returned an empty result.
- Azure authentication and Foundry setup are deferred at the owner's request on 4 November.
- Cloudflare account plan, remaining daily allowance and actual inference still need verification. The catalog result establishes model visibility only.

### Next account checks

1. In the Cloudflare dashboard, select the authenticated account and open Workers & Pages / Workers AI. Record the Workers plan and today's neuron usage. The published free allowance is 10,000 neurons per day, with model-specific eligibility. See [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/).
2. Once free eligibility and available allowance are confirmed, run one bounded synthetic playground request using the exact model ID above and the prompt `Reply with the word READY`. Record the response and usage.
3. Register development Google and GitHub OAuth clients using section 9, then verify the available Oracle service and resolve backend/database/forecasting placement. Azure can be revisited later.

Prepared 1 November 2026. Status: setup in progress. Phase 0 is **not complete** until the applicable checks below have evidence. Commands in this guide are instructions for subsequent setup; they have not been executed unless explicitly recorded in section 2.

**Latest setup verification: 2 November 2026 (IST).** Node 24.22.2/npm 11.19.1, Python 3.12.10 with a standard `.venv`, Wrangler 4.156.0, Azure CLI 2.91.0, GitHub CLI 2.103.3, and PostgreSQL 17.11 binaries are installed locally and version-checked. Python dependency resolution/import checks pass. The Windows `VirtualMachinePlatform` feature-enable command succeeded with exit **3010: restart required**. Docker Desktop installation and WSL runtime verification remain pending until after the restart. No automatic restart was performed. No application or cloud resource has been created. Local setup is authorized by the owner's later installation request; earlier planning-only/deferred-install instructions below are historical.

Open a project terminal with the installed tools:

```powershell
Set-Location 'C:\Users\Asus\Desktop\PROJECTS\Data-Science-Project'
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -NoExit -File .\scripts\Use-DevTools.ps1
```

This selects the project Python environment and adds the installed tools to that terminal's PATH. It leaves Windows' persistent PATH and execution policy unchanged. The script disables Wrangler debug-file logging and CLI telemetry; necessary Azure account configuration is private under ignored `.tools/azure-config/` unless `AZURE_CONFIG_DIR` was already set. Use `npm.cmd`, `wrangler.cmd`, and `az.cmd` in PowerShell. Installer archives and redundant setup environments are removed after verification rather than retained as downloads.

`requirements.txt` holds direct Python dependencies; `requirements-lock.txt` records the resolved Windows/Python versions, including transitive dependencies. These pins have passed installation and import checks; they are not a vulnerability-audit result. The database server binaries are installed, but no cluster, application schema, account credentials, or persistent service has been configured.

Storage cleanup completed: removed the task's two temporary installer/download directories, the unused Node alpha and embedded Python copies, an unused Azure Python environment, the project npm cache, and unused PostgreSQL pgAdmin/StackBuilder bundles (about 2 GiB altogether). Required Node, Python, virtual environment, CLI and PostgreSQL files remain. Shared user caches and original uploaded references were preserved. Removed installers/components can be downloaded again if needed.

Historical container installation procedure, completed on 2 November 2026:

1. In administrator PowerShell, run `wsl --install --no-distribution`, then `wsl --update`. Verify `wsl --version` and `wsl --status`. Do not install Ubuntu solely for Docker; a separate distribution is optional.
2. Reinstall Docker Desktop using its official per-user installer with the WSL2 backend. The earlier signed installer was removed after its failed prerequisite check to avoid retaining unnecessary downloads. Keep only one installer archive and delete it after successful verification.
3. Start Docker Desktop and wait for its engine to become ready. Verify `docker version` shows both client and server and `docker compose version` succeeds. Until then, do not mark Docker ready.
4. Continue provider authentication and OAuth registration from the detailed sections below. No cloud login or OAuth application has been created by the local installer work.

Follow-up: the owner reports Oracle Always Free access and requested a full Cloudflare-free feasibility comparison. Read [Cloudflare/Oracle assessment](CLOUDFLARE-ORACLE-FEASIBILITY.md) before selecting database/hosting software. The exact Oracle service is still unknown; PostgreSQL setup below is conditional on retaining the uploaded stack, not a requirement if Oracle Autonomous Database is selected.

The owner also has Azure AI Foundry access. Azure Foundry is an optional provider for the controlled assistant or evaluation experiments; it does not replace the Cloudflare feasibility decision, database, authorization, or Chronos placement. Its use must remain server-side and must be explicitly budgeted.

## 1. Scope, source authority, and architecture decisions

The current user request controls this work: use `siddharthmittal-dev/Data-Science-Project`, implement in tested phases, use Cloudflare for AI models, and do not implement anything now. The uploaded handoff's instruction to start building is reference material, not authorization to implement. Its README, `.gitignore`, scaffolding, and environment-file tasks are deferred to Phase 1.

Reference copies are in `docs/reference/`:

- `Agentic-Clinic-Terra-Frontend-Details.md`: selected Terra design and prototype limitations.
- `Agentic-Clinic-Terra-Frontend.zip`: original four-file prototype; preserved without extracting it into application source.
- `Architecture-and-development-plan.md`: architecture, feature inventory, data design, evaluation, operations, and original phase plan.
- `Original-handoff-prompt.txt`: original continuation instructions; retained as historical requirements.

Reconciliation:

| Subject | Working decision |
| --- | --- |
| Frontend | Terra is selected; the older plan's unresolved Sage/Pulse/Terra choice is superseded. |
| Application purpose | Academic coordination prototype; synthetic data only. No clinical decision making. |
| AI hosting | Cloudflare Workers AI for supported assistant/embedding models; exact model IDs require validation. |
| Core stack | Retain proposed FastAPI, PostgreSQL, SQLAlchemy, Alembic, durable jobs, and server sessions provisionally. Cloudflare AI hosting does not automatically replace these. |
| App hosting | OCI is the uploaded plan's candidate, not a verified deployment. Cloudflare for models does not by itself mean the entire application moves to Workers. |
| Forecasting | Chronos-Bolt Small remains a requirement, but its Cloudflare hosting is unresolved. Do not silently replace it with an LLM. |
| Budget | Carry forward the uploaded ₹0 target until the owner changes it. No upgrades or paid provisioning performed. |
| Phase numbering | Use the consolidated roadmap in section 12; original documents use conflicting phase numbers. |

Cloudflare **Workers** run application code; **Workers AI** executes supported managed models. Ordinary Workers have a 128 MB isolate memory limit. The current Workers AI catalog has no Chronos entry; custom private model requirements are directed to Cloudflare's custom-requirements process. There is no verified self-service, free Chronos deployment path here. This is a feasibility finding, not a proof that Cloudflare could never support it. Sources: [Workers limits](https://developers.cloudflare.com/workers/platform/limits/), [model catalog](https://developers.cloudflare.com/workers-ai/models/), [custom requirements](https://developers.cloudflare.com/workers-ai/platform/limits/).

Provisional topology: browser → same-origin API → PostgreSQL/private storage/durable background jobs; API or document worker → authenticated Cloudflare inference Worker → Workers AI binding. The browser never receives provider credentials. A separate Python job host would run Chronos **only if** the owner permits forecasting outside Cloudflare. If every model must run on Cloudflare, settle the forecasting requirement before implementation.

## 2. What was actually inspected

| Check | Observation | Status |
| --- | --- | --- |
| Repository clone | Local clone at `C:\Users\Asus\Desktop\PROJECTS\Data-Science-Project`; origin matches supplied URL | Verified |
| Remote base | `main`, commit `5673a2f` (`Initial commit`) | Verified at inspection |
| Tracked base content | Only `README.md`: project name and `Project.` | Verified |
| Working tree before planning | Clean | Verified |
| Application/backend/tests/CI | No source, dependency manifests, migrations, CI, or tests in base commit | Absent |
| ZIP inventory | `app.js` 39,630 bytes; `styles.css` 26,236; `index.html` 674; `README.md` 5,820 | Verified |
| ZIP source inspection | Terra selected in JS; synthetic arrays; scripted `sendChat`; simulated `sample`; CSV from fixed `volume` | Static inspection only |
| API connection | No `fetch`/`XMLHttpRequest` calls found in inspected prototype JS | Static inspection only |
| Browser behavior | Not exercised in this task | Pending |
| Historical 36 checks | Claimed by uploaded frontend guide, not rerun; test sources absent from ZIP | Not independently verified |
| Git | `2.55.0.windows.2` | Available |
| Windows | Windows 11 Home Single Language, 64-bit, build `10.0.26300` | Verified |
| Node/npm, Python/py, Docker, Wrangler, GitHub CLI | Not resolved by `Get-Command` in this shell | Install location/PATH needs checking; not proof of global absence |
| WSL | `wsl --status` reports not installed | Pending installation if Docker route chosen |
| RAM/free disk/virtualization | Not reliably captured in inspection | Owner checks in step 0A |
| GitHub write access, cloud accounts, OAuth credentials, billing | Not exercised/accessed; owner reports Oracle Always Free access | Account-specific resources/quotas unknown |

The initial 1 November inspection created only planning documents and reference copies. Subsequent installation work added local dependencies and tooling under the owner's explicit authorization; no application code, cloud resources, secrets, commits, or pushes were created.

Setup resolution, 2 November 2026: after the Node MSI failed with error 1603, Node 24 LTS was installed from an official archive and checked against its published SHA256. The earlier alpha runtime and embedded Python environment were removed. The signed Python installer succeeded per-user under `.tools/python/` and created a standard `.venv`. Azure CLI was installed from Microsoft's ZIP package; GitHub CLI's archive was checked against its release SHA256. PostgreSQL was installed from EDB's Windows binary archive. These tools are local to this checkout; do not rename/move `.tools/python` or `.venv` without recreating the environment. Docker's signed 4.97.0 installer failed its prerequisite check because `VirtualMachinePlatform` was disabled. The subsequent administrator feature-enable command succeeded with exit 3010, requiring a restart. Docker/WSL remain unverified until after the restart and installation checks.

## 3. Step 0A — Windows, network, and editor readiness

1. Open Settings → System → About. Record Windows version and system architecture; choose matching installers, rather than assuming ARM64 or x64 from '64-bit'.
2. Open Task Manager → Performance → CPU and check virtualization. Check Memory and File Explorer → This PC for free disk. Record RAM and free space. A working planning target is 16 GB RAM and 30 GB free for Docker, Python environments and later model caches; these are project headroom targets, not model/vendor minimums.
3. Compare with [Docker's current Windows requirements](https://docs.docker.com/desktop/setup/install/windows-install/). If virtualization is disabled, use the computer vendor's BIOS instructions before proceeding; if hardware is unsuitable, use native PostgreSQL instead of Docker.
4. Verify browser access to GitHub, Cloudflare dashboard, nodejs.org, python.org, npm registry, PyPI, and Docker registry if containers are selected. Model downloads later require Hugging Face access. Do not disable TLS verification to work around connectivity.
5. Install or open an editor of your choice. Open the **existing clone**, rather than creating a second repository or Git initialization.
6. Use one terminal environment consistently. This guide uses Windows PowerShell. WSL has its own tools and paths; installing Node inside WSL does not install it on Windows PATH.

**Pass:** hardware values recorded, required sites reachable, correct folder opens, and selected installation route is supported. If tools exist elsewhere, reopen the terminal after correcting PATH before reinstalling.

## 4. Step 0B — GitHub ownership and repository workflow

1. Sign into GitHub with the repository owner's account and enable two-factor authentication. Open the supplied repository and confirm access to Settings or the appropriate collaborator role. Cloning alone proves read access, not write permission.
2. Open PowerShell and run these read-only checks:

   ```powershell
   Set-Location 'C:\Users\Asus\Desktop\PROJECTS\Data-Science-Project'
   git --version
   git remote -v
   git branch --show-current
   git status --short
   git config --get user.name
   git config --get user.email
   ```

3. If identity is missing, set **repository-local** values when preparing to commit. Replace examples with your chosen public identity; a GitHub no-reply email can be used.

   ```powershell
   git config user.name 'Your chosen author name'
   git config user.email 'Your GitHub author email'
   ```

4. Use Git Credential Manager/browser login when a push is needed. Do not put a password/token in the remote URL. GitHub CLI is optional; browser login is sufficient for Phase 0.
5. Review repository visibility and licensing with the owner. In Settings → Actions, inspect available runner quota/permissions. Branch protections and secret scanning depend on account/repository capabilities; record actual availability.
6. Phase 1 will create a working branch and the first reviewed pull request; its successful push will verify write access. No test push is required now, and no push has been performed.

**Pass:** owner/collaborator access, origin, author identity, visibility and license decision recorded. Write access remains 'account reviewed' until a real phase branch is pushed.

## 5. Step 0C — Node.js and npm

Needed for later frontend builds and the Cloudflare Worker toolchain; the existing ZIP itself needs no npm packages.

1. Open the [official Node download page](https://nodejs.org/en/download). Select a supported **LTS** release matching Windows architecture. Choose a release also supported by [Wrangler](https://developers.cloudflare.com/workers/wrangler/install-and-update/); do not use an EOL release or pin a version copied from an old tutorial.
2. Download the official Windows installer and verify its publisher/signature. Install npm and PATH integration. Additional native compilation tools are unnecessary until a dependency demonstrates a need.
3. Close and reopen PowerShell, then run:

   ```powershell
   node --version
   npm.cmd --version
   node -p "process.platform + ' ' + process.arch"
   ```

4. If PowerShell blocks `npm.ps1`, use `npm.cmd`/`npx.cmd`; do not weaken machine-wide execution policy.
5. Record exact Node/npm versions. Phase 1 will pin the tested toolchain and commit a lockfile. Do not run `npm init`, `create-next-app`, `npm create cloudflare`, or install project dependencies in this planning task.

**Pass:** Node and npm return versions and the expected architecture in a fresh terminal.

## 5A. Step 0C-A — GitHub CLI, Azure CLI, and Wrangler

These are operator/deployment tools, not application dependencies. Install them only after Node readiness and from official sources.

1. **GitHub CLI:** download the Windows installer from [cli.github.com](https://cli.github.com/), install it, reopen PowerShell, and run `gh --version`. Authenticate with `gh auth login` using the browser flow, select the existing GitHub host and HTTPS, then verify with `gh auth status`. Use the least access required; never paste a token into the terminal. `gh auth logout` removes the local session later.
2. **Azure CLI:** install from [Microsoft's Azure CLI Windows guide](https://learn.microsoft.com/cli/azure/install-azure-cli-windows). Reopen PowerShell and run `az version`. Authenticate with `az login` in the browser, select the intended tenant/subscription with `az account show`, and do not create resources. Use `az logout` after a temporary session if desired. Azure CLI access does not grant Azure AI Foundry model access or authorize spending.
3. **Wrangler:** after Node/npm is installed, Phase 1 should install it locally in the Worker package with `npm.cmd install --save-dev wrangler@latest` and commit the lockfile. Do not install it globally or scaffold/deploy a Worker in Phase 0. Later verify with `npx.cmd wrangler --version`, `npx.cmd wrangler login`, and `npx.cmd wrangler whoami`.
4. **Docker Desktop:** use the official Windows installer and WSL2 backend only if the WSL/Docker route was selected. Verify `docker version` and `docker compose version` after reboot/startup. A client-only result is not sufficient.

**Pass:** each selected CLI returns a version; browser authentication succeeds for the intended account; no resources were created; credentials remain outside the repository.

## 6. Step 0D — Python environment

Needed for the proposed FastAPI backend and, conditionally, separate Chronos jobs.

1. Use [official Python Windows downloads](https://www.python.org/downloads/windows/). The uploaded stack proposes Python 3.11/3.12. Start compatibility review with 3.12, selecting an official patched build/install route; do not substitute the newest Python without checking dependency support. If no suitable supported Windows distribution is available, settle a supported interpreter/container version before installing dependencies.
2. Select the correct architecture, include pip and the supported launcher/manager, and enable the installer's PATH option if provided. Reopen PowerShell.
3. Check `py --list` and `py -3.12 --version` (or the installed manager's equivalent). If only `python` is provided, verify its resolved path and version before using it.
4. After software installation is authorized, verify isolation in a disposable folder **outside the repository**, for example `%TEMP%\agentic-clinic-python-check`:

   ```powershell
   $pythonCheckPath = Join-Path $env:TEMP 'agentic-clinic-python-check'
   py -3.12 -m venv $pythonCheckPath
   & (Join-Path $pythonCheckPath 'Scripts\python.exe') --version
   & (Join-Path $pythonCheckPath 'Scripts\python.exe') -m pip --version
   ```

5. Activation is optional; explicit interpreter paths avoid execution-policy issues. Do not install FastAPI, Torch, Chronos, OCR or database libraries yet. Pin and test them together in their appropriate phases.

**Pass:** interpreter and pip work, isolated environment creation succeeds, exact version/architecture recorded. Python dependency compatibility is a later phase test, not inferred from installation.

## 7. Step 0E — Local PostgreSQL route

Use PostgreSQL for booking transactions and race tests. SQLite is not an equivalent substitute for those checks. Select **one** route to avoid two servers competing for port 5432.

### Preferred development route: WSL2 and Docker Desktop

1. Check [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install) and Docker hardware/OS requirements from step 0A.
2. When installing prerequisites, open PowerShell as Administrator, run `wsl --install`, and reboot when requested. On first Ubuntu start, create the Linux username/password locally.
3. Run `wsl --update`, `wsl --status`, and `wsl --list --verbose`. Confirm WSL2; update the selected distribution to version 2 if needed using Microsoft's instructions.
4. Install Docker Desktop from its official Windows guide. Review its license for your usage, select WSL2 backend/Linux containers, and start Docker Desktop. Enable integration only for the intended distribution if using a WSL workflow.
5. In a fresh terminal run `docker version` and `docker compose version`. Both client **and server** must respond; client-only output is not a pass.
6. Optional environment smoke check: `docker run --rm hello-world`. This downloads/runs a disposable image; no project services are created. Record success and Docker/Compose versions.
7. Phase 1 will define a pinned PostgreSQL image, persistent volume, health check and localhost-only development binding; Phase 2 creates migrations. There is no Compose file to run now.

### Alternative: native Windows PostgreSQL

1. Use the installer linked from [postgresql.org](https://www.postgresql.org/download/windows/). Select a supported stable version; avoid release candidates. Record exact major/minor and align future CI/deployment with it.
2. Install server and command-line tools; pgAdmin is optional. Store the administrator password privately. Skip optional StackBuilder packages unless later needed.
3. Bind to localhost, select an available local port, and prevent inbound public network access. Do not configure the application to use the superuser.
4. Check `psql --version` using the installed `bin` directory if it is not on PATH. Connect with an interactive password prompt and run `SELECT version();` and `SHOW listen_addresses;`.
5. Phase 2 will create separate application/test roles and databases with appropriate privileges. Do not create a schema or seed application data now.

**Pass:** one route selected; Docker daemon/Compose works, or native PostgreSQL responds locally. Application connection, constraints and concurrency are tested in Phase 2/4, not Phase 0.

## 8. Step 0F — Cloudflare account, access, model feasibility, and cost

### Account readiness without deployment

1. Open [Cloudflare dashboard](https://dash.cloudflare.com/), sign up/sign in, verify email, and enable MFA. Select the intended account; record its non-secret Account ID privately in the setup record.
2. Open Workers & Pages/Workers AI (dashboard labels can move). Review the actual Workers plan, existing usage and billing settings. Retain Free unless the owner explicitly chooses otherwise.
3. Read [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/). At review, Free includes 10,000 neurons/day; requests fail after the applicable free limit rather than providing unlimited usage. Some models require paid billing access. Check the selected model's eligibility and usage, not just the account plan. Reset is 00:00 UTC, which is 05:30 IST.
4. Do not enable paid Workers, prepaid AI Gateway credits, R2, Vectorize or Queues solely because examples mention them. Each has separate eligibility/billing implications. None is necessary for lexical retrieval or basic Workers AI access in this proposed design.
5. Check [Workers AI catalog](https://developers.cloudflare.com/workers-ai/models/) in the chosen account. For assistant candidates record ID, task, license/terms, context/input/output limits, paid/free eligibility, and availability. For embeddings record dimensions and input limits; `@cf/baai/bge-small-en-v1.5` is a candidate, not a final selection. See its [model page](https://developers.cloudflare.com/workers-ai/models/bge-small-en-v1.5/).
6. Do not copy the model ID from a quickstart unquestioningly: during review, the quickstart's `llama-3.1-8b-instruct` model link redirected to an unavailable-model page. Verify current availability directly before selecting.
7. Record the forecasting decision: retain Chronos on a separate Python job host, obtain a verified Cloudflare custom-model route, or revise the model requirement with owner/instructor agreement. A text model generating a list of numbers is not a Chronos integration or equivalent evaluation.

**Pass:** account access and Free status verified, current supported model candidates recorded, no accidental paid activation, forecasting placement resolved. Account-specific access has not been verified by this task.

### Optional Phase 0 model-access check without application code

Only run this when ready to consume the free model allowance. It is a setup check, not an assistant implementation.

1. Prefer the dashboard model playground. Select a verified free-eligible text model and submit a short synthetic prompt such as 'Reply with the word READY'. Bound output where the interface permits.
2. Record the exact model ID, timestamp, success/error and usage. Never paste credentials or real documents into the test.
3. If the playground is unavailable and REST access is selected, follow [Cloudflare's REST setup](https://developers.cloudflare.com/workers-ai/get-started/rest-api/): Workers AI → Use REST API → Create Workers AI API Token; review the template, restrict it to the intended account, and store it privately. A manual token currently needs Workers AI Read and Edit permissions. Do not use the Global API Key.
4. Use the model page's exact request schema and an in-memory/local secret mechanism, not a literal token in a command saved to shell history. Confirm one successful short response; record metadata only, then revoke temporary credentials if no longer needed.
5. Treat 401/403 as access issues, 429 as quota/rate issues and unavailable-model errors as catalog/configuration issues. Do not repeatedly retry or upgrade to paid to make a check pass.

**Pass:** actual inference response and usage evidence. Merely seeing the catalog or creating an account is not proof of inference access. This check is still pending.

### Worker toolchain and later deployment boundary

1. Node readiness must pass first. [Wrangler supports Windows 11 and supported Node release lines](https://developers.cloudflare.com/workers/wrangler/install-and-update/).
2. In Phase 1, create the reviewed Worker package and install **project-local**, pinned Wrangler; commit its lockfile. Check `npx.cmd wrangler --version`, then use `npx.cmd wrangler login` and `npx.cmd wrangler whoami` to verify the intended account. No global Wrangler or scaffolding is required now.
3. Add an `AI` binding in the reviewed Worker configuration when implementing the provider adapter. Bindings avoid a Workers AI token in Worker application code. Workers AI calls from local development still use remote inference and consume usage.
4. Before deploying an inference Worker, implement backend-to-Worker authentication, strict operation/model allowlists, input/output bounds, timeouts, rate limits and redacted logs. CORS does not authenticate a public endpoint. Never ship an anonymous inference relay.
5. Put Worker secrets in Cloudflare secret storage and corresponding local secrets in an ignored local development file; keep API-side credentials server-only. Follow [Workers secrets](https://developers.cloudflare.com/workers/configuration/secrets/). Deployment and application routing occur in later phases.

**Pass now:** Node/account prerequisites recorded. Wrangler/binding/authentication/deployment checks are explicitly deferred to their implementation phases; no sample Worker is deployed in Phase 0.

## 9. Step 0G — OAuth, URL and session prerequisites

Choose a stable public origin later; use `http://localhost:8000` as the provisional API origin for local setup. Proposed callbacks are `/api/v1/auth/google/callback` and `/api/v1/auth/github/callback`. These paths are a planning convention; no endpoints exist yet. Keep frontend development routing same-origin through a proxy when built.

### Google OIDC

1. Sign into [Google Cloud Console](https://console.cloud.google.com/) and create/select a dedicated project for Agentic Clinic authentication; no paid API is required merely for this plan.
2. Open Google Auth Platform or APIs & Services credentials, as shown in the current console. Configure branding, support/developer email and the appropriate audience. For an external academic demo, use testing mode and explicitly add intended test accounts.
3. Create an OAuth client of type Web application. Add the exact local callback URL `http://localhost:8000/api/v1/auth/google/callback`. Add frontend JavaScript origins only if the eventual login library/flow requires them; a server redirect flow is the intended design.
4. Request only `openid`, `profile`, `email` for identity. Save the client ID and secret privately; use separate development/production clients. A Cloudflare API token and a Google OAuth client secret are unrelated credentials.
5. Later add the exact production HTTPS callback after host/domain selection. Do not invent a live hostname. Follow [Google OIDC documentation](https://developers.google.com/identity/openid-connect/openid-connect).

### GitHub OAuth

1. GitHub → Settings → Developer settings → OAuth Apps → New OAuth App; see [official registration steps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).
2. Register a development app with homepage `http://localhost:8000` and callback `http://localhost:8000/api/v1/auth/github/callback`.
3. Save client ID and generated client secret privately. Use a separate production app/configuration for the final origin; request only necessary identity scopes, never repository scopes just for login.
4. No login test can pass until backend callbacks exist. Registration success means credentials are ready, not that sessions/authorization are implemented.

**Pass:** owner access, consent/test-user settings, client registration and exact redirect records available. During Phase 3 test state/PKCE, Google nonce/claims, session rotation, CSRF, logout and denial across roles/clinics. GitHub OAuth is not assumed to be Google-style OIDC.

## 10. Step 0H — Hosting, persistence, secrets, and data readiness

## 10A. Step 0H-A — Azure AI Foundry setup

Perform these steps in the Azure portal; do not paste keys, connection strings, or private endpoints into chat or Git.

1. Sign in at [ai.azure.com](https://ai.azure.com/) with the Azure account that owns the subscription. Confirm the intended Microsoft Entra tenant, subscription, resource group, region, and whether the subscription is free/student/credit-based or pay-as-you-go.
2. Open **Microsoft Foundry** (the portal may still show Azure AI Studio labels), create or select a project, and record only the project name, resource name, subscription ID suffix, region, and deployment status. Do not create a new paid resource until the owner verifies quota and billing.
3. In the project's **Models + endpoints** catalog, select a small, currently available model for coordination text only. Record its provider/model ID, deployment name, API version, context/output limits, region, quota (TPM/RPM), content-safety configuration, and whether it is serverless or provisioned. Model availability and pricing are account/region-specific.
4. Prefer Microsoft Entra ID / managed identity for a deployed backend. For local-only testing, create a narrowly scoped project credential only if the portal supports it, store it in the local secret manager, set an expiry/rotation date, and never put it in `.env.example`, frontend code, logs, screenshots, or a URL. Do not use a subscription owner key.
5. In the project settings, record the endpoint hostname and deployment name. The future backend/provider adapter will call the endpoint from the server; the browser will call our API, never Azure directly. Use the official Azure AI Foundry SDK/API documentation for the current endpoint format rather than copying an old OpenAI-compatible example.
6. Configure content filters and safety settings appropriate for an academic clinic coordinator. The assistant must refuse diagnosis, prescribing, emergency triage, and autonomous appointment changes. Generated text may propose a typed action, but only the server can authorize and execute a confirmed mutation.
7. Set Azure Cost Management budgets and alerts for the subscription/resource group if available. Alerts are not a hard spend cap. Record the budget owner, alert recipients, region, quota, and any free/student-credit expiration. Do not activate a paid tier to overcome a quota without explicit approval.
8. Run one short synthetic smoke test in the Foundry playground only after confirming the selected model's pricing/allowance. Use a prompt such as `Return READY and no other text.` Record timestamp, model deployment name, latency, token usage if shown, safety result, and failure mode. Do not upload documents or real health data.
9. Phase 1 will add an Azure provider adapter behind a configuration flag and mocked tests. It will enforce input/output token limits, timeouts, retries, rate limits, redacted structured logs, provider/model metadata, and deterministic fallback behavior. Do not install an Azure SDK or call the endpoint from this Phase 0 checklist.
10. If Azure Foundry will be used instead of Cloudflare for assistant text, record that as a provider decision. Keep Cloudflare for any separately approved supported model/embedding use. Never present Azure text generation as Chronos forecasting.

**Azure pass criteria:** project/region/model deployment and quota are recorded; credential method is chosen and kept private; budget/credit status is understood; one synthetic test is evidenced; provider placement and fallback are documented. Account-specific access and pricing are not verified by this repository inspection.

Useful official references: [Microsoft Foundry overview](https://learn.microsoft.com/azure/ai-foundry/what-is-azure-ai-foundry), [Foundry model catalog](https://learn.microsoft.com/azure/ai-foundry/concepts/foundry-models-overview), [Azure OpenAI authentication](https://learn.microsoft.com/azure/ai-services/openai/how-to/managed-identity), and [Azure Cost Management](https://learn.microsoft.com/azure/cost-management-billing/costs/quick-acm-cost-analysis).

### Hosting decision before provisioning

1. Confirm whether OCI remains the backend/database/job host. Cloudflare AI is compatible with retaining that host; switching the entire app to Workers would require a separate architecture decision for FastAPI dependencies, PostgreSQL access, filesystem persistence and background jobs.
2. For OCI, owner signs into their tenancy and records home region, available Always Free resources, compute architecture, remaining quota and actual billing status. Do not treat old quota numbers or trial credit as a free-resource guarantee. Use the original architecture's OCI checklist as a candidate deployment runbook, then verify [current free-resource rules](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm) in the actual tenancy before creating anything.
3. Check whether course requirements explicitly require Oracle deployment. If no account/eligible capacity exists, record local-only fallback. Account verification, payment details and resource creation are not prerequisites for local Phase 1.
4. Record DNS/domain ownership if public deployment is planned. A workers.dev URL can address a Worker; it does not itself host the retained OCI application or solve its OAuth/cookie origin configuration. Decide the complete public routing before registering production callbacks.
5. Choose private persistence for PostgreSQL, documents/derived indexes and, conditionally, Chronos model cache. Define backup destination, retention, restore owner, disk headroom and encryption needs. Do not create storage products yet.

**Pass:** host choice or explicit local-only scope, cost/availability evidence before any future provisioning, public-origin ownership or deferred production URL. Actual VM/TLS/backup restore are deployment-phase checks.

### Configuration inventory (names only; not an environment file)

| Category | Proposed names | Handling |
| --- | --- | --- |
| Application | `APP_ENV`, `PUBLIC_BASE_URL`, `ALLOWED_ORIGINS` | Public URL/origin values are exact, not wildcard guesses |
| Database | `DATABASE_URL`, separate test database setting | Credentials server-only; PostgreSQL private |
| Sessions | `SESSION_SECRET`, `CSRF_SECRET` if required by chosen library | Generate securely later; server-only |
| OAuth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Secrets server-only; separate dev/prod |
| Cloudflare admin | `CLOUDFLARE_ACCOUNT_ID`, scoped API token if REST chosen | Account ID isn't a password; token is secret |
| Inference Worker | `AI` binding, `AI_WORKER_URL`, `AI_WORKER_AUTH_SECRET`, selected model settings | Binding belongs in Worker config; relay auth shared server-to-server |
| Files/jobs | `DOCUMENT_ROOT`, `MAX_UPLOAD_BYTES`, `WORKER_CONCURRENCY`, timeouts | Private paths, explicit bounds; final names in Phase 1 |
| Forecast | `CHRONOS_MODEL_ID`, `CHRONOS_MODEL_REVISION`, `MODEL_CACHE_DIR`, `FORECAST_HORIZON` | Conditional on host decision; horizon seven days |

1. Choose a password manager or equivalent private secret store. Store no secret in Git, screenshots, chat, frontend bundles, CI logs or URLs.
2. Phase 1 creates `.gitignore` **before** local secret files. Ignore `.env*` except placeholder examples, `.dev.vars*`, venvs, node modules, DB files/dumps, uploads, models, caches and logs as appropriate. Keep original synthetic reference ZIP trackable.
3. Phase 1 creates placeholder-only `.env.example` and validates required variables; CI uses synthetic credentials and mocked inference rather than paid calls.
4. Prepare fictional clinics, roles and clinic guides. Record generator seed, dataset hash/version, timezone and cutoff rules when generators are implemented.
5. Forecast target stays daily scheduled appointment count, seven-day horizon, not true patient demand. Evaluation must compare Chronos to previous-same-weekday baseline at identical chronological cutoffs. Preserve closure days, missing-vs-zero rules, MAE/bias/per-horizon errors and interval coverage/width requirements from the original handoff.
6. Prepare a small authorized question/source fixture for later retrieval evaluation. Dense retrieval, OCR and model downloads are later optional capabilities, not blanket Phase 0 installs. Lexical/extractive fallback remains required.

**Pass:** secret ownership, persistence/retention plan and synthetic-data rules recorded; no real patient data, generated fixtures or credentials committed now.

## 11. Phase 0 exit record

Update with evidence as each setup step is actually completed. Do not mark an account or dependency ready from this document alone.

| Gate | State | Evidence needed |
| --- | --- | --- |
| Clone and base inspection | Done | Commit/origin/inventory in section 2 |
| Uploaded references preserved | Done | Original copies and hash comparison |
| Windows architecture/resources/network | Partial | OS checked; installer architecture, RAM/disk/virtualization/network record |
| GitHub identity/account access | Verified | Authenticated as siddharthmittal-dev; repository ADMIN access verified 4 November; branch push deferred |
| Node/npm | Installed, verified | Node 24.22.2, npm 11.19.1, x64; official archive SHA256 matched |
| Python | Installed, verified | Signed installer, Python 3.12.10, standard `.venv`, requirements installed, `pip check` and imports pass |
| PostgreSQL development route | Binaries ready; server pending | PostgreSQL/psql 17.11 verified; no database cluster/service initialized |
| Cloud CLIs | Installed; GitHub/Cloudflare authenticated | Azure login and Foundry deferred by owner on 4 November |
| Docker/WSL | Verified | WSL 3.0.3, Docker Desktop 4.97.0, client/server 29.9.2, Compose 5.6.1; docker-desktop running with WSL 2 |
| Cloudflare account/cost | Partial | Account access and catalog verified; Free plan, usage and model eligibility still require evidence |
| Cloudflare model access | Pending | One actual synthetic inference and usage record |
| Chronos placement | Decision required | Separate host permitted or verified Cloudflare route/revised requirement |
| Google/GitHub registration | Pending | Development clients and exact callbacks stored privately |
| Backend hosting | Pending | OCI retained or local-only/alternative explicitly recorded |
| Public origin | Deferred if local-only | Domain/routing evidence before deployment |
| Secrets/data/backup ownership | Pending | Owner and retention decisions |
| Course acceptance | Pending | Instructor accepts synthetic data, models, evaluation and hosting choices |

Evidence template for each gate: date/time (IST), command or console screen, actual version/model/account-plan metadata, pass/fail, safe error description, next action. Never attach token values. If setup is blocked, record the precise failing check and continue unrelated prerequisites.

Minimum Phase 1 entry: local toolchain and database route available; Cloudflare/forecasting architecture decision recorded; owner access and budget confirmed; setup blockers explicit. Cloud account inference and OAuth registration may be scheduled before their phases if the owner chooses local-first work, but then Phase 0 must be recorded as **partial**, not 'all prerequisites complete'. Each later phase requires its own passing tests before advancing.

## 12. Consolidated implementation roadmap — deferred

| Phase | Scope | Required exit evidence |
| --- | --- | --- |
| 0 | This prerequisite setup and decision record | Applicable readiness gates above pass |
| 1 | Repository foundation, frontend/backend packages, config, health/readiness, CI, local tooling; Worker tooling when needed | Repeatable clean install, lint/type checks, health and CI tests; no committed secrets |
| 2 | PostgreSQL schema, migrations, roles/scopes and synthetic generator | Empty DB migrates/seeds; constraints and dataset reproducibility checked |
| 3 | Google/GitHub login, secure server sessions, CSRF, role/clinic policies | Login/logout, expiry/replay, cross-user/cross-clinic denial tests |
| 4 | Doctors, slots, booking/rescheduling/cancellation and audit/idempotency | Concurrent PostgreSQL booking produces exactly one winner; retries and rollback tested |
| 5 | Deterministic assistant, proposals/confirmation, Cloudflare text adapter after evaluation | No mutation without confirmed, revalidated one-use proposal; provider failure and model-output validation tested |
| 6 | Private uploads, bounded extraction/OCR where needed, lexical retrieval; Cloudflare embeddings after evaluation | Isolation/deletion/injection/citation tests and retrieval evaluation |
| 7 | Scoped analytics, metric definitions and CSV/JSON exports | Independent fixtures validate counts, filters and zero denominators |
| 8 | Resolved forecasting host, baseline, Chronos jobs and rolling evaluation | Reproducible seven-day forecasts, provenance and measured baseline comparison; limits/fallback tested |
| 9 | Terra production frontend and API/Insights integration | Functional mobile/desktop flows, loading/error/stale states, accessible chart/table and browser tests |
| 10 | Chosen host deployment, authenticated Worker relay, HTTPS, persistence, backups, monitoring | Approved resources, private internals, live inference, OAuth, restart/restore and usage checks |
| 11 | Security/accessibility review, end-to-end tests, instructor report/demo and handoff | Documented test evidence, honest limitations, reproducible demo and runbook |

Terra's original appearance and interaction reference remains authoritative during Phase 9. Frontend integration may be developed alongside feature phases only when explicitly started; no additional design concept/backend is introduced. Keep all detailed entity/API/security/forecast requirements from the uploaded handoff unless a recorded decision supersedes them. API naming conflicts between source documents must be settled once in Phase 1, with a single versioned OpenAPI contract.

## 13. What is deliberately not installed or implemented yet

No Next.js project, FastAPI service, schema, OAuth login, inference Worker, RAG pipeline, Chronos adapter, CI workflow, environment file, deployment or paid cloud resource exists from this task. Installed packages are prerequisites, not working features. Checks performed: tool versions, standard virtual-environment creation, Python dependency consistency/imports, native workerd/esbuild executables, Node/GitHub CLI checksums, signed Python/Docker installers, and terminal tool selection. No application tests exist yet. Next: finish Windows' Docker/WSL prerequisites, authenticate the cloud CLIs, register the development OAuth clients, verify account quotas, and resolve Chronos/database placement. Enter credentials only in provider login flows or ignored local secret storage; do not paste keys into chat.
