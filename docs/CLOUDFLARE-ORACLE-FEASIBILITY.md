# Cloudflare Free versus Oracle Always Free — Phase 0 decision

Reviewed 1 November 2026. Public documentation review, not a benchmark or an account-specific quota audit. The owner reports having Oracle Always Free access. Exact active database/compute services, region and remaining allocations still need console verification.

## Recommendation

Use **Cloudflare for supported AI inference and optionally static Terra hosting; use Oracle infrastructure for the existing backend/job/database plan** if eligible compute is actually available. Do not attempt an all-Cloudflare-free migration of the entire uploaded design without changing requirements.

The blockers are capability and compatibility, not simply traffic allowances: Chronos-Bolt Small is absent from Workers AI's current catalog; Cloudflare Containers require Workers Paid; D1 uses SQLite semantics and does not replace PostgreSQL-specific locking/constraints or Oracle Database unchanged. Supported Cloudflare text models must not be presented as Chronos forecasting.

An Oracle database alone solves persistence, not the FastAPI server, OCR/extraction or Chronos compute host. Always Free account access does not establish that a VM or database is already running or that capacity is available.

## Verified public allowances and project implications

| Component | Published allowance/constraint | Fit for this project |
| --- | --- | --- |
| Static assets on Workers | Asset requests free/unlimited; storing assets has no additional cost. Worker-script invocations are metered separately. Free deployment limits include 20,000 asset files and 25 MiB per file. | Existing four-file Terra mockup fits by file count/size; future static build must be checked. This does not add backend behavior. |
| Workers Free API runtime | 100,000 requests/day, 10 ms CPU/request, 128 MB isolate memory | Lightweight API/proxy work may fit. No evidence that the complete existing Python/ML/document design fits these limits. Waiting on network I/O differs from CPU execution. |
| Workers AI | 10,000 neurons/day free; model costs vary. Certain models require paid billing. | Plausible for bounded academic text/embedding calls. No fixed number of chats can be promised before choosing models and measuring input/output usage. |
| D1 Free | 5 million rows read/day, 100,000 written/day, 5 GB total account storage; 10 databases, maximum 500 MB/database, 7-day Time Travel | Likely ample for small structured synthetic data, but requires schema/transaction redesign. 5 GB is not the single-database limit. Reads are scanned rows, not just returned rows. |
| Vectorize Free | 30 million queried dimensions/month and 5 million stored dimensions | Optional for later dense retrieval; lexical search does not require it. Account eligibility and actual query accounting must be tested. |
| Queues Free | 10,000 operations/day; 24-hour retention | Write/read/delete generally use 3 operations per small successful message; retries add operations. A queue does not provide arbitrary Python/ML compute. |
| Durable Objects Free | SQLite-backed objects available; 100,000 requests/day and 13,000 GB-s/day duration | Possible coordination/state option for a redesigned Cloudflare app; unnecessary extra service for the retained PostgreSQL job plan. |
| Workflows Free | 100,000 invocations/day shared with Workers; 10 ms CPU/invocation; 3,000 steps/day; 1 GB-month state | Durable orchestration is available, but does not provide a free unrestricted ML execution environment. |
| Containers | No Free-plan allocation; included usage belongs to the $5/month Workers Paid plan | Cannot use 'included container hours' as a ₹0 solution for Chronos/FastAPI containers. |
| Private document blobs | R2 Standard includes 10 GB-month storage, 1 million Class A and 10 million Class B operations/month, with free direct egress; separate subscription/checkout and overage billing | Infrequent Access is excluded from this free allocation. Do not treat R2 as an automatically enabled, hard-capped free store. OCI private storage is an alternative if eligible. |
| Oracle Always Free | Owner reports account access; active services, usable limits and region unverified | Can be a hybrid host after checking actual resources. Oracle Cloud hosting and Oracle Database are different choices. |

Sources: [static asset billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/), [Workers limits](https://developers.cloudflare.com/workers/platform/limits/), [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/), [D1 limits](https://developers.cloudflare.com/d1/platform/limits/), [D1 architecture](https://developers.cloudflare.com/d1/), [Vectorize allowances](https://www.cloudflare.com/products/vectorize/), [Queues pricing](https://developers.cloudflare.com/queues/platform/pricing/), [Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/), [Containers pricing](https://developers.cloudflare.com/containers/platform/pricing/), [R2 onboarding](https://developers.cloudflare.com/r2/get-started/).

Public documentation can change or disagree: during this review the general Cloudflare pricing page and Durable Objects product docs showed different SQLite read allowances. Use the service-specific page plus actual account enforcement for that product, and do not rely on the higher generic figure. All account-wide allowances are shared with other projects in the same account.

Additional sources: [Workflows pricing](https://developers.cloudflare.com/workflows/reference/pricing/), [R2 pricing](https://developers.cloudflare.com/r2/pricing/), [Vectorize service pricing](https://developers.cloudflare.com/vectorize/platform/pricing/).

## Why free Cloudflare does not host the current complete design unchanged

1. **Forecast model:** no Chronos entry was found in the [Workers AI catalog](https://developers.cloudflare.com/workers-ai/models/). Cloudflare directs private custom-model requests to its [custom requirements process](https://developers.cloudflare.com/workers-ai/platform/limits/); there is no verified ₹0 Chronos route. The [Chronos model card](https://huggingface.co/amazon/chronos-bolt-small) describes a Python/Torch inference library and CPU support, which is a separate execution requirement.
2. **Python and background work:** a normal Worker is not a full Linux VM. Cloudflare explicitly documents FastAPI support in Python Workers, using a different toolchain from the proposed local Python setup. Supported packages are pure Python, PyEmscripten wheels or Pyodide packages; this does not establish Torch/Tesseract/native driver compatibility. Every dependency and filesystem assumption needs validation. Queuing a job does not remove consumer CPU/memory limits. No forecast runtime or OCR compatibility test was run. Source: [Python Workers packages](https://developers.cloudflare.com/workers/languages/python/packages/).
3. **Database:** D1's SQLite semantics require alternatives to PostgreSQL `SELECT ... FOR UPDATE`, `timestamptz`, exclusion/partial-constraint design and the proposed PostgreSQL queue. Atomic booking can be designed for a different database, but its strategy and race tests must change; D1 is not inherently incapable of safe booking.
4. **Files and restore:** uploaded documents need private object storage plus derived-data deletion and backups. A database blob is not a complete document-storage/backup plan. R2's separate billing enrollment needs review.
5. **Cost isolation:** quotas are separate across products. A paid plan's 'included usage' is not a Free-plan entitlement. Alerts alone are not a guaranteed spending cap.

## Comparing the options

| Option | Changes required | Feasibility |
| --- | --- | --- |
| All Cloudflare Free, original scope | Worker-compatible API, D1 transaction/schema redesign, private storage decision, substitute/verified route for Chronos and OCR | Not verified for the full original scope; do not select as a drop-in plan |
| Cloudflare frontend/AI + OCI VM with PostgreSQL | Retains FastAPI/SQLAlchemy/Alembic and PostgreSQL job/locking plan; adds bounded Cloudflare provider integration | Closest match to uploaded architecture; ₹0 depends on actual free VM/storage availability and measured resource use |
| Cloudflare frontend/AI + Oracle Autonomous Database + backend/job compute | Replace PostgreSQL-specific DB design/driver/migrations/queue; provide separate compute for API and Chronos | Possible candidate, not automatically ready just because Autonomous DB exists |
| Cloudflare frontend/AI + local backend/DB/Chronos | Local development/demo, no hosted always-on backend | Useful ₹0 development fallback; hosted static frontend must not pretend local services are publicly available |

If the Oracle service is **Autonomous Database / Autonomous AI Database**, prefer a backend near it with the supported Oracle driver, TLS/wallet configuration as required by that service, a least-privilege schema and appropriate transaction tests. The browser and model must not receive database credentials. Cloudflare Hyperdrive's documented engines are PostgreSQL/MySQL-compatible; a provider named 'Oracle' in that support table means those engines hosted by Oracle, not Oracle Database wire-protocol support. Source: [Hyperdrive database compatibility](https://developers.cloudflare.com/hyperdrive/reference/supported-databases-and-features/).

If the resource is **OCI Compute**, PostgreSQL on that VM remains closest to the source plan. Verify compute, persistent volumes, network exposure, backup capacity and model RAM/runtime. A database connection test cannot prove Chronos compute is available.

### Oracle's published free resources — subject to tenancy verification

- Autonomous Always Free: up to two instances per tenancy, 20 GB storage each, maximum 30 simultaneous database sessions. These are Oracle Database resources, not free managed PostgreSQL instances.
- Important Autonomous Free limitations: no private endpoint/VCN placement and no built-in restore to a selected past backup/timestamp. It also excludes long-term/manual backups to OCI Object Storage. A separate supported logical export and restore plan must be designed and tested; do not claim the original private-database/restore architecture is satisfied unchanged.
- Compute resource documentation currently lists A1 free allocation of 1,500 OCPU-hours and 9,000 GB-memory-hours/month (described as 2 OCPUs/12 GB for Always Free tenancies), plus the documented eligible AMD micro allowance. Combined boot/block storage allowance is 200 GB. These numbers do not prove regional capacity or available remaining allocation, and a micro VM is not a proven Chronos host.
- Free resources can stop or be reclaimed under service inactivity policies. Keep independent recoverable data and verify the actual resource rules before deployment.

Sources: [Autonomous Always Free limits and exclusions](https://docs.oracle.com/en/cloud/paas/autonomous-database/serverless/adbsb/autonomous-always-free.html), [OCI Always Free resource reference](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm). The Oracle console's product names, eligibility labels and total existing consumption must be checked before selecting a shape or creating a database.

## Detailed account checks to add to Phase 0

### Cloudflare inventory

1. Sign into the intended Cloudflare account. Record its Account ID, Workers plan, existing projects and current daily/monthly usage; keep credentials private.
2. Open Workers AI, verify candidate models exist and are free-eligible. Record exact IDs and model pricing; perform only a short synthetic inference when setup checks are started.
3. Open D1, Vectorize, Queues and Durable Objects inventory pages **without provisioning**. Record whether already enabled and how much shared quota is in use. Do not enable all four just to complete a checklist; the hybrid may not need them.
4. Open R2 information/checkout only if considering R2. Record subscription/payment requirements and overage terms. Do not submit checkout until the owner chooses that storage route.
5. Confirm Containers shows Paid as a prerequisite. Keep this out of a ₹0 plan. Do not assume unused free AI allowance transfers to containers or database storage.

### Oracle inventory — owner has Always Free access

1. Sign into OCI and select the correct tenancy and home region. Record region and whether account is Always Free-only, trial, or paid with Always Free resources. Do not upgrade.
2. Open the database inventory and inspect existing instances. Record **exact product name**, lifecycle state, Always Free label, database version, allocated storage, current usage, connection methods and backup/retention features. An empty inventory means no database is provisioned yet.
3. Open Compute → Instances. Record any existing VM, shape, architecture, RAM/OCPU allocation, lifecycle state and Always Free eligibility. If no VM exists, inspect current quota/capacity but do not create one yet.
4. Open Limits/Quotas/Usage and Billing. Compare **combined existing use** with the current free allowance, and inspect storage/volume allocations. Trial credit and paid service quotas do not establish zero cost. Verify [Oracle's current free-resource rules](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm).
5. Record whether database is Oracle Autonomous DB or PostgreSQL/MySQL on Oracle-hosted compute. Share only product/shape/eligibility metadata when deciding the architecture, never wallet archives, DB passwords or private keys.
6. After selecting a route, plan a minimal encrypted connection check in the database phase: one test query, least-privilege user, correct network access and no public unauthenticated database. Do not open a database to the entire internet to make Cloudflare reach it.
7. Before deployment, verify backup/restore and idle/reclamation policies for the actual selected resources. Backups and long-term availability are not guaranteed merely by seeing 'Always Free'.

## Capacity worksheet — measure before promising full free operation

The project has no usage target or selected text model yet. These are planning calculations, not observed load tests:

- Worker daily invocations = active users × dynamic requests per user + background/retry/admin requests. Static asset hits served without invoking Worker script are separate.
- AI neurons/day = sum of each selected model's measured usage across assistant, embeddings, retries and development calls. Use bounded context/output, per-user limits and a shared account budget. No model-independent 'free chat count' exists.
- D1 rows/day = measured rows read/written across query plans, including relevant index work. Index and paginate; small response size alone does not prove low row-read use.
- Vector storage = chunk count × embedding dimensions. At 384 dimensions, 5 million stored dimensions allows about 13,020 vectors before overhead/other indexes and product limits; this is arithmetic, not a measured dataset.
- Queue operations ≈ successful small messages × 3 + retries/dead-letter work. 10,000 operations is about 3,333 such deliveries/day before retries, not 10,000 complete jobs.
- Chronos host needs measured cold start, peak memory, inference duration and concurrency at the seven-day horizon. Model weight size alone does not give process RAM.
- Add headroom for existing projects and development calls; record failure/fallback behavior at each quota. No production capacity claim until representative tests pass.

**Current decision:** hybrid recommended, not provisioned. Exact Oracle service and free compute capacity remain to be verified. No application implementation, resource creation or paid activation was performed.
