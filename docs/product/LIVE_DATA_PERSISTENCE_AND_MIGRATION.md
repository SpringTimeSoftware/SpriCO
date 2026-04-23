# Live Data Persistence And Migration

This document explains where SpriCO stores live data and why older local history may not appear after deployment unless the original databases are migrated.

## Data Stores

| Store | Default path | Environment override | Main readers |
| --- | --- | --- | --- |
| SpriCO SQLite | `dbdata/sprico.sqlite3` | `SPRICO_SQLITE_PATH` | Evidence Center, Shield, Red Team Campaigns, LLM Vulnerability Scanner, Policies, Projects, Custom Conditions |
| SpriCO JSON fallback | `dbdata/sprico_storage.json` | `SPRICO_STORAGE_BACKEND=json` | Same SpriCO pages when JSON fallback is explicitly selected |
| PyRIT memory SQLite | `dbdata/pyrit.db` | backend startup may initialize `SQLiteMemory(db_path=...)` | Interactive Audit conversations, Attack History, labels, media |
| Audit SQLite | `dbdata/audit.db` | constructor argument in `AuditDatabase`; target store can use `SPRICO_TARGET_DB_PATH` | Audit Runs, dashboards, benchmark library, target configuration |
| Target configuration | `dbdata/audit.db` by default | `SPRICO_TARGET_DB_PATH` | Target Configuration, active target selection, scanner/Red target registry |
| garak artifacts | `dbdata/garak_scans/{scan_id}/` | none currently; based on `DB_DATA_PATH` | LLM Vulnerability Scanner diagnostics and artifact metadata |
| PyRIT media/artifacts | `dbdata/` | PyRIT `DB_DATA_PATH` derivation | message media and serialized prompt artifacts |

`DB_DATA_PATH` is computed by `pyrit.common.path`. In this checkout it resolves to the repository-adjacent `dbdata` directory when running from the git repository.

## Page To Store Mapping

| Page | Primary data source |
| --- | --- |
| Interactive Audit | PyRIT memory SQLite through `CentralMemory`, plus selected target configuration |
| Attack History | PyRIT memory SQLite attack sessions only |
| Audit Runs | `dbdata/audit.db` |
| LLM Vulnerability Scanner | SpriCO SQLite `garak_runs`, `garak_artifacts`, `scans`, `scan_results`, `evidence_items`, and artifact files under `dbdata/garak_scans/` |
| Scanner Run Reports | SpriCO SQLite `garak_runs` and `garak_artifacts`; report projection from existing scanner run records |
| Evidence Center | SpriCO SQLite `evidence_items` |
| Findings | SpriCO SQLite `findings` and audit findings from `audit.db` depending view |
| Red Team Campaigns | SpriCO SQLite `red_scans`, `scans`, `scan_results`, `evidence_items`, `findings` |
| Shield | SpriCO SQLite `shield_events` and `evidence_items` |
| Policies / Projects / Custom Conditions | SpriCO SQLite policy/project/condition tables |
| Target Configuration | target records in `audit.db` by default |

## Backup Before Live Deployment

Back up these paths before replacing or moving a live instance:

- `dbdata/sprico.sqlite3`
- `dbdata/sprico_storage.json`, if `SPRICO_STORAGE_BACKEND=json` was used
- `dbdata/pyrit.db`
- `dbdata/audit.db`
- `dbdata/garak_scans/`
- `dbdata/target_secrets.key`
- any uploaded media or serialized PyRIT files under `dbdata/`

If environment variables point elsewhere, back up those resolved paths instead.

## Migrating Local Or Dev History To Live

1. Stop backend and frontend processes.
2. Back up the live server `dbdata` directory.
3. Copy the source `sprico.sqlite3`, `pyrit.db`, `audit.db`, `garak_scans/`, `target_secrets.key`, and related uploaded media into the live server `dbdata` directory.
4. Preserve file permissions so the backend service account can read and write the files.
5. Restart the backend.
6. Confirm `/api/version` reports the expected database information where available.
7. Open Attack History for PyRIT sessions, Audit Runs for structured audits, LLM Vulnerability Scanner for scanner history, Red Team Campaigns for campaign runs, and Evidence Center for normalized evidence.

Do not copy only the frontend build. The frontend does not contain live history.

## Export And Import Status

- Audit Runs can be viewed and reported through existing audit APIs and UI.
- Static exported HTML transcripts are not live backend records.
- Import old exported HTML transcript: not implemented yet.
- To preserve old transcript history in live SpriCO, migrate the original backend databases or replay/import the source conversations through supported backend workflows.

## Empty `dbdata`

If `dbdata` is empty, SpriCO creates fresh stores on startup. Default policies may be seeded, but old PyRIT attacks, audit runs, targets, scanner runs, evidence, findings, and artifacts will not appear.

This is the common reason old history disappears after deployment: the live server is reading a fresh `dbdata` directory instead of the original databases.

## Verifying The Active Storage

Use these checks:

- `/api/version` for backend version and database info exposed by the app.
- Target Configuration to confirm expected configured targets.
- Attack History to confirm PyRIT CentralMemory attack sessions.
- Audit Runs to confirm `audit.db` records.
- Evidence Center to confirm SpriCO `evidence_items`.
- LLM Vulnerability Scanner history or Scanner Run Reports to confirm `garak_runs`.

If the UI is empty but old files exist elsewhere, verify the backend working directory, service account, environment variables, and `DB_DATA_PATH` resolution.

## Storage Status Endpoint

`GET /api/storage/status` returns safe metadata only:

- active SpriCO storage backend
- resolved SpriCO SQLite or JSON storage path
- PyRIT memory database path, when discoverable
- audit database path
- target configuration store path
- policy/project/condition store path
- garak artifact root
- uploaded artifact root
- record counts for scanner runs, Red scans, Shield events, Evidence Center records, Findings, policies, projects, conditions, PyRIT attack sessions, and audit runs

The endpoint must not expose secrets or raw file contents. Use it to verify that the live server is reading the expected storage paths and record counts after deployment.
