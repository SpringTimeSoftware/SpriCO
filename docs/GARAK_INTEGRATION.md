# SpriCO garak Integration

SpriCO integrates garak as scanner evidence, not as a final policy verdict engine.

Install optional scanner and test dependencies:

```bash
python -m pip install -e ".[dev,garak]"
```

garak remains optional. Core SpriCO startup does not import or require garak, and parser/normalizer tests use fixtures when garak is absent.

Implemented API:

- `GET /api/garak/status`
- `GET /api/garak/probes`
- `GET /api/garak/detectors`
- `GET /api/garak/generators`
- `GET /api/integrations/garak/status`
- `GET /api/integrations/garak/plugins`
- `GET /api/integrations/garak/compatibility`
- `POST /api/scans/garak`
- `GET /api/scans/garak`
- `GET /api/scans/garak/reports`
- `GET /api/scans/garak/reports/summary`
- `GET /api/scans/garak/reports/{scan_id}`
- `GET /api/scans/garak/{scan_id}`
- `GET /api/scans/garak/{scan_id}/artifacts`
- `GET /api/scans/garak/{scan_id}/findings`

Validation failures:

`POST /api/scans/garak` returns a structured 400 response for request validation failures and does not create evidence or findings for those failures:

```json
{
  "error": "validation_failed",
  "message": "Cannot start scanner run.",
  "details": [
    {
      "field": "target_id",
      "reason": "Target is required."
    }
  ],
  "next_steps": [
    "Select a configured target."
  ]
}
```

The scanner UI renders the field-level reason and next steps instead of only showing `Request validation failed`.

The request schema intentionally allows `cross_domain_override` and continues to reject arbitrary extra fields. If a live server returns `body.cross_domain_override: Extra inputs are not permitted`, that backend process is running an older schema and must be restarted or redeployed from the current checkout.

Status response includes:

- `available`
- `version`
- `install_hint`
- `advanced.python_executable`
- `advanced.python_version`
- `advanced.import_error`
- `advanced.cli_error`

Legacy top-level `python`, `executable`, `import_error`, and `cli_error` fields are preserved for older clients. The main UI hides executable paths unless Advanced Diagnostics is expanded.

Install modes:

- `absent`: API returns unavailable status without crashing.
- `pip`: garak import path is under site-packages.
- `vendored` or `unknown`: detected from import path when available.

Scan behavior:

1. Validate `permission_attestation`.
2. Validate `target_id`, `policy_id`, scan profile, vulnerability categories, target compatibility, and domain-policy alignment.
3. Resolve the selected scan profile to allowlisted garak probes/detectors/buffs.
4. Create an isolated artifact directory under `dbdata/garak_scans/{scan_id}`.
5. Build a safe `python -m garak` subprocess command without `shell=True`.
6. Capture config, command metadata, stdout, stderr, exit code, JSONL/hitlog/HTML artifacts.
7. Parse JSONL/hitlog artifacts into raw scanner findings.
8. Normalize scanner findings into SpriCO evidence and `SensitiveSignal` records.
9. Run `PolicyDecisionEngine` for the final SpriCO verdict.
10. Persist scanner run metadata, artifact metadata, evidence items, scan results, and actionable findings.

Scan profiles:

- `quick_baseline`: privacy/data leakage and prompt injection baseline checks.
- `privacy_and_prompt_injection`: privacy, prompt injection, and system prompt extraction coverage.
- `deep_llm_security`: broader prompt injection, jailbreak, data leakage, RAG/tool misuse, unsafe advice, hallucination, and authorization-boundary checks.

If an installed garak version does not expose a configured plugin, SpriCO reports skipped plugin names in `profile_resolution.skipped` instead of passing arbitrary CLI options through.

Evidence sources shown in the LLM Vulnerability Scanner:

- Active: SpriCO Domain Signals. SpriCO applies the selected policy/domain pack after scanner responses. This is required for final SpriCO verdicts.
- Scanner Evidence: garak Detector Evidence. garak runs probes and detector checks, produces scanner evidence only, and cannot override the final SpriCO verdict.
- Optional / Disabled: OpenAI Judge. Optional model-based evidence for ambiguous cases, disabled by default, especially for regulated or PHI workflows. The UI enables this only when `/api/judge/status` reports backend configuration and policy enablement. API keys must come from backend secrets, not frontend input.
- Not configured: PyRIT Scorers. PyRIT scorer evidence is not wired for this scanner workflow. Interactive Audit and structured audits use PyRIT targets/memory, but this scanner path is garak-based.

OpenAI Judge request settings:

- Scanner requests may include `judge_settings.enabled`, `provider`, `mode`, and `judge_only_ambiguous`.
- `enabled=false` performs no judge action.
- `enabled=true` is rejected unless backend judge status reports the provider configured and enabled.
- Healthcare/hospital scans require `mode=redacted` by default.
- OpenAI Judge output is evidence only and cannot override SpriCO PolicyDecisionEngine.

Selected profile versus selected categories:

- The selected profile defines the allowlisted probe/detector family, default generations, and timeout.
- Selected categories constrain the active scope within that profile.
- A `deep_llm_security` run with only one selected category is category-limited, not a full deep scan.
- The UI shows selected category count, resolved probe count, skipped probe count, default generations, timeout, and whether the run is full-profile or category-limited.

Supported target handling:

- Targets are loaded from the existing SpriCO `/api/targets` registry.
- OpenAI, Azure, Gemini/Google, and local/Hugging Face-like target types are converted only when the target includes a model/deployment name.
- `GeminiFileSearchTarget` requires explicit target-level garak generator mapping before garak execution is allowed.
- Custom HTTP/RAG/chat targets require target-level `garak_generator_type` and `garak_generator_name` settings before garak execution is allowed.
- Endpoint-less or TextTarget-style targets are rejected with a clear compatibility message.
- SpriCO does not silently substitute `test/Blank` for a selected real target.
- When the selected target domain and selected policy domain differ, the scanner blocks regulated-domain runs unless the user explicitly confirms cross-domain evaluation. The request stores `cross_domain_override=true` only when that confirmation is supplied.
- Hospital, healthcare, medical, and clinical domain labels are normalized to canonical `healthcare` before the target/policy compatibility check. For example, a `Healthcare` target with a `hospital` policy is compatible without a cross-domain override.

Evaluation status:

- `ready`, `queued`, and `running` describe setup or execution in progress.
- `completed` and `completed_no_findings` mean garak produced usable scanner output and SpriCO policy evaluation ran.
- `completed_no_findings` means no detector or SpriCO domain signal required intervention for the selected profile and categories. It does not prove the target is safe against all attacks.
- `timeout`, `failed`, `unavailable`, `incompatible_target`, and `parsing_failed` are stored as `evaluation_status=not_evaluated`.
- A not-evaluated run uses `final_verdict=NOT_EVALUATED` and `risk=NOT_AVAILABLE`. It must not be displayed as `PASS/LOW`.
- If an evaluated run has `evidence_count=0`, no Evidence Center records were created because no actionable scanner evidence was produced for the selected scope.
- If `evidence_count=0` because garak timed out, failed, was unavailable, or could not run against the target, the UI explains that no usable evidence was produced and does not imply the target is safe.
- A `PASS/LOW` result is displayed as `PASS for this scan run` and `No actionable findings for selected scope`. It is not a global safety or security guarantee.

Selected Scan Report:

The LLM Vulnerability Scanner renders a structured Scan Report from the existing garak run record. It does not use a separate report store.

- Scan Summary shows status, final SpriCO verdict, risk, evidence count, findings count, target, policy, scan profile, timestamps, and duration.
- Scope Tested shows target, target type, target domain, policy, policy domain, scan profile, and selected vulnerability categories.
- Probe Coverage shows resolved probes, skipped probes, detectors, buffs, default generations, and timeout seconds from `profile_resolution`.
- Evidence & Findings shows scanner evidence count, SpriCO signal count, findings count, evidence rows when present, and a Findings action only when actionable findings exist.
- Artifact Summary shows saved/missing/not produced state for command metadata, scan config, stdout, stderr, exit code, report JSONL, hitlog JSONL, and HTML report.
- Advanced Raw Evidence remains collapsed by default and is intended for administrators/debugging.

Scanner Run Reports:

`GET /api/scans/garak/reports` exposes every scanner run as a first-class report, including `completed_no_findings`, `completed`, `timeout`, `failed`, `incompatible_target`, and other not-evaluated statuses. The user-facing `Scanner Run Reports` view lists these runs outside the active scanner workflow so successful no-finding scans remain visible after the user leaves the scanner page.

Each report includes:

- scan, target, policy, profile, status, evaluation, verdict, risk, and timestamp fields
- resolved/skipped probe counts and lists
- detector and buff counts and lists
- `default_generations`
- `timeout_seconds`, including values stored as `profile_resolution.default_timeout_seconds`
- evidence, finding, artifact, and duration counts

Dashboard/report integration:

- `GET /api/scans/garak/reports/summary` aggregates scanner runs by status, target, and profile.
- Structured Dashboard shows scanner run coverage alongside structured audit metrics.
- `completed_no_findings` contributes to scanner run count, no-finding count, target coverage, profile coverage, and artifact count.
- `completed_no_findings` does not create a Finding because Findings are reserved for actionable issues.

Persistence contract:

- Successful evaluated scanner runs create a scanner run record, scanner history item, artifact metadata when artifacts exist, Evidence Center records for parsed scanner evidence, and Findings only for actionable SpriCO outcomes.
- Validation failures create no evidence and no findings. They may be shown in the UI as validation errors, not scanner history.
- Timeout/failure/unavailable runs create a scanner run record with the relevant status and `evaluation_status=not_evaluated`. They create evidence only if usable parsed evidence exists and create findings only when actionable evidence exists.
- Findings are created only for actionable issues such as final `FAIL`, `HIGH`/`CRITICAL` risk, or high-sensitivity `NEEDS_REVIEW`. `completed_no_findings` scans do not create Findings.

Schema separation:

- `scanner_evidence` records garak engine, version, probe, detector, generator, prompt/output excerpts, raw score/status, scanner hit/no-hit result, artifact reference, and raw record.
- `sprico_final_verdict` records SpriCO verdict, violation risk, data sensitivity, policy mode, access context, disclosure type, matched signals, and explanation.

Artifact metadata:

- `artifact_id`
- `scan_id`
- `artifact_type`
- `name`
- backend path, exposed only in Advanced Diagnostics/admin APIs
- `size`
- `sha256`
- `created_at`

The scanner page summarizes artifacts without requiring administrators to inspect raw JSON:

- command metadata: saved or missing
- scan config: saved or missing
- stdout: saved or missing
- stderr: empty, saved, or missing
- exit code: saved or missing
- report.jsonl: saved, not produced, or missing
- hitlog.jsonl: saved, not produced, or missing
- html report: saved, not produced, or missing

Backend paths and raw command metadata are shown only under Advanced Diagnostics or admin APIs.

Evidence normalization:

- `engine_id`: `garak`
- `engine_name`: `garak LLM Scanner`
- `engine_type`: `scanner`
- `source_type`: `external_scanner`
- `evidence_type`: `scanner_evidence`
- target, policy, scan profile, scanner result, and final SpriCO verdict metadata

Limitations:

- garak is not bundled by SpriCO; local availability depends on the environment.
- garak is Apache-2.0 licensed and optional.
- Dynamic plugin discovery uses garak CLI list commands when available.
- Scanner scores are stored as raw evidence and never mapped directly to SpriCO PASS/FAIL.
- Secrets are redacted from command/stdout/stderr capture on a best-effort basis.

Real execution configuration:

- garak must be installed with `python -m pip install -e ".[garak]"` or `python -m pip install -e ".[dev,garak]"`.
- `permission_attestation` must be true.
- target/generator settings must come from the target registry or allowlisted scan profile mapping.
- arbitrary CLI arguments and raw generator overrides are rejected by the scanner API.
- parser and normalizer tests use fixture artifacts and do not require garak.
- the real smoke test skips unless `GARAK_TEST_ENABLED=1` and garak is installed/configured.

Integration test environment:

- Set `GARAK_TEST_ENABLED=1`.
- Optional: set `GARAK_TEST_GENERATOR_TYPE`, `GARAK_TEST_GENERATOR`, `GARAK_TEST_TARGET`, and `GARAK_TEST_PROFILE`.
- Without these variables, fixture parser/normalizer tests still run and the real garak smoke test is skipped with an explicit reason.

Final verdict rule:

- garak pass/fail remains scanner evidence.
- garak cannot override SpriCO `PolicyDecisionEngine`.
- If SpriCO policy context finds a regulated-domain violation, the SpriCO final verdict remains the authoritative result even when scanner evidence is absent or lower severity.
