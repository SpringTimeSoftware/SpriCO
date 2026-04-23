# SpriCO Red Scan Execution

`POST /api/red/scans` executes deterministic Red scans for `target_id = "mock_hospital_target"` without calling external APIs.

Request shape:

```json
{
  "target_id": "mock_hospital_target",
  "objective_ids": [],
  "policy_id": "policy_hospital_strict_v1",
  "engine": "sprico",
  "max_turns": 5,
  "max_objectives": 10,
  "converters": [],
  "scorers": []
}
```

Execution path:

1. Load the selected SpriCO policy.
2. Select objectives from the native Red objective library.
3. Generate deterministic mock attack prompts and target responses.
4. Score turns with SpriCO scoring and `PolicyDecisionEngine`.
5. Persist evidence and findings.
6. Return scan results and risk summary.

The mock hospital target includes safe refusal, PHI leakage, context-follow-up leakage, address disclosure, and public-information safe response examples. Non-mock target execution is blocked by default to avoid sending hospital, patient, PHI, PII, or audit data to external systems.

`POST /api/red/scans/{scan_id}/compare` compares two persisted Red scans and returns fixed, regressed, and new finding identifiers.
