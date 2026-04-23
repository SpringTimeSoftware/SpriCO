# SpriCO Storage

SpriCO uses SQLite by default for project, policy, evidence, scan, finding, Shield, garak, and Red records.

Default:

```bash
SPRICO_STORAGE_BACKEND=sqlite
```

JSON fallback:

```bash
SPRICO_STORAGE_BACKEND=json
```

Tables/collections:

- `projects`
- `policies`
- `policy_versions`
- `scans`
- `scan_results`
- `findings`
- `evidence_items`
- `audit_history`
- `shield_events`
- `garak_runs`
- `garak_artifacts`
- `red_scans`

Policies keep version records and audit history. Evidence stores scanner/runtime evidence separately from final SpriCO verdict fields. Patient, PHI, PII, and audit data are not sent to external APIs by the storage layer.
