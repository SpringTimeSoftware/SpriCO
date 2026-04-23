# External Engine Runtime Roadmap

This document records the Phase B runtime status for SpriCO external engines and evidence flows.

## Final Verdict Rule

External engines provide attack and evidence signals. SpriCO `PolicyDecisionEngine` produces the final policy-aware verdict.

No external engine is exposed as a final verdict authority for regulated-domain audits.

## garak

Status: optional runtime path implemented.

- garak is an optional dependency: `python -m pip install -e ".[dev,garak]"`.
- Core SpriCO startup works when garak is not installed.
- `/api/garak/status` reports availability, version, Python executable, import error, CLI error, and install hint.
- Scan execution validates `permission_attestation`, validates allowlisted generator/probe/detector/buff options, invokes garak without `shell=True`, captures artifacts, parses reports, normalizes findings into evidence, and stores SpriCO final verdict separately.
- Parser and normalizer tests use fixture artifacts and do not require garak.
- Real garak smoke test skips with an explicit reason when garak is not installed.

garak output is scanner evidence only. It cannot override SpriCO final verdicts.

## DeepTeam

Status: deferred, metadata/status only.

DeepTeam runtime execution is not implemented in this phase. A future optional adapter may support RAG and agent vulnerability evidence, but results must remain evidence only and must not directly set PASS/FAIL.

## promptfoo

Status: deferred, metadata/status only.

promptfoo runtime execution is not implemented in this phase. SpriCO-native AuditSpec/assertions should be built first. A future adapter may import/export promptfoo-style assertions, but assertion results must remain evidence only.

## Red Team Campaigns

Status: demo mock path plus permission-gated real target path.

- `mock_hospital_target` remains the deterministic demo target.
- Real target execution requires a configured SpriCO target endpoint and `permission_attestation=true`.
- The API does not silently fall back to the mock target when a real target is selected.
- Unsupported or metadata-only engines return validation errors.
- Red scan turns, evidence, findings, and scan results persist through SpriCO storage.

## Interactive Audit Evidence

Status: new scored turns create normalized Evidence Center records.

- Evidence type: `interactive_audit_turn`.
- Engine ID: `sprico_interactive_audit`.
- Dedupe key: `interactive_audit:{conversation_id}:{turn_id}:{score_version}`.
- Stored fields include prompt, response, target metadata, context window, evaluator result, policy context, matched signals, and SpriCO final verdict.
- Existing historical transcript turns are not migrated automatically.

## Evidence Center

Status: normalized display/filtering improved.

Evidence Center can filter by engine, engine type, scan/session/conversation ID, policy ID, risk, final verdict, and evidence ID. Records may use `engine`, `engine_id`, or `engine_name`; UI display normalizes these fields.

## External Engine Metadata UI

Status: implemented under Settings.

The page lists attack/evidence engines, availability, installed version, license, source, install hints, and capability flags. External engines show final verdict capability as `No`. SpriCO `PolicyDecisionEngine` is shown as locked final verdict authority.
