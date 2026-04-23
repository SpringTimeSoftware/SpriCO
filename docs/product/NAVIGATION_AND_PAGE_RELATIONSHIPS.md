# Navigation And Page Relationships

This document describes the Phase A grouped navigation result. SpriCO still uses `currentView` state; React Router is not introduced.

## Grouped Navigation Map

| Group | User-facing label | `currentView` | Component file | Main APIs | Status |
| --- | --- | --- | --- | --- | --- |
| Home | Home | `landing` | `frontend/src/components/Landing/LandingPage.tsx` | none | full static product entry page |
| Audit Workbench | Interactive Audit | `chat` | `frontend/src/components/Chat/ChatWindow.tsx` | `/api/attacks`, `/api/audit/interactive/...`, `/api/targets/active` | full existing workflow |
| Audit Workbench | Activity History | `activity-history` | `frontend/src/components/History/ActivityHistoryPage.tsx` | `/api/activity/history` | cross-workflow activity index |
| Audit Workbench | Attack History | `history` | `frontend/src/components/History/AttackHistory.tsx` | `/api/attacks`, `/api/labels` | full existing workflow |
| Audit Workbench | Audit Runs | `audit` | `frontend/src/components/Audit/AuditPage.tsx` | `/api/audit/run`, `/api/audit/runs`, `/api/audit/results/...` | full existing workflow |
| Audit Workbench | Findings | `findings` | `frontend/src/components/Audit/AuditPage.tsx` | `/api/audit/findings/...` | full existing workflow |
| Audit Workbench | Evidence Center | `evidence` | `frontend/src/components/SpriCO/EvidencePage.tsx` | `/api/evidence` | functional read-only evidence view |
| Scanners | LLM Vulnerability Scanner | `garak-scanner` | `frontend/src/components/SpriCO/GarakScannerPage.tsx` | `/api/garak/status`, `/api/integrations/garak/plugins`, `/api/scans/garak`, `/api/targets`, `/api/policies` | optional garak runtime scanner workflow with SpriCO final verdict separation |
| Scanners | Scanner Run Reports | `scanner-reports` | `frontend/src/components/SpriCO/ScannerRunReportsPage.tsx` | `/api/scans/garak/reports` | scanner job report ledger; includes no-finding, failed, timeout, and not-evaluated runs |
| Scanners | Red Team Campaigns | `red` | `frontend/src/components/SpriCO/RedPage.tsx` | `/api/red/objectives`, `/api/red/scans`, `/api/policies` | partial; deterministic mock hospital campaign works; configured HTTP target path is permission-gated |
| Scanners | garak Engine Diagnostics | `garak-scanner` | `frontend/src/components/SpriCO/GarakScannerPage.tsx` | `/api/garak/status`, `/api/integrations/garak/plugins` | diagnostic section inside scanner page |
| Policies | Shield Check | `shield` | `frontend/src/components/SpriCO/ShieldPage.tsx` | `/api/shield/check`, `/api/policies` | functional native SpriCO check |
| Policies | Policies | `policy` | `frontend/src/components/SpriCO/PolicyPage.tsx` | `/api/projects`, `/api/policies`, policy simulation/history APIs | functional policy/project management |
| Policies | Custom Conditions | `conditions` | `frontend/src/components/SpriCO/CustomConditionsPage.tsx` | `/api/conditions`, condition lifecycle APIs | functional backend lifecycle; UI exposes retire/rollback/history |
| Policies | Authorization Context | disabled | not implemented | not implemented | coming soon |
| Dashboards | Structured Dashboard | `dashboard` | `frontend/src/components/Audit/DashboardPage.tsx` | `/api/audit/dashboard` | full existing workflow |
| Dashboards | Heatmap Dashboard | `heatmap-dashboard` | `frontend/src/components/Audit/HeatmapDashboardPage.tsx` | `/api/dashboard/heatmap-dashboard` | full existing workflow |
| Dashboards | Stability Dashboard | `stability-dashboard` | `frontend/src/components/Audit/StabilityDashboardPage.tsx` | `/api/dashboard/stability`, stability detail APIs | full existing workflow |
| Library | Benchmark Library | `benchmark-library` | `frontend/src/components/Audit/BenchmarkLibraryPage.tsx` | `/api/benchmarks/...` | full existing workflow |
| Library | Prompt Variants | `prompt-variants` | `frontend/src/components/Audit/PromptVariantsPage.tsx` | audit variant APIs | full existing workflow |
| Library | Attack Templates | disabled | not implemented | not implemented | coming soon |
| Settings | Configuration | `config` | `frontend/src/components/Config/TargetConfig.tsx` | `/api/targets`, target config APIs | full existing workflow |
| Settings | Target Help | `target-help` | `frontend/src/components/Audit/TargetHelpPage.tsx` | none | full static help page |
| Settings / Legal | Open Source Components | `open-source-components` | `frontend/src/components/SpriCO/OpenSourceComponentsPage.tsx` | `/api/legal/open-source-components` | functional legal registry page |
| Settings | External Engine Metadata | `external-engines` | `frontend/src/components/SpriCO/ExternalEngineMetadataPage.tsx` | `/api/external-engines` | functional metadata UI |
| Settings | Judge Models | `judge-models` | `frontend/src/components/SpriCO/JudgeModelsPage.tsx` | `/api/judge/status` | optional evidence-model configuration status |
| Settings | About / Diagnostics | `diagnostics` | `frontend/src/components/SpriCO/DiagnosticsPage.tsx` | `/api/version`, `/api/storage/status`, `/api/garak/status` | build, backend, scanner, and storage verification |

## Shell Behavior

- `frontend/src/components/Sidebar/Navigation.tsx` exports `NAVIGATION_GROUPS`, the grouped top navigation, and the compact quick-access rail.
- `frontend/src/components/Layout/MainLayout.tsx` renders the grouped navigation in the top bar.
- `currentView` now starts at `landing`; every existing workflow remains reachable through grouped navigation or landing-page CTAs.
- The Home top navigation item directly opens `currentView` `landing`. It does not open a submenu and does not show a nested SpriCO Overview item.
- Clicking the SpriCO title in the top bar navigates to `currentView` `landing`.
- On `currentView` `landing`, the compact left rail is hidden entirely; the landing page uses top navigation only.
- On workspace views, the compact left rail remains for quick access only. It no longer lists every page with abbreviations such as `Gk`, `Rd`, `Ev`, `Cd`, `Li`, `Hx`, `St`, `Bm`, `Fi`, or `Pv`.
- Every existing `currentView` value is preserved.
- In Vite dev mode, the SpriCO title tooltip includes the frontend load timestamp so stale localhost sessions can be identified without adding production UI noise.

## Landing Page

The SpriCO landing page is implemented at `frontend/src/components/Landing/LandingPage.tsx` with original CSS and inline SVG visuals in `LandingPage.css`. It uses only local React code, existing Fluent UI components/icons, and original CSS/SVG geometry. No external images, vendor screenshots, or third-party vendor assets are copied.

Landing shell behavior:

- grouped top navigation remains visible
- compact left rail is not rendered
- the hero uses a broad `min(1440px, calc(100vw - 64px))` container
- supporting cards use broad containers and full-width bands to avoid unused blank canvas

CTA mappings:

- `Start Interactive Audit` -> `chat`
- `Run LLM Vulnerability Scanner` -> `garak-scanner`
- `Launch Red Team Campaign` -> `red`
- `Review Evidence Center` -> `evidence`
- `Open Audit Workbench` -> `chat`
- `Configure Policies` -> `policy`
- `View Evidence Center` -> `evidence`

Landing-page workflow relationships:

- Hero animation maps input streams through Evidence Layer, Domain Signals, `PolicyDecisionEngine`, and PASS/WARN/FAIL verdict outputs.
- Trust strip frames SpriCO as evidence-first, policy-aware, evidence-only for external engines, and domain-pack driven.
- How SpriCO works maps target selection, scanner workflows, evidence normalization, domain policy, and findings/dashboard review to existing views.
- Threat category cards map privacy leakage, prompt injection, RAG poisoning, tool misuse, hallucination, and authorization boundary failures to evidence collection.
- Domain-aware scoring shows healthcare, legal, HR, financial, enterprise, and general AI safety domains. These domain cards connect to policy packs and Custom Conditions by describing the signal categories and policy context each pack can evaluate.
- Healthcare examples are retained as one domain-specific example, not the overall product focus.
- Interactive Audit remains the manual audit workbench for turn-by-turn scoring.
- LLM Vulnerability Scanner uses available scanner engines as evidence sources behind the `garak-scanner` view.
- Red Team Campaigns runs repeatable adversarial campaigns and stores evidence/findings.
- Policies, Shield, and Custom Conditions define native SpriCO controls and policy context.
- Evidence Center is the review surface for normalized scanner/evidence metadata and SpriCO final verdicts.
- Dashboards and Findings remain the review surfaces for audit posture and triage.

## Standard Dev Port Verification

Expected local frontend command:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 3000 --strictPort
```

Open `http://127.0.0.1:3000`. The current frontend build should show the SpriCO landing headline and top navigation groups: `Home`, `Audit Workbench`, `Scanners`, `Policies`, `Dashboards`, `Library`, and `Settings`.

If `localhost:3000` still shows the old flat rail, the browser or dev server is stale. Stop the old Vite/scheduled frontend process, restart the command above, hard refresh the page, and confirm the SpriCO title tooltip shows a fresh dev load timestamp.

## Scanner Model

The primary scanner experience is now labeled `LLM Vulnerability Scanner`. The underlying `currentView` remains `garak-scanner` for backward compatibility.

garak fits behind this page as an optional attack/scanner evidence engine:

- garak can provide scanner evidence when installed and configured.
- garak is not the product's final scoring authority.
- SpriCO native policy checks remain available when garak is not installed.
- The page displays `Final Verdict Authority: SpriCO PolicyDecisionEngine`.
- The page uses the same configured target registry as Interactive Audit and Target Configuration via `/api/targets`.
- Users must select a configured target and confirm permission attestation before scanner execution.
- Scanner setup is grouped into Target & Permission, Domain Policy, Scanner Setup, Evidence Engines, and Advanced Diagnostics.
- Scanner setup uses allowlisted scan profiles and vulnerability categories; raw CLI arguments are not accepted.
- garak artifacts are stored under `dbdata/garak_scans/{scan_id}` and linked to evidence/finding records by scan and artifact metadata.
- Scanner History records scanner jobs. Evidence Center stores normalized proof from completed scanner runs, Shield checks, Red campaigns, and interactive audit evidence. Findings stores actionable SpriCO outcomes.
- Validation failures in the scanner form return structured field-level errors and do not create Evidence Center or Findings records.
- The LLM Vulnerability Scanner selected result is a Scan Report built from the existing garak run record. It includes Scan Summary, Scope Tested, Probe Coverage, Evidence & Findings, Artifact Summary, and collapsed Advanced Raw Evidence sections.
- Scanner Run Reports at `currentView` `scanner-reports` list every persisted scanner run, including `completed_no_findings`, `timeout`, `failed`, and other not-evaluated jobs. This makes no-finding scanner coverage visible outside the active scanner page.
- `completed_no_findings` means no actionable issue was produced for the selected scan profile and categories. It is not a global safety guarantee.
- Scanner History is a job ledger. Evidence Center is the proof ledger. Findings contains only actionable issues such as `FAIL`, `HIGH`/`CRITICAL` risk, or high-sensitivity `NEEDS_REVIEW`.

Required product copy:

`External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.`

## Target Registry Reuse

SpriCO workflows share one target registry:

- Target Configuration creates, archives, and manages configured targets through `/api/targets`.
- Interactive Audit continues to use the active/configured target flow.
- LLM Vulnerability Scanner loads configured targets from `/api/targets` through `UnifiedTargetSelector`.
- Red Team Campaigns loads configured targets from `/api/targets` for real target scans.
- Shield can continue to receive target metadata through policy/check metadata; a dedicated selector can be added later without changing target storage.

`UnifiedTargetSelector` is implemented in `frontend/src/components/SpriCO/UnifiedTargetSelector.tsx`. It displays target name, target type, derived provider, derived domain, connection/config status, compatible workflows, and policy pack hints. Provider/domain are derived from existing target registry fields and target parameters; no disconnected target store is introduced.

Workflow compatibility is intentionally conservative:

- Interactive Audit and Shield can show configured targets.
- LLM Vulnerability Scanner and Red Team Campaigns require a non-TextTarget configured with an endpoint.
- Missing endpoint targets remain visible but show a validation error before execution.

## Final Verdict Architecture

External engines are evidence sources only:

- garak detector evidence
- DeepTeam metadata/evidence, when later implemented
- promptfoo assertions, when later implemented
- PyRIT scorer evidence
- optional OpenAI judge evidence
- optional OpenAI judge evidence is configured under Settings -> Judge Models, is disabled by default, and remains evidence-only. API keys must be backend secrets.

SpriCO `PolicyDecisionEngine` remains the final verdict authority for regulated domains. Final verdict authority is displayed as locked and is not presented as a selectable scoring engine.

## Evidence Center Relationships

Evidence Center reads normalized evidence from `/api/evidence`.

Attack History is separate from Evidence Center. Attack History reads PyRIT CentralMemory attack sessions through `/api/attacks`; it does not automatically show garak scans, Shield events, Red Team Campaigns, Evidence Center records, or static exported HTML transcripts.

Current evidence producers:

- Shield Check writes runtime policy/evidence records.
- Red Team Campaigns writes demo mock and permission-gated real target campaign turns, evidence, and findings.
- garak scanner runs write scanner evidence and SpriCO final verdict metadata when scans are recorded.
- Interactive Audit writes normalized Evidence Center records for newly scored assistant turns using `interactive_audit:{conversation_id}:{turn_id}:{score_version}` as a dedupe key. Older historical transcript turns are not migrated automatically.
- If a turn does not have a normalized Evidence Center record, the UI says: `This turn is scored in the interactive audit transcript. No normalized Evidence Center record exists yet.`

The Evidence Center normalizes display and filtering across:

- engine
- engine type
- scan ID
- policy ID
- risk
- final verdict

## External Engine Metadata

The Settings group includes `External Engine Metadata` at `currentView` `external-engines`.

The page displays:

- attack engines and evidence engines from `/api/external-engines`
- availability, installed version, license, source, and install hints
- whether an engine can generate attacks, evidence, or final verdicts
- `SpriCO PolicyDecisionEngine` as the locked final verdict authority for regulated-domain audits

External engines show final verdict capability as `No`. The page includes the required product copy: `External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.`

## Red Mock And Real Target Modes

Red Team Campaigns now shows two execution modes:

- `Demo mock scan` uses `mock_hospital_target` and remains available without external configuration.
- `Real target scan` requires a configured SpriCO target endpoint and explicit permission attestation.

The real target path does not silently fall back to the mock target. If no endpoint exists, the API returns: `Selected target is missing an endpoint and cannot be used for real campaign execution.`

DeepTeam and promptfoo are not executable Red runtimes in this phase. garak is treated as scanner evidence and is not exposed as a Red final verdict engine.

The current UI labels the difference explicitly:

- Demo mock scan: deterministic demo-only hospital target used for product demos and regression checks.
- Real target scan: configured target selected from `/api/targets`, permission attestation required, endpoint required.
- Unsupported metadata-only engines return a clear validation error and cannot execute campaigns.

Scanner versus campaign:

- LLM Vulnerability Scanner runs broad scanner-style checks and records scanner evidence plus SpriCO final verdict metadata.
- Red Team Campaigns runs objective-driven attack prompts over turns, scores responses with SpriCO domain policy, and stores campaign evidence/findings.

## garak Scanner Evidence Flow

The LLM Vulnerability Scanner keeps garak optional. When garak is unavailable, SpriCO native checks remain usable. When garak is installed/configured and a scan is run, garak output is persisted as scanner evidence, normalized into SpriCO signals, and passed through `PolicyDecisionEngine` for the final verdict.

The UI must continue to show scanner evidence and SpriCO final verdict separately.

Scanner evidence is visible through:

- LLM Vulnerability Scanner run history/results
- Scanner Run Reports, including no-finding and not-evaluated runs
- Evidence Center records with `engine_id=garak`, `source_type=external_scanner`, and `evidence_type=scanner_evidence`
- Findings when the final SpriCO verdict is `FAIL`, the risk is `HIGH`/`CRITICAL`, or high-sensitivity `NEEDS_REVIEW` evidence requires triage. `completed_no_findings` scans do not create Findings.
- Structured Dashboard scanner coverage metrics from `/api/scans/garak/reports/summary`
- dashboards/reports that read shared `findings`, `evidence_items`, `garak_runs`, `scans`, or `scan_results` storage

Scanner reporting relationships:

- Scanner Run Reports is the scanner job ledger and shows every scanner run.
- Evidence Center is the proof ledger and shows normalized evidence only when usable evidence was produced.
- Findings is the triage ledger and shows only actionable issues.
- Structured Dashboard counts scanner runs separately from structured audit run metrics. No-finding scans increase scanner coverage counts but do not create Findings.

## Custom Conditions Lifecycle

The Custom Conditions page shows the required lifecycle:

`draft -> simulate -> test -> approve -> activate -> monitor -> retire/rollback`

Activation requirements shown in the UI:

- positive test
- negative test
- simulation
- approval
- frozen version
- audit history

Custom conditions remain declarative only. There is no Python, JavaScript, shell, SQL, or arbitrary code execution path.
