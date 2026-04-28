# Reporting And History Integration Report

## Scope

This report covers the current-state reporting and history model after the integration/stabilization pass.

This pass did **not** add new runtime engines, destructive migrations, or new final-verdict authorities.

SpriCO PolicyDecisionEngine remains the final verdict authority.

## Current State Before This Pass

Before the code changes in this pass, the repository already had most of the intended reporting/history foundation in place:

- `Activity History` already aggregated cross-workflow activity from PyRIT memory, `audit.db`, and SpriCO storage.
- `PyRIT Attack History` was already labeled as PyRIT-scoped rather than universal history.
- `Scanner Run Reports` already treated garak runs as first-class report objects.
- No-finding scanner runs were already represented in scanner report summaries.
- Findings were already kept separate from raw evidence and no-finding scan coverage.
- The dashboard already showed scanner coverage totals, status counts, profile counts, and no-finding coverage.

The main remaining gaps were presentation-level integration gaps rather than missing storage or missing report models.

## Changes Made In This Pass

### 1. Dashboard now shows scanner coverage by target

Updated:

- `frontend/src/components/Audit/DashboardPage.tsx`

Added:

- `Scanner Runs By Target` breakdown panel sourced from the existing `scanner_runs_by_target` summary data.

Why this matters:

- The dashboard now exposes scanner coverage as a target-aware reporting view, not just as totals/status/profile counts.

### 2. Scanner Run Reports now use user-facing status labels

Updated:

- `frontend/src/components/SpriCO/ScannerRunReportsPage.tsx`

Changed:

- The scanner run table now shows friendly status labels such as `Completed - no findings` and `Not evaluated` instead of raw internal values like `completed_no_findings`.

Why this matters:

- This removes developer-ish/internal wording from a user-facing reporting page.

### 3. Added regression/verification tests around the integrated behavior

Updated / added:

- `frontend/src/components/Audit/DashboardPage.test.tsx`
- `frontend/src/components/SpriCO/ScannerRunReportsPage.test.tsx`
- `frontend/src/components/Chat/chatLayout.constants.test.ts`

Also re-ran existing page tests covering:

- `GarakScannerPage`
- `AttackHistory`
- `ActivityHistoryPage`
- `EvidencePage`
- `Navigation`

## Where Scanner No-Finding Coverage Now Appears

No-finding scanner runs are visible in these places:

1. `LLM Vulnerability Scanner`
   - Selected result messaging:
     - completed
     - no actionable scanner evidence
     - no Findings created
     - PASS for selected scan scope only

2. `Scanner Run Reports`
   - list/table row
   - selected report detail
   - report summary metrics

3. `Structured Dashboard`
   - scanner runs total
   - completed no findings
   - status breakdown
   - profile breakdown
   - target breakdown

4. `Activity History`
   - scanner category entries include completed no-finding runs as normal activity records

## Why No-Finding Runs Still Do Not Appear In Findings

This remains intentional.

Findings are still actionable-only.

No-finding scanner runs do not create Findings because:

- their `findings_count` is `0`
- the selected scan detail explicitly states that no actionable scanner evidence was produced
- the selected scan detail explicitly states that no Findings were created
- dashboard/reporting/history coverage is now the correct place to represent completed no-finding runs

This preserves the product model:

- `Scanner Run Reports` = scanner history
- `Evidence Center` = proof
- `Findings` = actionable outcomes only

## Activity History vs PyRIT Attack History

### PyRIT Attack History

Purpose:

- PyRIT-backed attack/session history only

Sources:

- PyRIT CentralMemory
- saved Interactive Audit replay references from `audit.db`

What it is not:

- not scanner run history
- not Shield history
- not Red Team Campaign history
- not universal history

### Activity History

Purpose:

- cross-workflow activity ledger

Current categories surfaced:

- PyRIT attack sessions
- Interactive/Audit runs
- Scanner runs
- Red Team Campaigns
- Shield events
- Evidence
- Findings

This is the correct cross-workflow page when a user wants to answer:

- where is my activity stored?
- did a scanner run happen even if it created no findings?
- which part of the product recorded this event?

## Pages That Now Carry The Truth More Clearly

### LLM Vulnerability Scanner

Carries these truths:

- garak is evidence/scanner only
- SpriCO PolicyDecisionEngine is final verdict authority
- PASS is limited to the selected scan scope
- completed no-finding runs are not equivalent to global safety

### Scanner Run Reports

Carries these truths:

- all scanner job outcomes belong here
- no-finding scans still count as coverage
- failed/timeout/not-evaluated runs are distinct from safe results

### Structured Dashboard

Carries these truths:

- scanner coverage is part of release visibility
- no-finding scans increase coverage without creating Findings
- scanner coverage can be analyzed by status, profile, and target

### PyRIT Attack History

Carries these truths:

- this page is scoped
- other product activity may exist elsewhere

## Data Safety / Compatibility

This pass did not:

- add destructive schema migrations
- wipe or reset DBs
- overwrite old data
- move data between stores
- change final verdict authority

The changes were additive presentation/integration changes only.

## Known Remaining Gaps

1. Live deployment still matters
   - If a live environment still shows Activity History `502`, that is a deployment/runtime mismatch problem, not a local repo code-shape problem.
   - The live backend must actually serve the current `/api/activity/history` route.

2. Activity History is still a lightweight ledger, not a full investigative console
   - It does not yet provide deep cross-category filtering, pivoting, or row-level expansion comparable to a dedicated SIEM/report explorer.

3. Scanner reporting is integrated, but target-specific drilldowns are still shallow
   - Dashboard now shows runs by target, but target pages do not yet offer a dedicated full target history surface.

4. Red Team Campaigns remains partial by design
   - The reporting/history model is honest about this, but the engine/runtime maturity is still partial.

## Result

Result for this pass:

- scanner no-finding coverage is visible in reporting/history surfaces
- Findings remain actionable-only
- Activity History remains the cross-workflow history page
- PyRIT Attack History remains clearly scoped
- dashboard reporting is materially more complete because scanner coverage now includes target breakdown
