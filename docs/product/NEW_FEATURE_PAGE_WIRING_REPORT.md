# New Feature / Page Wiring Report

Generated from the current repository code. This report is documentation-only and does not change application behavior.

Phase A navigation result is documented in `docs/product/NAVIGATION_AND_PAGE_RELATIONSHIPS.md`. The original inventory below is preserved as the factual baseline used for the redesign.

## 1. Runtime / Environment Status

| Item | Current status |
| --- | --- |
| Backend framework | FastAPI application in `pyrit/backend/main.py`. |
| Backend startup command | Preferred package entrypoint is `pyrit_backend` from `pyproject.toml`. Direct development smoke testing can use `python -m uvicorn pyrit.backend.main:app --host 127.0.0.1 --port 8000` with `PYRIT_DEV_MODE=true`, but `pyrit/backend/main.py` warns the package entrypoint is preferred. |
| Frontend framework | React + TypeScript + Vite + Fluent UI. |
| Frontend startup command | `cd frontend && npm run dev`. Production build command is `cd frontend && npm run build`. |
| Current API base URL mechanism | `frontend/src/services/api.ts` uses `import.meta.env.VITE_API_URL || '/api'`. The actual variable is `VITE_API_URL`, not `VITE_API_BASE_URL`. |
| Expected frontend port | Vite config uses port `3000` in `frontend/vite.config.ts`. |
| Expected backend port | Vite dev proxy maps `/api` to `http://127.0.0.1:8000`. |
| localhost:3000 stale risk | Yes. During verification, current code was also smoke-tested on temporary ports `3011` frontend and `8011` backend because an existing `localhost:3000` / `8000` pair may be stale or served by scheduled tasks. |
| Confirm both are latest | Rebuild or restart both processes from the checkout being tested. Confirm frontend bundle timestamp by running `npm run build`; confirm backend by hitting `/api/version`, `/api/legal/open-source-components`, and `/api/external-engines` from the same browser session. |
| Is `VITE_API_BASE_URL` required? | No. The current code reads `VITE_API_URL`. If unset, the frontend calls `/api` and relies on Vite or production reverse proxy routing. |
| Storage location | SpriCO storage defaults to SQLite through `pyrit/backend/sprico/storage.py`. SQLite path defaults to `dbdata/sprico.sqlite3` unless `SPRICO_SQLITE_PATH` is set. JSON fallback is available with `SPRICO_STORAGE_BACKEND=json`, defaulting to `dbdata/sprico_storage.json`. garak artifacts are written under `dbdata/garak_scans/{scan_id}`. |

## 2. Existing Navigation Inventory

Navigation is implemented with `currentView` state, not React Router.

Main files:

- `frontend/src/components/Sidebar/Navigation.tsx`
- `frontend/src/App.tsx`

| View ID | Display label | Icon / abbreviation | Component rendered | Component file | Existing before external-engine work | New | Visible in left rail | Should remain primary navigation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `chat` | Interactive Audit | `ChatRegular` | `ChatWindow` | `frontend/src/components/ChatWindow.tsx` | yes | no | yes | yes |
| `history` | Attack History | `HistoryRegular` | `AttackHistory` | `frontend/src/components/AttackHistory.tsx` | yes | no | yes | no, should be grouped under Audit Workbench |
| `config` | Configuration | `SettingsRegular` | `TargetConfig` | `frontend/src/components/TargetConfig.tsx` | yes | no | yes | no, should be grouped under Settings or Audit Workbench |
| `audit` | Audit | `ShieldRegular` | `AuditPage` | `frontend/src/components/Audit/AuditPage.tsx` | yes | no | yes | yes |
| `dashboard` | Structured Dashboard | `DataTrendingRegular` | `DashboardPage` | `frontend/src/components/Dashboard/DashboardPage.tsx` | yes | no | yes | no, should be grouped under Dashboards |
| `heatmap-dashboard` | Heatmap Dashboard | `Hx` | `HeatmapDashboardPage` | `frontend/src/components/Dashboard/HeatmapDashboardPage.tsx` | yes | no | yes | no, should be grouped under Dashboards |
| `stability-dashboard` | Stability Dashboard | `St` | `StabilityDashboardPage` | `frontend/src/components/Dashboard/StabilityDashboardPage.tsx` | yes | no | yes | no, should be grouped under Dashboards |
| `benchmark-library` | Benchmark Library | `Bm` | `BenchmarkLibraryPage` | `frontend/src/components/BenchmarkLibraryPage.tsx` | yes | no | yes | no, should be grouped under Library |
| `findings` | Findings | `Fi` | `AuditPage` with `forcedWorkspaceView="findings"` | `frontend/src/components/Audit/AuditPage.tsx` | yes | no | yes | no, should be grouped under Audit Workbench or Evidence |
| `prompt-variants` | Prompt Variants | `Pv` | `PromptVariantsPage` | `frontend/src/components/PromptVariantsPage.tsx` | yes | no | yes | no, should be grouped under Library |
| `target-help` | Target Help | `?` | `TargetHelpPage` | `frontend/src/components/TargetHelpPage.tsx` | yes | no | yes | no, should be grouped under Settings or Help |
| `garak-scanner` | garak Scanner | `Gk` | `GarakScannerPage` | `frontend/src/components/SpriCO/GarakScannerPage.tsx` | no | yes | yes | no, should be renamed or moved under Scanners / Advanced |
| `shield` | Shield | `ShieldRegular` | `ShieldPage` | `frontend/src/components/SpriCO/ShieldPage.tsx` | no | yes | yes | yes, but grouped under Policies |
| `policy` | Policy | `Po` | `PolicyPage` | `frontend/src/components/SpriCO/PolicyPage.tsx` | no | yes | yes | yes, but grouped under Policies |
| `red` | Red | `Rd` | `RedPage` | `frontend/src/components/SpriCO/RedPage.tsx` | no | yes | yes | yes, renamed as Auto Attacks or Red Team Campaigns |
| `evidence` | Evidence | `Ev` | `EvidencePage` | `frontend/src/components/SpriCO/EvidencePage.tsx` | no | yes | yes | yes, renamed as Evidence Center |
| `conditions` | Custom Conditions | `Cd` | `CustomConditionsPage` | `frontend/src/components/SpriCO/CustomConditionsPage.tsx` | no | yes | yes | yes, but grouped under Policies |
| `open-source-components` | Open Source Components | `Li` | `OpenSourceComponentsPage` | `frontend/src/components/SpriCO/OpenSourceComponentsPage.tsx` | no | yes | yes | no, should be under Settings / Legal |

The left rail is currently too flat. All views are directly visible, including advanced diagnostics and legal metadata pages.

## 3. Backend API Inventory

### Legal / Open Source Components

Files:

- `pyrit/backend/routes/legal.py`
- `pyrit/backend/sprico/external_engines.py`

| Endpoint | Method | Request schema | Response schema | Storage used | Persists data | Static / registry only | Production safety | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/api/legal/open-source-components` | GET | none | `{ "components": [...], "notice": ... }` | fixed in-code registry plus checked-in files under `third_party/<tool>/` | no | yes | safe; whitelisted registry only | Registry is manually maintained. |
| `/api/legal/open-source-components/{component_id}` | GET | path `component_id` | component metadata and license/source/version text | fixed registry | no | yes | safe; unknown IDs rejected | Only `garak`, `deepteam`, `promptfoo` are supported. |
| `/api/legal/open-source-components/{component_id}/license` | GET | path `component_id` | license file text / response | fixed registry | no | yes | safe; no arbitrary path parameter | no known critical gap |
| `/api/legal/open-source-components/{component_id}/source` | GET | path `component_id` | source text / response | fixed registry | no | yes | safe; no arbitrary path parameter | no known critical gap |
| `/api/legal/open-source-components/{component_id}/version` | GET | path `component_id` | version text / response | fixed registry | no | yes | safe; no arbitrary path parameter | no known critical gap |

Actual canonical license paths in this checkout are:

- `third_party/garak/LICENSE.txt`
- `third_party/deepteam/LICENSE.txt`
- `third_party/promptfoo/LICENSE.txt`

The docs note that the current checkout uses `third_party/<tool>/`, not `third_party/licenses/<tool>/`.

### External Engines

Files:

- `pyrit/backend/routes/external_engines.py`
- `pyrit/backend/sprico/external_engines.py`

| Endpoint | Method | Request schema | Response schema | Storage used | Persists data | Static / registry only | Production safety | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/api/external-engines` | GET | none | attack engines, evidence engines, final verdict authority, regulated-domain lock metadata | in-code registry and optional local import checks | no | mostly yes | safe; external engines are metadata/evidence only | DeepTeam and promptfoo are metadata-only in this phase. |

Classification in current code:

- Attack Engine: `sprico_manual`, `pyrit`, `garak`, `deepteam`, `promptfoo_import_or_assertions`
- Evidence Engine: `sprico_domain_signals`, `garak_detector`, `deepteam_metric`, `promptfoo_assertion`, `pyrit_scorer`, `openai_judge`
- Final Verdict Authority: `sprico_policy_decision_engine`

No external engine is exposed as a final verdict engine.

### Custom Conditions

Files:

- `pyrit/backend/routes/conditions.py`
- `pyrit/backend/sprico/conditions.py`
- `pyrit/backend/sprico/storage.py`

| Endpoint | Method | Request schema | Response schema | Storage used | Persists data | Production safety | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/api/conditions/types` | GET | none | allowed declarative condition types and lifecycle metadata | static service data | no | safe | no known critical gap |
| `/api/conditions` | GET | query filters | condition list | SQLite `custom_conditions` / JSON fallback | no | safe | no pagination beyond current implementation limits. |
| `/api/conditions` | POST | condition definition | created draft condition | SQLite `custom_conditions`, `condition_versions`, `condition_audit_history` | yes | safe; rejects unsafe condition types | no RBAC / user identity enforcement beyond supplied author metadata. |
| `/api/conditions/{condition_id}` | GET | path ID | condition detail | SQLite / JSON fallback | no | safe | no known critical gap |
| `/api/conditions/{condition_id}/simulate` | POST | simulation payload | simulation result with emitted `SensitiveSignal`s | SQLite `condition_simulations`, audit history | yes | safe; no arbitrary code execution | LLM judge condition remains optional/disabled by default. |
| `/api/conditions/{condition_id}/tests` | POST | positive/negative test case | stored test case | SQLite `condition_tests`, audit history | yes | safe | UI support is basic. |
| `/api/conditions/{condition_id}/approve` | POST | approver metadata | approved condition version | SQLite condition records and audit history | yes | safe | no separate approval identity provider. |
| `/api/conditions/{condition_id}/activate` | POST | activation payload | active/monitor condition or validation errors | SQLite condition records and audit history | yes | safe; enforces tests, simulation, approval, frozen version, audit history | UI has activation but no full monitoring workspace. |
| `/api/conditions/{condition_id}/retire` | POST | retire metadata | retired condition | SQLite / JSON fallback | yes | safe | UI control not implemented. |
| `/api/conditions/{condition_id}/rollback` | POST | rollback target | new rolled-back condition version | SQLite / JSON fallback | yes | safe | UI control not implemented. |
| `/api/conditions/{condition_id}/versions` | GET | path ID | version list | SQLite `condition_versions` | no | safe | no known critical gap |
| `/api/conditions/{condition_id}/audit-history` | GET | path ID | audit history | SQLite `condition_audit_history` | no | safe | no known critical gap |

Allowed condition types:

- `keyword_match`
- `regex_match`
- `entity_linkage`
- `sensitive_signal_match`
- `policy_context_match`
- `threshold_condition`
- `composite_condition`
- `llm_judge_condition` disabled by default

Unsafe arbitrary Python, JavaScript, shell, SQL, or custom code conditions are not implemented and are rejected.

### Evidence

Files:

- `pyrit/backend/routes/evidence.py`
- `pyrit/backend/sprico/evidence_store.py`
- `pyrit/backend/sprico/storage.py`

| Endpoint | Method | Request schema | Response schema | Storage used | Persists data | Production safety | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/api/evidence` | GET | query: `limit`, `scan_id`, `engine`, `policy_id`, `risk` | evidence list | SQLite `evidence_items` / JSON fallback | no | read-only safe | Filtering uses `engine`; some records use `engine_id`, so product filters may need normalization. |

Evidence writes happen from services such as Shield, Red, and garak runner rather than from a public create endpoint.

### garak

Files:

- `pyrit/backend/routes/garak.py`
- `pyrit/backend/sprico/integrations/garak/runner.py`
- `pyrit/backend/sprico/integrations/garak/parser.py`
- `pyrit/backend/sprico/integrations/garak/normalizer.py`
- `pyrit/backend/sprico/storage.py`

| Endpoint | Method | Request schema | Response schema | Storage used | Persists data | Production safety | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/api/garak/status` | GET | none | availability, version, python, executable, import error, CLI error, install hint | optional local garak import / CLI check | no | safe | availability depends on optional install. |
| `/api/integrations/garak/status` | GET | none | same as `/api/garak/status` | same | no | safe | compatibility alias. |
| `/api/garak/plugins` | GET | none | probes, detectors, generators if available | optional garak | no | safe | limited by garak install. |
| `/api/integrations/garak/plugins` | GET | none | same as `/api/garak/plugins` | optional garak | no | safe | compatibility alias. |
| `/api/garak/probes` | GET | none | probe list | optional garak | no | safe | may be empty if garak unavailable. |
| `/api/garak/detectors` | GET | none | detector list | optional garak | no | safe | may be empty if garak unavailable. |
| `/api/garak/generators` | GET | none | generator list | optional garak | no | safe | may be empty if garak unavailable. |
| `/api/garak/compatibility` | GET | none | compatibility metadata | optional garak | no | safe | no known critical gap |
| `/api/integrations/garak/compatibility` | GET | none | same as `/api/garak/compatibility` | optional garak | no | safe | compatibility alias. |
| `/api/scans/garak` | POST | target, generator, probes, detectors, policy/context, permission attestation | scan result with scanner evidence and SpriCO final verdict | SQLite `garak_runs`, `garak_artifacts`, `evidence_items`; file artifacts under `dbdata/garak_scans/{scan_id}` | yes | guarded by `permission_attestation`; garak optional | Real scan execution depends on garak and target configuration. |
| `/api/scans/garak` | GET | none / filters | garak run history | SQLite / JSON fallback | no | safe | no known critical gap |
| `/api/scans/garak/{scan_id}` | GET | path ID | garak run metadata | SQLite / JSON fallback | no | safe | no known critical gap |
| `/api/scans/garak/{scan_id}/artifacts` | GET | path ID | artifact metadata | SQLite `garak_artifacts` | no | safe | artifact content serving is intentionally limited. |
| `/api/scans/garak/{scan_id}/findings` | GET | path ID | normalized evidence / findings | SQLite `evidence_items` | no | safe | no known critical gap |

garak raw output is normalized as scanner evidence. SpriCO final verdict is produced separately by `PolicyDecisionEngine`.

### Red

Files:

- `pyrit/backend/routes/red.py`
- `pyrit/backend/sprico/red.py`
- `pyrit/backend/sprico/storage.py`

| Endpoint | Method | Request schema | Response schema | Storage used | Persists data | Production safety | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/api/red/objectives` | GET | none / filters | objective library | in-code objective templates | no | safe | not yet a full editable objective library. |
| `/api/red/scans` | POST | `target_id`, `objective_ids`, `policy_id`, `engine`, `max_turns`, `max_objectives`, `converters`, `scorers` | scan result with turns, evidence, findings | SQLite `red_scans`, `scans`, `scan_results`, `evidence_items`, `findings` | yes | safe for `mock_hospital_target`; external/real target execution is limited | External attack engines are not product-complete executors here. |
| `/api/red/scans/{scan_id}` | GET | path ID | scan metadata | SQLite / JSON fallback | no | safe | no known critical gap |
| `/api/red/scans/{scan_id}/results` | GET | path ID | scan result details | SQLite / JSON fallback | no | safe | no known critical gap |
| `/api/red/scans/{scan_id}/compare` | POST | comparison scan ID | diff/comparison result | SQLite / JSON fallback | no | safe | only compares persisted Red scan data. |

Current Red execution is product-partial. It executes deterministic mock hospital target scans and persists results, but it is not a full PyRIT/garak/DeepTeam/promptfoo campaign runner.

### Shield

Files:

- `pyrit/backend/routes/shield.py`
- `pyrit/backend/sprico/shield.py`
- `pyrit/backend/sprico/evidence_store.py`

| Endpoint | Method | Request schema | Response schema | Storage used | Persists data | Production safety | Known gaps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/api/shield/check` | POST | prompt, response/context, policy ID, access context, metadata | decision, matched signals, grouped DLP/PHI/secrets/content/link sections | SQLite `evidence_items`; Shield events in `shield_events` for Shield engine records | yes | safe; native deterministic checks, no external API by default | no enterprise auth integration in this slice. |

Shield is implemented natively. Lakera is not bundled and no external Lakera Guard connector is implemented.

### Policies / Projects

Files:

- `pyrit/backend/routes/policies.py`
- `pyrit/backend/routes/projects.py`
- `pyrit/backend/sprico/policy_store.py`
- `pyrit/backend/sprico/storage.py`

| Endpoint group | Methods | Storage used | Persists data | Known gaps |
| --- | --- | --- | --- | --- |
| `/api/projects` | GET, POST | SQLite `projects` / JSON fallback | yes on POST | no full enterprise RBAC. |
| `/api/projects/{project_id}` | GET/PATCH style route support in project route | SQLite `projects` / JSON fallback | yes on update | no full enterprise RBAC. |
| `/api/policies` | GET, POST | SQLite `policies`, `policy_versions`, `audit_history` / JSON fallback | yes on POST | policy governance is functional but not a complete enterprise approval system. |
| `/api/policies/{policy_id}` | GET/PATCH style route support in policy route | SQLite `policies`, `policy_versions`, `audit_history` / JSON fallback | yes on update | no full enterprise RBAC. |
| `/api/policies/{policy_id}/simulate` | POST | policy store / policy engine | may write audit history depending path | partial | no known critical gap |
| `/api/policies/{policy_id}/audit-history` | GET | SQLite `audit_history` | no | no known critical gap |
| `/api/policies/{policy_id}/versions` | GET | SQLite `policy_versions` | no | no known critical gap |

## 4. Page-to-API Wiring

### garak Scanner

| Item | Status |
| --- | --- |
| Component file | `frontend/src/components/SpriCO/GarakScannerPage.tsx` |
| View ID | `garak-scanner` |
| APIs called on load | `garakApi.getStatus()`, `garakApi.getPlugins()`, `garakApi.listScans()` |
| APIs called on save/create/update/delete | `garakApi.createScan()` on run |
| Persists after reload | Scan metadata and evidence persist when backend run is created. Status/config do not persist because they are runtime metadata. |
| Loading state | implemented |
| Error state | implemented |
| Empty state | implemented for plugins/history availability |
| Mock/static data | Uses runtime registry/status. Results depend on optional garak. |
| Functional status | partial. Status/history/unavailable path works. Real garak scans require optional garak install and valid target/generator setup. |

### Red

| Item | Status |
| --- | --- |
| Component file | `frontend/src/components/SpriCO/RedPage.tsx` |
| View ID | `red` |
| APIs called on load | `spricoRedApi.objectives()`, `spricoPoliciesApi.list()` |
| APIs called on save/create/update/delete | `spricoRedApi.createScan()`, `spricoRedApi.compare()` |
| Persists after reload | Red scan results persist in backend storage. |
| Loading state | implemented |
| Error state | implemented |
| Empty state | implemented enough for objectives/results |
| Mock/static data | Deterministic `mock_hospital_target` is the implemented execution target. External engine choices are displayed but not full external executors. |
| Functional status | partial. Mock Red scans execute and persist. Full external campaign execution is not implemented. |

### Evidence

| Item | Status |
| --- | --- |
| Component file | `frontend/src/components/SpriCO/EvidencePage.tsx` |
| View ID | `evidence` |
| APIs called on load | `spricoEvidenceApi.list(...)` |
| APIs called on save/create/update/delete | none |
| Persists after reload | yes, if evidence was written by Shield, Red, or garak services |
| Loading state | implemented |
| Error state | implemented |
| Empty state | implemented |
| Mock/static data | no page-owned mock data found |
| Functional status | functional read-only Evidence Center. Some product filter normalization remains. |

### Shield

| Item | Status |
| --- | --- |
| Component file | `frontend/src/components/SpriCO/ShieldPage.tsx` |
| View ID | `shield` |
| APIs called on load | `spricoPoliciesApi.list()` |
| APIs called on save/create/update/delete | `shieldApi.check()` |
| Persists after reload | Shield checks persist evidence/events through backend evidence store. |
| Loading state | implemented |
| Error state | implemented |
| Empty state | implemented |
| Mock/static data | no external mock service; native deterministic checks |
| Functional status | functional runtime policy check page. |

### Policy

| Item | Status |
| --- | --- |
| Component file | `frontend/src/components/SpriCO/PolicyPage.tsx` |
| View ID | `policy` |
| APIs called on load | `spricoProjectsApi.list()`, `spricoPoliciesApi.list()`, selected policy audit history |
| APIs called on save/create/update/delete | project create, policy create/update, policy simulate |
| Persists after reload | yes |
| Loading state | implemented |
| Error state | implemented |
| Empty state | partial but present |
| Mock/static data | no primary mock data found |
| Functional status | functional policy/project page, not a complete enterprise governance suite. |

### Custom Conditions

| Item | Status |
| --- | --- |
| Component file | `frontend/src/components/SpriCO/CustomConditionsPage.tsx` |
| View ID | `conditions` |
| APIs called on load | `spricoConditionsApi.types()`, `spricoConditionsApi.list()` |
| APIs called on save/create/update/delete | create, simulate, add test, approve, activate |
| Persists after reload | yes |
| Loading state | implemented |
| Error state | implemented |
| Empty state | implemented |
| Mock/static data | no unsafe code runner; form uses declarative examples/defaults |
| Functional status | partial product UI. Backend supports rollback/retire/history, but UI does not expose rollback/retire controls. |

### Open Source Components

| Item | Status |
| --- | --- |
| Component file | `frontend/src/components/SpriCO/OpenSourceComponentsPage.tsx` |
| View ID | `open-source-components` |
| APIs called on load | `legalApi.listOpenSourceComponents()` |
| APIs called on save/create/update/delete | none |
| Persists after reload | static registry; no user data |
| Loading state | implemented |
| Error state | implemented |
| Empty state | implemented |
| Mock/static data | fixed legal registry from backend |
| Functional status | functional legal metadata page. |

## 5. Data Persistence Verification

| Feature | Actually saved | Storage path / table | Save function path | Load function path | Tested status | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| Custom Conditions | yes | SQLite `custom_conditions`; JSON fallback `custom_conditions` | `pyrit/backend/sprico/conditions.py` via storage backend | same service and `routes/conditions.py` | targeted unit tests pass | UI lacks rollback/retire controls. |
| Condition simulation | yes | SQLite `condition_simulations`; audit history | `pyrit/backend/sprico/conditions.py` | same service | targeted unit tests pass | simulation is deterministic/declarative; optional LLM judge disabled by default. |
| Condition approval | yes | condition record plus `condition_approvals` / audit history | `pyrit/backend/sprico/conditions.py` | same service | targeted unit tests pass | no external identity provider. |
| Condition activation | yes | condition record plus audit history | `pyrit/backend/sprico/conditions.py` | same service | targeted unit tests pass | backend enforces activation gates; UI is basic. |
| Condition rollback | yes in backend | condition records, versions, audit history | `pyrit/backend/sprico/conditions.py` | same service | backend route exists; no UI smoke path | UI not implemented. |
| Evidence entries | yes | SQLite `evidence_items` | `pyrit/backend/sprico/evidence_store.py`; Red and garak services also write | `pyrit/backend/routes/evidence.py` | targeted unit tests and smoke tests pass | filter normalization can improve. |
| garak run metadata | yes | SQLite `garak_runs` | `pyrit/backend/sprico/integrations/garak/runner.py` | garak routes | parser/status tests pass; real execution skipped if garak unavailable | optional garak must be installed/configured for real scans. |
| garak artifacts | yes | SQLite `garak_artifacts`; files under `dbdata/garak_scans/{scan_id}` | garak runner | garak routes | parser/artifact tests pass | raw artifact serving is intentionally limited. |
| Red scan results | yes | SQLite `red_scans`, `scans`, `scan_results`, `evidence_items`, `findings` | `pyrit/backend/sprico/red.py` | red routes | targeted unit tests pass | real external/target campaign execution is not product-complete. |
| Shield events | yes for Shield engine evidence | SQLite `shield_events` and `evidence_items` | `pyrit/backend/sprico/evidence_store.py` from Shield service | evidence route and storage backend | targeted unit tests pass | no full event management UI. |
| Policies | yes | SQLite `policies`, `policy_versions`, `audit_history` | `pyrit/backend/sprico/policy_store.py` | policy routes | targeted tests pass | no full RBAC/governance workflow. |
| Projects | yes | SQLite `projects` | `pyrit/backend/sprico/policy_store.py` | project routes | targeted tests pass | no full RBAC/governance workflow. |
| Legal/open-source registry | no user data | fixed registry in code, checked-in `third_party/<tool>/` files | not applicable | `pyrit/backend/sprico/external_engines.py` | targeted tests pass | static/manual registry. |

## 6. User Journey Mapping

### A. Manual Hospital Audit

Intended flow:

`Interactive Audit -> per-turn score -> Evidence -> Findings -> Dashboard`

Current implementation status:

- `Interactive Audit` exists as `chat`.
- Existing scoring and audit workflows remain present.
- Findings and dashboards exist through existing Audit/Dashboard components.
- Evidence Center shows evidence written by Shield, Red, and garak services.
- Direct manual chat-to-`evidence_items` wiring is not confirmed as product-complete from the new evidence page. Manual audit data may still flow through existing audit stores rather than the new SpriCO evidence store.

Status: partial cross-page integration.

### B. Auto Attack Campaign

Intended flow:

`Auto Attacks / Red -> Target -> Attack Engine -> Evidence Engines -> SpriCO PolicyDecisionEngine -> Findings`

Current implementation status:

- Page exists as `Red`.
- Backend executes deterministic mock hospital target scans using `target_id = "mock_hospital_target"`.
- Turns, scores, evidence, scan results, and findings are persisted.
- Attack engine choices are exposed, but full external execution through garak, DeepTeam, promptfoo, or PyRIT campaign runners is not product-complete.
- SpriCO scoring and `PolicyDecisionEngine` remain final authority.

Status: partial, mock target execution functional.

### C. LLM Vulnerability Scanner

Intended flow:

`LLM Vulnerability Scanner -> auto-select garak when available -> garak scanner evidence -> SpriCO final verdict -> Evidence/Findings`

Current implementation status:

- A primary `LLM Vulnerability Scanner` page is not implemented.
- Current page is named `garak Scanner`.
- garak status, plugin listing, scan form, scan history, and evidence/final verdict separation are implemented.
- Auto-selecting garak behind a generic scanner page is not implemented.

Status: scaffold/partial from a product-flow perspective.

### D. garak Advanced Diagnostics

Intended flow:

`Settings/Integrations/garak or Scanners/Advanced Diagnostics/garak -> garak status -> probes/detectors -> optional test scan`

Current implementation status:

- Current separate page is `garak Scanner`.
- It displays status, install hint, plugins, scan form, history, and evidence.
- It can persist unavailable run metadata and real run metadata when optional garak is installed and configured.

Status: functional as diagnostics/adapter page; naming and placement are confusing.

### E. Custom Condition Authoring

Intended flow:

`Custom Conditions -> draft -> simulate -> add positive/negative tests -> approve -> activate -> monitor -> rollback`

Current implementation status:

- Backend lifecycle supports draft, simulate, tests, approve, activate, retire, and rollback.
- Backend activation requires simulation, at least one positive test, at least one negative test, approval, frozen version, and audit history.
- UI supports create, simulate, add tests, approve, and activate.
- UI does not expose rollback or retire controls.
- Monitor state exists as activation state/status metadata but no dedicated monitor workspace is implemented.

Status: backend functional, UI partial.

### F. Open Source License Review

Intended flow:

`Settings -> Open Source Components -> garak/deepteam/promptfoo -> license/source/version`

Current implementation status:

- Page exists as `Open Source Components`.
- Backend uses fixed whitelisted legal registry.
- The page is currently visible directly in the flat left rail, not nested under Settings.

Status: functional, navigation placement should change.

## 7. Clarify garak Page Purpose

| Question | Answer |
| --- | --- |
| Is `garak Scanner` currently a separate page? | yes. View ID is `garak-scanner`. |
| What does it do today? | It displays garak availability/status, install hint, plugin/probe/detector/generator metadata where available, scan form, scan history, and side-by-side scanner evidence versus SpriCO final verdict. |
| Does it run actual garak scans or only show status/config? | It can call the backend scan route. Actual garak execution depends on optional garak installation and valid target/generator setup. Without garak, the route records unavailable evidence/status rather than running a real scan. |
| Does it persist results? | yes, backend scan metadata/evidence can persist in SQLite/JSON fallback and artifacts under `dbdata/garak_scans/{scan_id}`. |
| Should it be renamed? | yes. As a primary product page, `garak Scanner` is too implementation-specific. |
| Should it be moved under Advanced / Integrations? | yes, if kept as a garak-specific page. |
| What should the user-facing scanner page be called? | `LLM Vulnerability Scanner`. |

Recommended product decision:

- The primary user-facing page should be `LLM Vulnerability Scanner`.
- garak should be an engine behind that page.
- A separate garak page, if kept, should be `garak Engine Diagnostics` under Advanced / Integrations.

## 8. Navigation Redesign Proposal

Keep the current `currentView` pattern. Do not introduce React Router.

Recommended grouped navigation:

### Audit Workbench

- Interactive Audit (`chat`)
- Attack History (`history`)
- Audit (`audit`)
- Findings (`findings`)
- Target Configuration (`config`)

### Scanners

- LLM Vulnerability Scanner, new or renamed wrapper around scanner workflow
- Auto Attacks / Red Team Campaigns (`red`)
- garak Engine Diagnostics (`garak-scanner`) under Advanced

### Policies

- Shield (`shield`)
- Policies (`policy`)
- Custom Conditions (`conditions`)
- Evidence Center (`evidence`)

### Dashboards

- Structured Dashboard (`dashboard`)
- Heatmap Dashboard (`heatmap-dashboard`)
- Stability Dashboard (`stability-dashboard`)

### Library

- Benchmark Library (`benchmark-library`)
- Prompt Variants (`prompt-variants`)

### Settings

- Configuration (`config`) if not kept in Audit Workbench
- Target Help (`target-help`)
- Open Source Components (`open-source-components`)
- External Engine Metadata, if promoted from API-only to UI

Compact left rail recommendation:

- Keep only group icons or the most-used top-level views in the compact rail.
- Use a grouped side nav panel or command/menu panel for subpages.
- For this Fluent UI app, a grouped side nav is the least disruptive option because it preserves left-rail muscle memory and the existing `currentView` state model.

Implementation approach without React Router:

- Keep `ViewName` as the source of truth.
- Add a grouped navigation data structure around existing `ViewName` values.
- Preserve every existing `currentView` value.
- Do not remove or rename old view IDs immediately; change display labels first and add aliases only if needed.
- Keep `App.tsx` render switch intact, adding wrappers only where needed.

## 9. Naming Recommendations

| Current name | Recommended user-facing name | Placement |
| --- | --- | --- |
| garak Scanner | LLM Vulnerability Scanner for primary flow; garak Engine Diagnostics for advanced flow | Scanners / Advanced Integrations |
| Red | Auto Attacks or Red Team Campaigns | Scanners |
| Evidence | Evidence Center | Policies or Audit Workbench |
| Custom Conditions | Custom Conditions | Policies |
| Open Source Components | Open Source Components | Settings / Legal |
| Policy | Policies | Policies |
| Shield | Shield | Policies |

## 10. Safety and Scoring Architecture Check

| Requirement | Current code status |
| --- | --- |
| External tools are attack/evidence engines only | true in `pyrit/backend/sprico/external_engines.py` and garak normalization flow. |
| garak does not produce final verdict | true. garak records scanner evidence; SpriCO final verdict is separate. |
| DeepTeam does not produce final verdict | true. It is metadata/status only in this phase. |
| promptfoo does not produce final verdict | true. It is metadata/status only in this phase. |
| OpenAI judge does not produce final verdict | true in the external engine matrix; any judge output is classified as evidence only. |
| SpriCO PolicyDecisionEngine remains final authority | true in policy/scoring services and external engine metadata. |
| Industry-specific logic runs through domain packs | true for hospital privacy scoring and Shield domain signals. |
| Hospital policy checks include authorization context | true. Policy decisions evaluate access context, authorization source, policy mode, purpose/scope metadata, and matched sensitive signals. |

No file was found in this slice that exposes garak, DeepTeam, promptfoo, PyRIT scorer, or OpenAI judge as a final verdict engine.

## 11. Hospital Regression Check

| Regression requirement | Test coverage found |
| --- | --- |
| patient ID + diagnosis strict context => `FAIL/HIGH` | `tests/unit/scoring/test_hospital_privacy_regressions.py::test_patient_id_diagnosis_in_strict_unknown_context_fails_high` |
| patient ID + location follow-up => `FAIL/HIGH` or `FAIL/CRITICAL` | `tests/unit/scoring/test_hospital_privacy_regressions.py::test_contextual_followup_patient_location_never_passes_low` |
| address list disclosure => `FAIL/CRITICAL` | `tests/unit/scoring/test_hospital_privacy_regressions.py::test_patient_address_list_fails_critical` |
| prompt claim `I am doctor/admin/auditor` => `CLAIMED_ONLY` | `tests/unit/scoring/test_policy_decision_engine.py::test_prompt_claimed_doctor_is_claimed_only_not_authorized`; related Shield test: `tests/unit/backend/test_sprico_shield_policy_red.py::test_prompt_claimed_doctor_remains_claimed_only` |
| safe refusal with no PHI leak => `PASS/LOW` | `tests/unit/scoring/test_hospital_privacy_regressions.py::test_safe_medication_refusal_without_phi_leak_passes_low` |
| refusal with PHI leak => not simple `PASS/LOW` | No dedicated named unit test was found in the current inventory. Related policy/scorer behavior exists, and this case was manually replayed during verification, but a dedicated regression test should be added. |

## 12. Known Issues and Recommended Fixes

### Critical

- No current critical route-unavailable, data-loss, or safety/scoring bug was found in the verified slice.

### High

- The left rail is too flat and exposes advanced/legal pages as primary navigation.
- `garak Scanner` is misleading as a primary page name. It should be a generic `LLM Vulnerability Scanner` or moved as `garak Engine Diagnostics`.
- `localhost:3000` can be stale if scheduled tasks or old dev servers are running. Verification on alternate ports showed current code working, but this can confuse testers.
- Red page shows external attack engine choices, but only deterministic mock target execution is product-complete. The UI should make this limitation clearer.

### Medium

- Custom Conditions UI does not expose rollback or retire controls even though backend APIs exist.
- Custom Conditions monitor phase is represented in state but not a full monitoring workspace.
- Manual Interactive Audit to the new Evidence Center is not confirmed as fully wired; evidence currently clearly covers Shield, Red, and garak paths.
- Evidence filter normalization should align `engine`, `engine_id`, and user-facing engine names.
- DeepTeam and promptfoo are metadata/status entries only in this phase.
- Real garak execution remains optional and depends on local installation/configuration.
- A dedicated refusal-with-PHI-leak hospital regression test is missing.

### Low

- Vite build emits `Generated an empty chunk: "react-vendor"`.
- Some UI labels use terse abbreviations such as `Gk`, `Rd`, `Ev`, `Cd`, and `Li`, which increases navigation ambiguity.

## 13. Implementation Plan for Next Phase

Do not implement these items in this report step.

### Phase A

- Reorganize navigation into grouped sections while preserving `currentView`.
- Rename or move `garak Scanner`.
- Create or rename the primary scanner flow as `LLM Vulnerability Scanner`.
- Keep `garak Engine Diagnostics` under Advanced / Integrations.
- Fix any pages that do not load/save from the current grouped flow.
- Add page relationship documentation near the frontend navigation map.

### Phase B

- Complete real optional garak runtime execution paths.
- Add scanner evidence import from real garak artifacts.
- Improve scan result UI for normalized external evidence and SpriCO final verdict.
- Keep garak optional and non-authoritative.

### Phase C

- Add SpriCO AuditSpec / promptfoo-style assertion import/export.
- Keep promptfoo optional and evidence-only.
- Route assertions through SpriCO domain packs and `PolicyDecisionEngine`.

## 14. Final Report Checklist

- [x] all pages inventoried
- [x] all APIs inventoried
- [x] all storage paths identified
- [x] all new pages classified as full/partial/scaffold
- [x] all broken save/load issues listed where found
- [x] navigation redesign proposed
- [x] garak page purpose clarified
- [x] no application code changed
