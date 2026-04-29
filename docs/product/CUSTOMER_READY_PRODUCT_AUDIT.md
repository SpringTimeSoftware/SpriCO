# Customer-Ready Product Audit

This document is a factual audit of the current SpriCO AI Audit Platform repository before and during the customer-ready stabilization work. It reflects the current `currentView` frontend, the FastAPI backend in `pyrit/backend/main.py`, and the current storage split across PyRIT memory, `audit.db`, `sprico.sqlite3`, and scanner artifacts.

## 1. Page Inventory

| Page | Purpose | Actual implementation | Data read | Data written | Status | Issues | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Home / Landing | Entry point and workflow launcher | `frontend/src/components/Landing/LandingPage.tsx` under `currentView === 'landing'` | Version/default labels and navigation-only metadata | None | Active | Landing copy must stay truthful about partial surfaces | Keep links accurate and scoped |
| Interactive Audit | Live PyRIT-backed audit/chat workflow | `ChatWindow` under `currentView === 'chat'`; PyRIT targets and memory; interactive scoring overlays | PyRIT conversations, target registry, saved interactive audit records, evidence IDs when available | PyRIT attack sessions/messages; saved interactive audit replay into `audit.db`; normalized turn evidence in `sprico.sqlite3` | Active | Historically not part of a unified reporting model | Keep PyRIT flow intact, attach normalized run/evidence/finding links additively |
| PyRIT Attack History | PyRIT memory view only | `AttackHistory.tsx` under `currentView === 'history'` | PyRIT `CentralMemory`; saved interactive audit list from `audit.db` | None | Active | Could be confused with universal history if copy drifts | Keep PyRIT-only label and cross-link to Activity / Evidence / Findings |
| Activity History | Cross-workflow ledger | `ActivityHistoryPage.tsx` and `/api/activity/history` | Unified run registry, evidence items, findings, PyRIT attacks | None | Active | Previously assembled from separate stores rather than a canonical run model | Back with unified run registry |
| Audit Workstation / Structured Audit | Workbook-backed structured execution | `AuditPage.tsx`; `audit/database.py`; `audit/executor.py`; `/api/audit/*` | `audit.db` test library, run results, stability/heatmap dashboards | `audit.db` run rows/results/stability data; now normalized evidence/findings/runs additively | Active | Findings view was audit-only and audit evidence was not normalized | Preserve run logic; add run/evidence/finding sync after execution |
| Benchmark Library | Public benchmark source catalog and replay launcher | `BenchmarkLibraryPage.tsx`; `/api/benchmarks/*` backed by `audit.db` | Benchmark source/scenario/media tables | Benchmark source imports; benchmark replay runs into `audit.db` | Active | Replay results were not part of a unified run registry | Map benchmark replays to unified runs |
| LLM Vulnerability Scanner | garak-based scanner workflow | `GarakScannerPage.tsx`; `/api/scans/garak*`; garak runner under `pyrit/backend/sprico/integrations/garak/` | garak status/plugins/profiles, targets, policies, historical scan records | garak runs/artifacts/evidence/findings in `sprico.sqlite3` and `dbdata/garak_scans/` | Active | Must stay explicit that garak is evidence only and PASS is scope-limited | Keep truthful copy and attach unified run records |
| Scanner Run Reports | Specialized scanner reporting ledger | `ScannerRunReportsPage.tsx`; `/api/scans/garak/reports*` | garak run records plus derived summary | None | Active | Specialized ledger previously separate from canonical runs | Keep specialized UI, link back to unified run model |
| Evidence Center | Proof storage and review | `EvidencePage.tsx`; `/api/evidence` | `sprico.sqlite3` `evidence_items` | None directly; other workflows write evidence | Active | Needed explicit run/source linkage and links back to findings/runs | Harden evidence model and filters |
| Findings | Actionable triage surface | Now `FindingsPage.tsx`; historically `AuditPage forcedWorkspaceView="findings"` | `sprico.sqlite3` `findings`; unified run-aware filters | None directly; workflows write findings | Active | Previously audit-only, not platform-wide | Replace with platform findings while preserving `currentView` |
| Red Team Campaigns | SpriCO-native objective-driven campaigns | `RedPage.tsx`; `/api/red/*`; `pyrit/backend/sprico/red.py` | Objectives, policies, targets, historical red scans | `red_scans`, `scans`, `scan_results`, evidence, findings | Partial but active | Could imply runtimes that do not exist if copy drifts | Keep explicit that current engine is SpriCO-native and other runtimes are not implemented |
| Shield | Runtime screening / guardrail check | `ShieldPage.tsx`; `/api/shield/check`; `pyrit/backend/sprico/shield.py` | Policies, custom conditions, request messages | Shield evidence and shield event records; now actionable findings and unified runs | Active | Previously stored evidence but not run/finding normalization | Keep policy authority intact; add run/finding linkage |
| Policies / Projects | Policy and project administration | `PolicyPage.tsx`; `/api/policies`; `/api/projects` | `sprico.sqlite3` policy/project records | Policy/project updates | Active | Needs to remain the authority context, not verdict engine replacement | Preserve as configuration context for runs/evidence |
| Custom Conditions | Safe declarative signal management | `CustomConditionsPage.tsx`; `/api/conditions*`; `pyrit/backend/sprico/conditions.py` | Condition lifecycle/version/test/simulation data | Condition lifecycle tables; now simulation run records and matched-signal evidence | Active | Needs explicit “no code execution” and “no direct verdict” truthfulness | Preserve declarative-only model and emit signals only |
| Dashboards | Structured analytics plus scanner coverage | `DashboardPage.tsx`, `HeatmapDashboardPage.tsx`, `StabilityDashboardPage.tsx`; `/api/dashboard/*` | `audit.db` analytics plus scanner summary; now unified run summary | None | Active | Dashboard previously mixed structured analytics with a separate scanner summary and no canonical run totals | Add unified run coverage section without removing existing dashboards |
| Diagnostics / Storage Diagnostics | Operator diagnostics | `DiagnosticsPage.tsx`; `/api/storage/status`; `/api/version`; `/api/judge/status`; garak status | Storage paths/counts, version, judge status, external engine metadata | None | Diagnostic | Counts previously lacked unified run registry | Add unified run counts additively |
| Open Source Components | OSS attribution / provenance | `OpenSourceComponentsPage.tsx`; `/api/legal/open-source-components*` | OSS metadata files | None | Active | None material to runtime model | Keep factual provenance data |

## 2. Current Databases and Stores

| Store | Purpose | Current usage |
| --- | --- | --- |
| `pyrit.db` | PyRIT `CentralMemory` | Interactive attack sessions and PyRIT Attack History |
| `audit.db` | Workbook-faithful audit database | Structured audit runs/results, saved interactive audit replays, benchmark sources/scenarios/media, dashboards, stability |
| `sprico.sqlite3` | Generic JSON-payload operational store | Policies, projects, custom conditions, scanner runs, red scans, shield events, evidence items, findings, unified runs |
| `sprico_storage.json` | JSON fallback backend | Local/dev fallback when `SPRICO_STORAGE_BACKEND=json` |
| `dbdata/garak_scans/` | Scanner artifact root | garak config, stdout/stderr, reports, parsed artifacts |
| `dbdata/` uploaded media/artifacts | Shared local artifact root | Media files and serialized prompt artifacts used by PyRIT flows |
| `target_secrets.key` and target config store | Target credential/config persistence | Encrypted target secrets and persistent target registry |

## 3. Current API Surface

| API area | Current routes / notes |
| --- | --- |
| Attacks | `/api/attacks*` |
| Activity | `/api/activity/history` |
| Audit | `/api/audit/*`, `/api/dashboard/*`, `/api/benchmarks/*`, `/api/target-capabilities` |
| Scanner | `/api/scans/garak*`, `/api/integrations/garak/*`, `/api/garak/status` |
| Evidence | `/api/evidence` |
| Findings | `/api/findings*` |
| Unified runs | `/api/runs*` |
| Red | `/api/red/*` |
| Shield | `/api/shield/check` |
| Policies | `/api/policies*` |
| Projects | `/api/projects*` |
| Conditions | `/api/conditions*` |
| Storage diagnostics | `/api/storage/status` |
| Version | `/api/version` |
| Judge status | `/api/judge/status` |
| Targets | `/api/targets*` |

## 4. Current Engine Reality

| Engine / capability | Reality |
| --- | --- |
| PyRIT | Active for Interactive Audit, PyRIT Attack History, target registry integration, and structured audit execution paths |
| garak | Active optional scanner evidence engine; not final verdict authority |
| promptfoo runtime | Optional Benchmark Library runtime adapter; evidence-only and never the final verdict authority |
| DeepTeam runtime | Not integrated in this phase |
| OpenAI Judge | Optional evidence-only mode when configured; not final verdict authority |
| SHAP / LIME | Not implemented here; any future work must be scoped to classical ML explainability only |
| SpriCO PolicyDecisionEngine | Final verdict authority; must remain authoritative over external evidence engines |

## 5. Key Product Gaps Before Stabilization

1. Reporting/history previously aggregated separate stores instead of a canonical run registry.
2. Evidence records lacked consistent run/source linkage and link-back to findings.
3. Findings were not platform-wide and were inconsistent across workflow sources.
4. Structured audit evidence/finding normalization was missing.
5. Shield and condition simulation records were not represented as canonical runs.
6. UI truthfulness depended on copy staying explicit about what is implemented versus metadata-only or not implemented.

## 6. Stabilization Direction Implemented In This Run

1. Additive unified run registry in `sprico.sqlite3` `runs`.
2. Additive `/api/runs*` and `/api/findings*` APIs without removing existing routes.
3. Hardened evidence records with run/source/policy/authorization/linkage fields.
4. Actionable-only finding creation rules applied consistently across scanner, red, shield, interactive audit, and structured audit evidence sync.
5. Platform Findings page replaces the audit-only findings surface while preserving `currentView`.
6. Activity History and dashboard coverage now have a canonical run model available.
