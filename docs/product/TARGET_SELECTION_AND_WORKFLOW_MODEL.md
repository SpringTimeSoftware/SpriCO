# Target Selection And Workflow Model

SpriCO uses one configured target registry for testing workflows. Targets are created and managed in Settings -> Configuration and are exposed through `/api/targets`.

## Target Registry Concept

Each configured target record includes the saved registry identifier, display name, target type, endpoint, model name, target-specific parameters, active/archive state, and persistence metadata. Scanner and campaign pages do not create a separate target store.

Frontend target selection is centralized in:

`frontend/src/components/SpriCO/UnifiedTargetSelector.tsx`

Backend target data comes from:

`pyrit/backend/routes/targets.py`

## Workflow Compatibility Matrix

| Workflow | Target source | Required target fields | Permission required before run | Notes |
| --- | --- | --- | --- | --- |
| Interactive Audit | `/api/targets/active` and existing target config flow | Existing active/configured target | Existing workflow behavior preserved | No routing rewrite. |
| LLM Vulnerability Scanner | `/api/targets` | configured target id, policy id, non-TextTarget, endpoint, garak-compatible generator mapping when garak execution is requested | yes | garak is optional scanner evidence only. |
| Red Team Campaigns - Demo | built-in `mock_hospital_target` | none | no | Demo-only deterministic target. |
| Red Team Campaigns - Real | `/api/targets` | configured target id, non-TextTarget, endpoint | yes | Never falls back to mock. |
| Shield | policy/check metadata today | target id optional | depends on policy context | Future UI can reuse `UnifiedTargetSelector`. |
| Evidence / Findings | stored scan/audit records | target id/name/type when available | n/a | Evidence stores target metadata with scan output. |

## Target Type Requirements

Scanner and real campaign execution require a configured endpoint because they send prompts to a target or need a compatible scanner generator configuration. `TextTarget` and other endpoint-less targets can still appear in the selector, but execution is blocked with a clear validation message.

garak-compatible scanner targets are resolved conservatively:

- OpenAI, Azure, Gemini/Google, and local/Hugging Face-style targets must include a model or deployment name that garak can use.
- `GeminiFileSearchTarget` needs explicit scanner generator mapping before garak can run.
- Custom HTTP/RAG/chat targets require target-level `garak_generator_type` and `garak_generator_name` settings before garak scanner execution is allowed.
- The scanner API rejects raw CLI arguments and raw generator overrides from the frontend.
- If a target is valid for Interactive Audit but cannot be converted safely for garak, SpriCO returns: `Selected target is configured for Interactive Audit but not yet compatible with garak scanner execution.`

The selector derives user-facing metadata from existing target fields:

- target name: `display_name` or `target_registry_name`
- target type: `target_type`
- provider: derived from target type and endpoint
- domain: target parameters when present, otherwise safe name heuristics
- connection/config status: endpoint configured or missing endpoint
- policy pack: target parameters or derived domain
- compatible workflows: Interactive Audit, Shield, LLM Vulnerability Scanner, Red Team Campaigns

## Scanner Flow

LLM Vulnerability Scanner groups setup into:

1. Target & Permission
2. Domain Policy
3. Scanner Setup
4. Evidence Engines
5. Advanced Diagnostics

Users must select a configured target and confirm permission attestation before running. External engines provide attack/evidence signals. SpriCO PolicyDecisionEngine remains the final verdict authority.

The scanner UI separates two concepts:

- Current Scan Configuration: the target, policy, scan profile, and evidence sources the user has selected for the next run.
- Selected Scan Result: the saved historical run currently displayed in the result panel.

If the displayed historical result was run against a different target than the current configuration, the page shows: `You are viewing a previous scan result for {result_target}. Current configuration target is {selected_target}.`

Domain-policy alignment is checked before execution. If the selected target domain differs from the selected policy domain, the scanner shows a warning such as `Selected target domain is HR, but selected policy is hospital. Choose a matching policy or confirm cross-domain evaluation.` Regulated-domain runs are blocked by default until the user explicitly confirms cross-domain evaluation; the backend stores that as `cross_domain_override=true`.

The scanner request requires:

- `target_id`
- `policy_id`
- `scan_profile`
- `vulnerability_categories`
- `permission_attestation=true`
- optional `max_attempts` and `timeout_seconds`

Scan profiles are allowlisted backend mappings. The UI does not send arbitrary garak command-line arguments.

Timeout, failure, unavailable, incompatible-target, and parsing-failed scanner runs are not evaluated as safe. These runs are stored with `evaluation_status=not_evaluated`, `final_verdict=NOT_EVALUATED`, and `risk=NOT_AVAILABLE`. `PASS/LOW` is shown only when the scanner completed, produced usable parsed results or attempts, and SpriCO policy evaluation completed with no actionable evidence.

Scanner validation failures are not scanner results. Missing target, missing permission attestation, unsupported profile, missing endpoint mapping, missing garak generator metadata, and domain-policy mismatch return structured validation errors and do not create evidence or findings.

LLM Vulnerability Scanner History records scanner jobs. Evidence Center stores the proof produced by completed scans. Findings stores actionable issues.

## Red Team Campaign Flow

Red Team Campaigns begins with Campaign Mode:

- Demo mock scan uses `mock_hospital_target`.
- Real target scan uses `UnifiedTargetSelector` and requires permission attestation.

If Real target scan is selected and the target is missing endpoint/configuration, the UI and API block execution. The backend does not silently fall back to the demo mock target.

## Evidence Storage

Scanner and Red outputs include target and policy metadata where available:

- `target_id`
- `target_name`
- `target_type`
- `policy_id`
- `scan_id`
- engine/evidence source metadata
- final SpriCO verdict fields

External engine output remains evidence only. SpriCO PolicyDecisionEngine remains the final verdict authority.

garak scanner runs now persist:

- `garak_runs`
- `garak_artifacts`
- `scans`
- `scan_results`
- `evidence_items`
- actionable `findings` when the final SpriCO verdict/risk warrants triage
