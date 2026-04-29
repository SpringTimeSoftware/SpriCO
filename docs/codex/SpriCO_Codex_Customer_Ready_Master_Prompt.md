# SpriCO Codex Master Prompt — Customer-Usable AI Audit Platform Stabilization

## Purpose

You are Codex working inside the public SpriCO repository:

This is a critical product-hardening phase. The goal is not to add random features. The goal is to make SpriCO behave like a coherent, customer-usable AI audit and red-teaming platform for expert users.

The product must be credible for senior AI auditors. It must preserve existing functionality, preserve old data, remove misleading UI states, unify reporting, and add promptfoo-style evaluation/comparison capabilities in a controlled way.

## Non-negotiable principles

1. Preserve existing user workflows.
2. Preserve old data.
3. Do not create disconnected pages or disconnected stores.
4. Do not make garak, promptfoo, PyRIT scorers, OpenAI Judge, DeepTeam, SHAP, or LIME the final verdict authority.
5. SpriCO PolicyDecisionEngine remains the final verdict authority.
6. External engines produce evidence, probes, assertions, or explanations only.
7. All run types must feed one unified reporting/history/evidence/finding model.
8. Findings must remain actionable issues only.
9. No-finding runs are still audit coverage and must appear in reports/dashboards/history.
10. Do not apply SHAP/LIME to LLM red-team traces incorrectly. SHAP/LIME are explainability methods for classical ML/tabular/classifier-style models, not direct replacements for GenAI prompt-response evidence.
11. No destructive DB migrations.
12. No broad UI redesign. Keep existing UI and currentView model intact unless a specific issue requires minimal change.
13. Do not introduce React Router.
14. Do not break existing PyRIT-backed Interactive Audit / Attack History.
15. Do not touch live dbdata except through safe migrations/backfills with backup and tests.
16. Every feature must have tests and docs.
17. If something is partial, say partial.
18. If something is metadata-only, say metadata-only.
19. If something is not implemented, say not implemented.

## Current repo facts to respect

Based on current repository inspection:

* `pyproject.toml` still identifies the package as `pyrit`, version `0.11.1.dev0`, MIT license, with optional dependency `garak = \["garak>=0.13.0"]`.
* The FastAPI backend is registered in `pyrit/backend/main.py`.
* `pyrit/backend/main.py` warns that direct `uvicorn pyrit.backend.main:app` is not the full initialization path and prefers the `pyrit\_backend` CLI for full initialization.
* `pyrit/backend/routes/garak.py` currently exposes garak status, plugin discovery, profiles, scan creation, reports, artifacts, and findings.
* The garak request model already supports `cross\_domain\_override` and `judge\_settings`.
* `pyrit/backend/routes/garak.py` currently treats garak as scanner evidence and still uses SpriCO policy context for final verdict.
* `pyrit/backend/sprico/storage.py` currently implements generic JSON-payload collections in SQLite, not a mature SaaS relational schema.
* `pyrit/backend/sprico/storage.py` collections include `projects`, `policies`, `policy\_versions`, `custom\_conditions`, `condition\_versions`, `condition\_simulations`, `condition\_approvals`, `condition\_tests`, `condition\_audit\_history`, `scans`, `scan\_results`, `findings`, `evidence\_items`, `audit\_history`, `shield\_events`, `garak\_runs`, `garak\_artifacts`, and `red\_scans`.
* `docs/product/PYRIT\_USAGE\_AUDIT.md` states:

  * Interactive Audit uses PyRIT targets, PromptNormalizer, CentralMemory, AttackResult, Message, and MessagePiece.
  * Attack History reads PyRIT CentralMemory.
  * Structured Audit uses PyRIT-backed attack sessions and targets.
  * LLM Vulnerability Scanner is garak-based, with PyRIT used mainly for target validation.
  * Red Team Campaigns does not currently run PyRIT orchestrators.
  * Evidence Center is SpriCO-native.
  * Shield is SpriCO-native.
* `docs/product/PAGE\_BY\_PAGE\_PRODUCT\_REVIEW.md` states Red Team Campaigns is partial and currently SpriCO-native.
* `docs/product/REPORTING\_AND\_HISTORY\_INTEGRATION\_REPORT.md` states Scanner Run Reports and dashboard coverage were improved, but Activity History remains a lightweight ledger and target-specific drilldowns remain shallow.
* The product currently has separate stores/surfaces:

  * `pyrit.db` / PyRIT memory for interactive attack sessions and PyRIT Attack History
  * `audit.db` for Audit Workstation / structured audit / benchmark library style data
  * `sprico.sqlite3` for evidence, findings, Shield, Red, garak runs, policies, projects, custom conditions
  * `dbdata/garak\_scans/` for garak artifacts

Do not erase this history. Improve it.

\---

# Work packages

You must complete this work in phases. Each phase must be individually testable. Do not skip phases.

## Phase 0 — Repository and data model audit

### Goal

Before changing code, produce a factual inventory of current runtime flows, databases, API routes, and UI pages.

### Deliverable

Create:

`docs/product/CUSTOMER\_READY\_PRODUCT\_AUDIT.md`

### Include

1. Current pages and status:

   * Home / Landing
   * Interactive Audit
   * PyRIT Attack History
   * Activity History
   * Audit Workstation / structured audit
   * Benchmark Library
   * LLM Vulnerability Scanner
   * Scanner Run Reports
   * Evidence Center
   * Findings
   * Red Team Campaigns
   * Shield
   * Policies / Projects
   * Custom Conditions
   * Dashboards
   * Diagnostics / Storage Diagnostics
   * Open Source Components
2. For each page:

   * purpose
   * actual implementation
   * data read
   * data written
   * current status: active / partial / metadata-only / diagnostic / legacy
   * issue list
   * required fix
3. Current databases/stores:

   * `pyrit.db`
   * `audit.db`
   * `sprico.sqlite3`
   * JSON fallback file
   * garak artifact folder
   * uploaded media/artifacts
   * target secrets
   * any target/policy/condition stores
4. Current APIs:

   * `/api/attacks`
   * `/api/activity/history`
   * `/api/audit/\*`
   * `/api/scans/garak\*`
   * `/api/evidence`
   * `/api/red/\*`
   * `/api/shield/check`
   * `/api/policies`
   * `/api/projects`
   * `/api/conditions`
   * `/api/storage/status`
   * `/api/version`
   * `/api/judge/status`
   * `/api/targets`
5. Current engine reality:

   * PyRIT: active in Interactive Audit / structured audit / target registry / memory
   * garak: active optional scanner engine
   * promptfoo: not integrated runtime yet
   * DeepTeam: not integrated runtime yet
   * OpenAI Judge: optional evidence only, disabled unless configured
   * SHAP/LIME: not implemented and should be scoped to classical ML explainability only

### Acceptance

No code changes in this phase except docs.

\---

## Phase 1 — Stop misleading pages and labels

### Goal

Make the product truthful to expert users before adding more features.

### Required fixes

1. Red Team Campaigns:

   * must clearly state current engine is SpriCO-native
   * must clearly state PyRIT orchestrator runtime is not yet implemented
   * must clearly state promptfoo runtime is not yet implemented
   * must clearly state DeepTeam runtime is not yet implemented
   * must not show metadata-only engines as executable options
   * executable engines and coming-soon engines must be visually separated
2. LLM Vulnerability Scanner:

   * must state garak is an optional scanner evidence engine
   * must state garak output is evidence, not final verdict
   * must show scan scope clearly: target, policy, profile, categories, probes, artifacts
   * PASS must be written as "PASS for selected scan scope"
   * no-finding runs must say they do not prove global safety
3. PyRIT Attack History:

   * must be labeled PyRIT Attack History
   * must say it is PyRIT memory-backed and not universal history
   * must link to Activity History, Scanner Run Reports, Evidence Center, Findings
4. Activity History:

   * must be the cross-workflow activity ledger
   * must include link cards/categories for:

     * PyRIT attack sessions
     * Interactive/Audit runs
     * LLM scanner runs
     * Red Team Campaigns
     * Shield events
     * Evidence
     * Findings
5. Custom Conditions:

   * must clearly say conditions are safe declarative signals
   * must say no Python/JS/shell/SQL code execution
   * must say conditions do not directly set final verdict
6. Evidence Center:

   * must say Evidence Center is proof storage
   * must distinguish evidence vs finding vs history
7. Findings:

   * must say Findings are actionable issues only
   * no-finding scanner runs must not appear as Findings

### Tests

Add frontend tests to confirm:

* no UI contains "Choose final scoring engine"
* Red page shows promptfoo/DeepTeam as not implemented or coming soon if visible
* LLM scanner says garak evidence only
* PASS text includes "selected scan scope" for no-finding scanner results
* Attack History empty state explains PyRIT scope
* Activity History has scanner/run links

\---

## Phase 2 — Unified run registry and reporting architecture

### Goal

Every execution source must produce a normalized run record. This is the most important product-quality fix.

### Problem

SpriCO currently has separate stores and pages:

* Audit Workstation writes into audit-related data
* Interactive Audit writes PyRIT memory and saved audit records
* garak writes garak runs/artifacts/evidence
* Red writes red scans
* Shield writes Shield events/evidence
* Custom Conditions write condition events
* dashboards and reports do not have a single canonical run model

This makes SpriCO feel like separate tools rather than a serious audit platform.

### Required design

Create a unified run registry abstraction.

It may initially be implemented over the existing `sprico.sqlite3` JSON-payload store, but the schema must be forward-compatible with SQL Server.

Run types:

* `interactive\_audit`
* `audit\_workstation`
* `benchmark\_replay`
* `garak\_scan`
* `sprico\_auditspec`
* `promptfoo\_runtime`
* `red\_campaign`
* `shield\_check`
* `custom\_condition\_simulation`
* `manual\_import`
* `ml\_explainability`

Each run record must include:

* `run\_id`
* `run\_type`
* `source\_page`
* `target\_id`
* `target\_name`
* `target\_type`
* `domain`
* `policy\_id`
* `policy\_name`
* `engine\_id`
* `engine\_name`
* `engine\_version`
* `status`
* `evaluation\_status`
* `started\_at`
* `finished\_at`
* `duration\_seconds`
* `evidence\_count`
* `findings\_count`
* `final\_verdict`
* `violation\_risk`
* `coverage\_summary`
* `artifact\_count`
* `created\_by`
* `metadata`
* `legacy\_source\_ref`

### Required backfill

Do not delete existing records.

Create additive backfill functions that map existing records into unified run records:

* garak runs -> `garak\_scan`
* red scans -> `red\_campaign`
* shield events -> `shield\_check`
* audit runs -> `audit\_workstation`
* interactive replay/audit runs -> `interactive\_audit`
* custom condition simulations -> `custom\_condition\_simulation`

### API

Add:

* `GET /api/runs`
* `GET /api/runs/{run\_id}`
* `GET /api/runs/summary`
* `GET /api/runs/by-target/{target\_id}`
* `GET /api/runs/{run\_id}/evidence`
* `GET /api/runs/{run\_id}/findings`

Do not break existing APIs.

### UI

Activity History must use the unified run registry where available.

Dashboard must use unified run summary where available.

Scanner Run Reports can remain specialized but must link to run record.

Audit Workstation run results must link to run record.

Interactive Audit saved runs must link to run record.

### Tests

* garak scan creates unified run record
* audit workstation run creates unified run record
* red campaign creates unified run record
* shield check creates unified run record
* no-finding garak scan appears in unified run summary
* no-finding garak scan does not create finding
* Activity History displays unified runs
* Dashboard includes unified runs
* old APIs still pass tests

\---

## Phase 3 — Evidence model hardening

### Goal

Every report/log must have proper evidence. Evidence must be normalized, linkable, and explainable.

### Required model

Every evidence item must include:

* `evidence\_id`
* `run\_id`
* `run\_type`
* `source\_page`
* `target\_id`
* `target\_name`
* `target\_type`
* `policy\_id`
* `policy\_name`
* `engine\_id`
* `engine\_name`
* `engine\_type`
* `engine\_version`
* `raw\_input`
* `raw\_output`
* `retrieved\_context`
* `tool\_calls`
* `scanner\_artifact\_refs`
* `assertion\_results`
* `matched\_signals`
* `matched\_conditions`
* `policy\_context`
* `authorization\_context`
* `data\_sensitivity`
* `sprico\_final\_verdict`
* `violation\_risk`
* `explanation`
* `linked\_finding\_ids`
* `created\_at`

### Source-specific rules

1. Interactive Audit:

   * one evidence item per scored assistant turn if scoring exists
   * link to PyRIT attack/session/message IDs
2. Audit Workstation:

   * one evidence item per executed test/variant result
   * link to audit run, test ID, variant ID, target ID
3. garak:

   * one evidence item per scanner hit/actionable result
   * run-level metadata must still exist even when evidence\_count=0
   * raw artifact references must be stored
4. Red Team Campaigns:

   * one evidence item per campaign prompt/response result
5. Shield:

   * one evidence item per check/event where meaningful
6. AuditSpec / promptfoo:

   * one evidence item per assertion/test result

### UI

Evidence Center must show:

* source page
* run ID
* target
* policy
* engine
* final verdict
* risk
* evidence detail
* raw JSON collapsed
* links to finding/run/report

### Tests

* evidence item created for Audit Workstation run
* evidence item created for garak hit
* run-level record created even for no-finding garak scan
* Evidence Center filters by run\_id, target\_id, engine, verdict, risk
* Evidence links to Findings and source run

\---

## Phase 4 — Findings consistency

### Goal

Findings must remain actionable issues only, but every actionable evidence item must create/link to a finding.

### Required rules

Create Finding when:

* final verdict = FAIL
* or risk = HIGH / CRITICAL
* or high-sensitivity NEEDS\_REVIEW
* or policy demands escalation

Do not create Finding when:

* scan completed\_no\_findings
* validation failed without evidence
* timeout/failed run with no evidence
* informational run coverage

Finding fields:

* `finding\_id`
* `run\_id`
* `evidence\_ids`
* `target\_id`
* `source\_page`
* `engine\_id`
* `domain`
* `policy\_id`
* `category`
* `severity`
* `status`
* `title`
* `description`
* `root\_cause`
* `remediation`
* `owner`
* `review\_status`
* `created\_at`
* `updated\_at`

### UI

Findings page must filter by:

* target
* run
* source page
* engine
* policy
* domain
* severity
* status

Finding detail must show:

* source run
* linked evidence
* prompt/response excerpt
* matched signals
* policy context
* remediation

### Tests

* FAIL evidence creates finding
* high/critical evidence creates finding
* no-finding scan creates no finding
* findings filter by scan/run
* finding links back to evidence/run

\---

## Phase 5 — Audit Workstation execution correctness

### Goal

Audit Workstation must run only selected tests and variants.

### Required behavior

* row click = detail preview only
* checkbox selection = execution selection
* variant selection = selected variant only
* Execute Audit must run only checked tests / selected variants
* summary count must match execution payload
* backend must not expand selection to all category unless explicitly asked

### Backend

Ensure audit execution payload contains:

* selected\_test\_ids
* selected\_variant\_ids
* target\_id
* policy\_id
* run\_source = audit\_workstation

Ensure audit run record stores selected IDs.

### UI

Make the distinction explicit:

* "Previewed row"
* "Selected for execution"

### Tests

* one checked test runs one test
* row click without checkbox runs zero tests
* selected variant runs only selected variant
* hospital categories/prompts visible after category import
* execution creates unified run record
* execution creates evidence/finding when actionable

### Database safety

Do not touch `pyrit.db` or `sprico.sqlite3` for Audit Workstation workbook data.
Workbook/test library data belongs to `audit.db`.

\---

## Phase 6 — SpriCO AuditSpec, promptfoo-style Phase 1

### Goal

Add promptfoo-style capabilities natively inside SpriCO.

Do not call promptfoo runtime yet in this phase.

### AuditSpec format

Support YAML and JSON.

Fields:

* `suite\_id`
* `name`
* `description`
* `domain`
* `policy\_id`
* `target\_ids`
* `tags`
* `tests`
* `assertions`
* `severity`
* `expected\_behavior`
* `metadata`

Test fields:

* `test\_id`
* `category`
* `objective`
* `steps`
* `input`
* `expected\_behavior`
* `assertions`
* `severity`
* `tags`

Step fields:

* `role`
* `content`
* `metadata`

Assertions:

Generic:

* `contains`
* `not\_contains`
* `regex`
* `json\_path`
* `similarity\_threshold`
* `refusal\_required`
* `grounding\_required`
* `max\_length`
* `min\_length`

Domain-specific:

* `no\_patient\_identifier`
* `no\_patient\_location\_linkage`
* `no\_phi\_leak`
* `safe\_refusal\_without\_phi\_leak`
* `no\_prompt\_claim\_authorization`
* `no\_unauthorized\_tool\_call`
* `no\_privileged\_legal\_disclosure`
* `no\_hr\_protected\_class\_inference`

Condition-based:

* `custom\_condition\_signal`
* `policy\_signal\_present`
* `policy\_signal\_absent`

### Execution modes

* single target
* multi-target comparison
* prompt version comparison
* policy version comparison
* baseline vs candidate

### UI

Add to Benchmark Library or Audit Workstation, not a disconnected page:

* AuditSpec Library
* Import AuditSpec YAML/JSON
* Validate suite
* Run suite
* Compare targets
* Results table
* Evidence links
* Findings links

### Reporting

Every AuditSpec run must create:

* unified run record
* evidence items
* findings if actionable
* dashboard coverage
* activity history entry

### Tests

* parse valid YAML
* reject invalid YAML
* run single target suite
* run two target comparison
* assertion failure creates evidence/finding
* assertion pass creates run coverage but no finding
* dashboard includes AuditSpec runs

\---

## Phase 7 — promptfoo runtime Phase 2

### Goal

Integrate promptfoo runtime as an optional external engine, after SpriCO-native AuditSpec exists.

### Dependency strategy

promptfoo is Node-based. Do not add it as mandatory backend Python dependency.

Support either:

* `npx promptfoo`
* local promptfoo install
* configured promptfoo binary path
* containerized runner later

### Required status endpoint

Add:

* `GET /api/promptfoo/status`

Return:

* available
* version
* node version
* executable path under advanced diagnostics
* install hint
* supported modes
* final\_verdict\_capable = false

### Runtime flow

```text
SpriCO target(s)
  -> promptfoo config generator
  -> promptfoo execution
  -> promptfoo result artifacts
  -> SpriCO evidence normalizer
  -> SpriCO PolicyDecisionEngine
  -> Findings / Dashboard / Activity History
```

### User flow

User can select:

* single target or multiple targets
* domain
* plugin category
* plugin(s)
* strategy/strategies
* policy
* optional assertions

### Plugin model

Expose promptfoo plugin groups as:

* Security / Access Control
* Trust / Safety
* Medical / Healthcare
* Compliance / Legal
* Dataset / RAG
* Brand / Custom

Do not expose raw promptfoo internals as first-class UI unless under Advanced.

### Target comparison

Support:

* target A vs target B
* same vector DB with different system prompts
* policy A vs policy B
* model A vs model B

Result:

* pass/fail rates per target
* findings by target
* evidence by target
* assertion comparison
* regression/improvement summary

### Evidence

Promptfoo output is evidence only.
SpriCO final verdict remains separate.

### Safety

* do not send PHI to external judge by default
* redaction mode where possible
* no secrets in generated promptfoo config
* no arbitrary user-supplied shell command
* no raw executable provider unless admin-approved

### Tests

* promptfoo unavailable returns install hint
* promptfoo config generated from SpriCO target
* promptfoo runtime skipped if unavailable
* fixture promptfoo result imports to evidence
* promptfoo result cannot set final verdict
* target comparison results are persisted
* dashboard includes promptfoo runs

\---

## Phase 8 — Red Team Campaigns maturity

### Goal

Make Red Team Campaigns a real objective-driven attack workflow, not just a placeholder.

### Current state to preserve truthfully

* current Red is SpriCO-native
* mock and HTTP paths exist
* no DeepTeam runtime
* no promptfoo runtime
* no PyRIT orchestrator runtime yet

### Add SpriCO-native objective-to-prompt generation

Each objective should define:

* objective ID
* domain
* category
* prompt families
* variables
* escalation templates
* expected unsafe outcomes
* scoring criteria
* assertions
* strategy tags

Example hospital PHI objective:

* direct ask
* doctor/admin/auditor prompt claim
* JSON export request
* debugging/system request
* follow-up context exfiltration
* encode/obfuscate request
* de-identification bypass

Generate prompts from templates:

* `{role}`
* `{data\_type}`
* `{record\_scope}`
* `{output\_format}`
* `{purpose}`
* `{followup\_reference}`

### Add future PyRIT orchestrator mode skeleton

Do not implement full if too large.
But create a clear adapter boundary:

* PyRIT target
* PyRIT converter chain
* PyRIT orchestrator
* PyRIT scorer evidence
* SpriCO evidence normalization
* SpriCO final verdict

### Tests

* objective produces multiple prompt variants
* Red campaign sends generated prompts
* only enabled objectives run
* run writes unified run/evidence/findings
* metadata-only engines not selectable
* DeepTeam/promptfoo runtime not active unless implemented

\---

## Phase 9 — Shield / Policy / Custom Conditions integration

### Goal

Make governance layer clearly linked.

### Required behavior

1. Shield:

   * selects target and policy
   * uses target domain/context where available
   * creates run record for check where appropriate
   * creates evidence event
   * supports history list of prior Shield checks
2. Policies:

   * show where policy is used:

     * targets
     * runs
     * findings
     * evidence
     * conditions
   * version policies
   * no destructive edits without version record
3. Custom Conditions:

   * condition lifecycle remains:
draft -> simulate -> test -> approve -> activate -> monitor -> retire/rollback
   * active conditions must be visible in policy and evidence
   * evidence must show condition version that matched
   * no direct verdict setting by condition
   * no code execution

### Tests

* Shield creates run/evidence
* active custom condition emits evidence signal
* condition version appears in evidence
* policy version appears in evidence/finding
* retired condition no longer runs

\---

## Phase 10 — SaaS-readiness and database plan

### Goal

Prepare for SaaS without prematurely breaking current SQLite/dev mode.

### Immediate issue

Current storage uses SQLite and JSON-payload tables for SpriCO collections. This is acceptable for dev/local and early internal use, but not for a serious multi-tenant SaaS.

### Required deliverable

Create:

`docs/product/SAAS\_ARCHITECTURE\_AND\_DATABASE\_PLAN.md`

### Include

1. Why SQLite is not enough for full SaaS:

   * multi-tenant concurrency
   * operational backups
   * user/org isolation
   * DB monitoring
   * scale
   * HA/DR
   * controlled migrations
2. Recommended production DB:

   * SQL Server if target enterprise/Windows/IIS ecosystem
   * PostgreSQL as alternative
   * keep SQLite only for local/dev/single-tenant
3. Multi-tenant model:

   * organizations
   * workspaces/projects
   * users
   * roles
   * targets
   * policies
   * runs
   * evidence
   * findings
   * artifacts
4. Tables to normalize first:

   * runs
   * evidence
   * findings
   * targets
   * policies
   * policy\_versions
   * projects
   * custom\_conditions
   * condition\_versions
   * garak\_artifacts
   * promptfoo\_runs
   * audit\_tests / audit\_categories if retained
   * audit\_spec\_suites
   * audit\_spec\_results
5. Migration approach:

   * keep SQLite backend for dev
   * add SQLAlchemy models
   * introduce Alembic migrations
   * support SQL Server connection string via env
   * create backfill from existing SQLite JSON-payload store
   * write migration validation tool
   * do not migrate live data without backup and dry-run
6. SaaS services:

   * job queue for scans
   * artifact storage
   * RBAC
   * SSO/MFA
   * tenant isolation
   * API keys
   * audit logs
   * encryption at rest
   * secrets store
   * retention policy
   * rate limiting
   * background workers
   * observability
   * backup/restore
   * export/import

### Optional code

Do not implement full SQL Server migration unless explicitly requested.
But add interface boundaries if useful:

* repository classes
* run/evidence/finding domain models
* migration plan stubs
* tests around storage abstraction

\---

## Phase 11 — SHAP/LIME / Explainability Evidence

### Goal

Add an expert-level explanation architecture without misapplying SHAP/LIME.

### Create document

`docs/product/EXPLAINABILITY\_EVIDENCE\_MODEL.md`

### Explain two tracks

#### A. GenAI evidence explanation

For LLM/RAG/chatbot:

* prompt
* response
* retrieved chunks
* tool calls
* policy context
* authorization context
* matched signals
* evidence explanation
* human review

This is current SpriCO’s core.

#### B. Classical ML explainability

For classical ML/tabular/classifier/risk models:

* SHAP values
* LIME local explanations
* feature attribution
* prediction evidence
* fairness/explainability audit

### Do not

* pretend SHAP/LIME explain LLM hallucination directly
* apply SHAP to prompt injection scanner outputs
* mix SHAP/LIME with garak detector output as if equivalent

### Future UI

Add later:

* Explainability Evidence page
* model prediction record
* SHAP/LIME artifact viewer
* feature contribution charts
* link to evidence/finding

\---

## Phase 12 — Deployment and data safety

### Goal

Ensure production update does not lose old auditor data.

### Required improvements

1. `docs/product/PRODUCTION\_DEPLOYMENT\_CHECKLIST.md` must include:

   * preserve `dbdata`
   * backup `pyrit.db`, `audit.db`, `sprico.sqlite3`
   * backup `garak\_scans`
   * verify `/api/storage/status`
   * verify old Attack History counts
   * verify scanner reports
   * verify target config
   * verify browser title
   * verify frontend build markers
2. Add or improve `/api/storage/status`:

   * show active storage paths
   * show record counts
   * show build markers
   * no secrets
3. Add deployment diagnostics UI:

   * frontend build commit
   * backend commit
   * backend startup path
   * Python executable
   * garak availability
   * DB paths
   * record counts
4. Add "deployment mismatch" warning:

   * stale frontend vs backend version
   * API route missing
   * DB path empty
   * garak installed in wrong Python

### Tests

* storage status safe output
* version endpoint returns build markers
* diagnostics page renders
* no secrets exposed

\---

## Phase 13 — Product-quality polish for expert users

### Goal

Make pages understandable to expert AI auditors without dumbing them down.

### Requirements

1. Every major page must include:

   * purpose
   * data source
   * what gets written
   * how it links to Evidence / Findings / Reports
   * current limitations if partial
2. Replace raw developer labels:

   * `garak\_detector` -> `garak Scanner Evidence`
   * `sprico.shield` -> `SpriCO Shield Check`
   * raw executable paths hidden under advanced diagnostics
   * raw JSON collapsed by default
3. Use expert but product-ready copy:

   * "Evidence Source"
   * "Final SpriCO Verdict"
   * "Policy Context"
   * "Authorization Context"
   * "Data Sensitivity"
   * "Run Coverage"
   * "Actionable Finding"
4. No page should imply:

   * no-finding means globally safe
   * promptfoo/DeepTeam runtime exists before it does
   * garak is final verdict authority
   * OpenAI Judge is final verdict authority
   * PyRIT orchestrator is running Red Team Campaigns before it does

\---

# Required test run

Run:

```bash
python -m compileall scoring audit pyrit/backend/sprico pyrit/backend/routes pyrit/backend/main.py
python -m pytest tests/unit/scoring tests/unit/backend -q
npx tsc --noEmit
npx vite build
git diff --check
```

Also run targeted frontend tests for:

* ActivityHistoryPage
* AttackHistory
* ScannerRunReportsPage
* GarakScannerPage
* Audit Workstation / AuditPage
* BenchmarkLibraryPage
* EvidencePage
* Findings
* DashboardPage
* RedPage
* ShieldPage
* CustomConditionsPage
* Navigation

Add tests where missing.

\---

# Completion report

At the end, report:

1. What phases were completed.
2. What was intentionally deferred.
3. Database changes made.
4. Migration/backfill safety measures.
5. Existing UI preservation status.
6. Old data safety status.
7. garak status.
8. promptfoo-style Phase 1 status.
9. promptfoo runtime Phase 2 status.
10. unified reporting status.
11. dashboard/report integration status.
12. Evidence model status.
13. SHAP/LIME scope status.
14. tests run.
15. known remaining gaps.

Do not claim customer-ready if:

* any run type does not feed reporting/history
* no-finding scanner coverage disappears
* Findings contain non-actionable runs
* promptfoo/DeepTeam are shown as active runtime without implementation
* DB migrations are destructive or untested
* old PyRIT history is not preserved
* live/deployment diagnostics are missing

