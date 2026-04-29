# Page-By-Page Product Review

## Scope

This review describes the current product as implemented in the repository today.

It is intentionally truthful rather than aspirational:

- if a page is PyRIT-only, it is described as PyRIT-only
- if a page is garak-backed, it is described as garak-backed
- if a page is partial, it is described as partial
- if a page is metadata/diagnostic/admin heavy, it is described that way

## What Currently Makes Sense

- `Interactive Audit` is the strongest user workflow. It is genuinely PyRIT-backed and carries the most coherent audit/evidence/scoring story.
- `PyRIT Attack History` and `Activity History` now form a sensible pair: one scoped, one cross-workflow.
- `LLM Vulnerability Scanner` and `Scanner Run Reports` correctly separate scanner execution from final policy verdict authority.
- `Evidence Center` and `Findings` are separated in a defensible way: proof vs actionable outcome.
- `Structured Dashboard` now reflects scanner coverage as well as structured audit metrics.
- `About / Diagnostics` and `Storage Diagnostics` give operators a real deployment truth surface.

## What Is Misleading Right Now

- `Red Team Campaigns` still exposes future/partial engine concepts in the same workspace as executable options. The page is honest, but the product still asks the user to understand maturity levels.
- `AuditPage` combines runner and findings behaviors into one very large workspace. Powerful, but mentally dense.
- `Benchmark Library` mixes reference material, imports, and replay controls in one screen. Accurate, but heavy.
- `Scanner Run Reports` is now legible, but it is still more of a ledger than a deep investigative report explorer.
- `Custom Conditions` is strong when the backend service is available, but it still exposes a partial-service path directly in the main UI.

## What Should Change Next

- Add stronger target-level reporting views that unify latest audit run, latest scanner run, evidence count, and findings count.
- Keep reducing internal/raw labels that leak into user-facing pages.
- Simplify the `Audit Workbench` mental model by making the distinction between runner, findings, and reference assets easier to scan.
- Continue making `Red Team Campaigns` honest while narrowing the gap between visible options and executable runtime.

## Release Blockers vs Polish Issues

### Release blockers

- Live deployment drift remains a blocker if production still serves stale frontend/backend artifacts.
- A live `Activity History` `502` remains a blocker in deployment, because it breaks the cross-workflow history model even though the local code path exists.
- Any live environment that still shows old Attack History wording or stale scanner report behavior should be treated as not fully rolled forward.

### Polish issues

- Mixed maturity language on some admin/engine pages
- Very large combined workspaces (`AuditPage`, `Benchmark Library`)
- Limited target drilldown outside dashboard/report surfaces

---

## 1. Home / Landing / Overview

- User-facing purpose:
  Entry point and product overview with links into the major workflows.
- Actual current implementation:
  A landing page, not the main working surface. Uses the grouped top navigation and routes into existing `currentView` values.
- Data source(s) it reads:
  Mostly static presentation content.
- Data it writes:
  None.
- What makes sense:
  Clear brand/title, direct entry into workflows, separate from the authenticated work surfaces.
- What is missing:
  It does not carry deep live system status itself.
- What is misleading:
  Nothing major if it stays an entry page and not the core workspace.
- Recommended change:
  Keep it stable; do not overload it with operator/runtime detail.
- Status:
  `active`

## 2. Interactive Audit

- User-facing purpose:
  Manual conversation-driven auditing against a configured target.
- Actual current implementation:
  PyRIT-backed chat workflow using target registry selection, PyRIT attack/message persistence, shared evaluator badges, per-turn evidence display, and optional save-to-structured-run.
- Data source(s) it reads:
  PyRIT attack sessions/messages, target registry, saved Interactive Audit replays from `audit.db`.
- Data it writes:
  PyRIT attacks/messages; saved structured audit runs when explicitly persisted.
- What makes sense:
  This is the strongest workflow in the product. The ribbon, transcript, shared evaluator, and “Open Findings” path make sense.
- What is missing:
  It still depends on the user understanding target state and storage boundaries.
- What is misleading:
  On its own it can still be mistaken for “the whole audit system” if the user never visits Activity History or Findings.
- Recommended change:
  Keep this as the primary manual audit surface and continue tightening cross-links into findings/evidence/history.
- Status:
  `active`

## 3. PyRIT Attack History

- User-facing purpose:
  Review PyRIT-backed attack/session history.
- Actual current implementation:
  Reads PyRIT attack summaries and also surfaces saved Interactive Audit replays from `audit.db`.
- Data source(s) it reads:
  PyRIT CentralMemory; `audit.db` saved interactive runs.
- Data it writes:
  None.
- What makes sense:
  The page now explicitly says it is PyRIT-scoped and links to other history/report pages.
- What is missing:
  It is not a searchable universal activity explorer.
- What is misleading:
  Showing saved Interactive Audit replays here is useful, but it slightly blurs the boundary between pure PyRIT memory and adjacent audit storage.
- Recommended change:
  Keep the current scope wording and continue treating Activity History as the universal ledger.
- Status:
  `active`

## 4. Activity History

- User-facing purpose:
  Cross-workflow history page.
- Actual current implementation:
  Lightweight ledger that groups recent PyRIT attacks, audit runs, scanner runs, Red campaigns, Shield events, evidence, and findings.
- Data source(s) it reads:
  PyRIT CentralMemory, `audit.db`, SpriCO storage (`garak_runs`, `red_scans`, `shield_events`, `evidence_items`, `findings`).
- Data it writes:
  None.
- What makes sense:
  This is the right answer to “where does my activity live?”
- What is missing:
  Deep filtering, timeline pivoting, and row expansion.
- What is misleading:
  The word “history” may imply a detailed explorer, but the implementation is currently a summary ledger.
- Recommended change:
  Keep it as the cross-workflow index and add deeper filters later without changing the page’s core role.
- Status:
  `active`

## 5. Audit / Findings Workspace

- User-facing purpose:
  Run structured workbook audits and inspect run-scoped findings.
- Actual current implementation:
  One large workspace component that supports runner mode and findings mode, including workbook filters, execution controls, run history, prompt variants, and evidence-heavy finding detail.
- Data source(s) it reads:
  `audit.db` tests/options/runs/results, target registry, retrieval traces.
- Data it writes:
  Structured audit runs, prompt variants, imported workbooks/benchmark replays.
- What makes sense:
  It preserves a tight link between executed tests and actionable result review.
- What is missing:
  Cleaner separation between “configure/run” and “investigate findings.”
- What is misleading:
  The page can read as a general findings page even though a lot of it is still structured-audit specific.
- Recommended change:
  Keep the shared data model, but simplify the mental model over time.
- Status:
  `active`

## 6. LLM Vulnerability Scanner

- User-facing purpose:
  Run scanner-based LLM vulnerability checks against a configured target.
- Actual current implementation:
  garak-backed scanner runner with SpriCO policy context, profile/category selection, compatible-target checks, judge-as-evidence controls, and selected-run detail.
- Data source(s) it reads:
  garak status/plugins/reports, target registry, policies, judge status.
- Data it writes:
  garak scanner runs, scanner evidence, artifacts, and possibly Findings when actionable.
- What makes sense:
  It clearly says external scanners produce evidence only and SpriCO owns the final verdict.
- What is missing:
  It is not a multi-engine orchestration plane in this phase.
- What is misleading:
  The existence of diagnostics-like sections in the same page can make it feel more engine-admin heavy than strictly workflow-driven.
- Recommended change:
  Keep the core workflow and continue moving engine-detail wording behind diagnostics where possible.
- Status:
  `active`

## 7. Scanner Run Reports

- User-facing purpose:
  Show scanner job history and selected report detail.
- Actual current implementation:
  Scanner ledger over persisted garak runs with no-finding, failure, timeout, not-evaluated, and actionable cases all visible.
- Data source(s) it reads:
  Persisted `garak_runs` report projection.
- Data it writes:
  None.
- What makes sense:
  This is the correct place for scanner history, not Findings.
- What is missing:
  Deeper filter/sort controls and richer target drill-through.
- What is misleading:
  Less misleading now that raw internal status labels have been normalized for the table.
- Recommended change:
  Keep it as the scanner ledger and add richer filtering later.
- Status:
  `active`

## 8. Evidence Center

- User-facing purpose:
  Review normalized proof records across workflows.
- Actual current implementation:
  Filterable evidence list with selected-record detail, normalized summary, and optional advanced raw evidence view.
- Data source(s) it reads:
  SpriCO evidence store (`evidence_items`).
- Data it writes:
  None from this page.
- What makes sense:
  Clear distinction between proof storage and findings.
- What is missing:
  Stronger direct links back to exact source workflow screens.
- What is misleading:
  Little. The page does a reasonable job of saying verdict is separate from raw engine output.
- Recommended change:
  Add more source-aware linking and filtering over time.
- Status:
  `active`

## 9. Red Team Campaigns

- User-facing purpose:
  Run objective-driven campaign tests.
- Actual current implementation:
  SpriCO-native campaign runner with mock mode, partial real target mode, objective library, scan results, and comparison view.
- Data source(s) it reads:
  Red objectives, policies, existing red scans, target registry.
- Data it writes:
  Red scan records.
- What makes sense:
  The page explicitly states current engine reality and future roadmap limitations.
- What is missing:
  True PyRIT orchestrator runtime, DeepTeam runtime, promptfoo runtime, mature target execution breadth.
- What is misleading:
  The selectable engine list still exposes non-executable engine names in the same configuration surface.
- Recommended change:
  Keep the honesty, but keep tightening the distinction between executable and metadata-only engines.
- Status:
  `partial`

## 10. Shield

- User-facing purpose:
  Run a policy-aware allow/warn/block/escalate style check over prompts/responses/context.
- Actual current implementation:
  Native SpriCO policy check console with authorization templates, metadata editing, decision summary, and matched-signal breakdown.
- Data source(s) it reads:
  Policies.
- Data it writes:
  Shield check results / related evidence via backend execution.
- What makes sense:
  The authorization template system makes the policy model concrete.
- What is missing:
  In-page historical ledger of prior Shield events.
- What is misleading:
  Users may read it as a runtime gateway product when it is currently more of a check/evaluation workspace.
- Recommended change:
  Add event history and stronger bridge to stored Shield evidence.
- Status:
  `active`

## 11. Policies / Projects

- User-facing purpose:
  Administer policies and lightweight project grouping.
- Actual current implementation:
  Project list, policy list, policy editing, allow/deny controls, simulation, and policy audit history in one page.
- Data source(s) it reads:
  Policies, projects, policy audit history.
- Data it writes:
  Policies, projects, simulation requests.
- What makes sense:
  Policies, simulation, and audit history belong together.
- What is missing:
  Clearer separation between project admin and policy authoring.
- What is misleading:
  “Projects” currently read more like grouping metadata than true tenancy/runtime isolation.
- Recommended change:
  Keep Projects lightweight unless the backend model becomes stronger.
- Status:
  `active`

## 12. Custom Conditions

- User-facing purpose:
  Create safe declarative signal conditions with lifecycle controls.
- Actual current implementation:
  Draft/simulate/test/approve/activate/retire/rollback workflow with declarative JSON parameters and service-availability handling.
- Data source(s) it reads:
  Custom condition types, condition list, version history, audit history.
- Data it writes:
  Condition records, tests, simulation results, approvals, activation/retirement events.
- What makes sense:
  The page is explicit that conditions emit signals and do not directly own final verdicts.
- What is missing:
  Simpler authoring ergonomics and more polished service-health handling.
- What is misleading:
  If the route is unavailable, the page still exists in primary navigation despite partial backend maturity.
- Recommended change:
  Keep it, but treat it as partial until service availability is consistently reliable.
- Status:
  `partial`

## 13. Benchmark Library

- User-facing purpose:
  Manage reusable benchmark/reference scenarios and reusable AuditSpec/promptfoo test definitions before they are executed.
- Actual current implementation:
  Multi-tab library with public/internal/imported reference assets plus an AuditSpec workspace. The AuditSpec workspace supports pasted/imported SpriCO-native YAML/JSON suites, repeatable AuditSpec execution, optional promptfoo runtime launches, custom promptfoo policies/intents, and comparison-oriented reporting in one place.
- Data source(s) it reads:
  Benchmark library tables, target registry, compare/replay APIs, AuditSpec suite storage, promptfoo catalog/status, policies, unified runs.
- Data it writes:
  Imported benchmark packs, imported AuditSpec suites, replayed structured audit runs, optional promptfoo runtime launches, and linked unified run/evidence/finding records.
- What makes sense:
  It clearly distinguishes reusable definitions from evidence. AuditSpec and promptfoo stay under Benchmark Library because both feed the same unified runs, Evidence Center, Findings, dashboard coverage, and Activity History.
- What is missing:
  Deeper saved comparison reporting and richer library search/filtering for large suite catalogs.
- What is misleading:
  Nothing severe if the page keeps saying three things clearly:
  1. Benchmark Library stores reusable definitions, not proof.
  2. AuditSpec is SpriCO-native YAML/JSON and is imported by paste/validate/import on this page.
  3. promptfoo runtime is optional external evidence generation, not final verdict authority.
- Recommended change:
  Keep the reference-vs-evidence distinction, keep promptfoo inside the Benchmark/AuditSpec workspace, and continue improving section-level clarity rather than splitting the workflow into disconnected pages.
- Status:
  `active`

## 14. Structured Dashboard

- User-facing purpose:
  Show aggregated structured audit metrics and scanner coverage.
- Actual current implementation:
  Structured audit KPI dashboard plus scanner coverage cards and breakdown panels.
- Data source(s) it reads:
  Audit dashboard API and garak report summary API.
- Data it writes:
  None.
- What makes sense:
  Structured audit metrics and scanner coverage now coexist in a useful reporting surface.
- What is missing:
  Broader target drilldown and deeper chart interactivity.
- What is misleading:
  The page title is structured-audit oriented, so the scanner section depends on the explanatory copy to avoid scope confusion.
- Recommended change:
  Keep the current structure but continue improving drill-through and scope signage.
- Status:
  `active`

## 15. Settings / Diagnostics / Storage Diagnostics

- User-facing purpose:
  Show build truth, backend truth, scanner installation state, and storage truth.
- Actual current implementation:
  About/Diagnostics page with frontend build markers, backend version/build/startup markers, API base URL, storage paths, record counts, and garak install status.
- Data source(s) it reads:
  `/api/version`, `/api/storage/status`, `/api/garak/status`
- Data it writes:
  None.
- What makes sense:
  This is the right operator/deployment page.
- What is missing:
  Louder mismatch alarms for stale frontend vs backend pairings.
- What is misleading:
  Little; this page is one of the most truthful parts of the current product.
- Recommended change:
  Keep expanding operator smoke-test guidance here instead of scattering it.
- Status:
  `diagnostic`

## 16. Open Source Components

- User-facing purpose:
  Review open source component/license metadata.
- Actual current implementation:
  Legal/admin page listing component metadata, links, and selected notice text.
- Data source(s) it reads:
  Legal/open-source component registry.
- Data it writes:
  None.
- What makes sense:
  Correctly placed under Settings/Legal-type navigation rather than a workflow group.
- What is missing:
  Search/filtering and better grouping by function or engine family.
- What is misleading:
  Nothing major as long as it stays an administrative/legal page.
- Recommended change:
  Leave it as a settings/legal page and avoid promoting it into the primary workflow.
- Status:
  `diagnostic`
