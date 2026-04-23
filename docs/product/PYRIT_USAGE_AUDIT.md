# PyRIT Usage Audit

Generated: 2026-04-21

This report audits how the current SpriCO repository uses PyRIT. It separates two things that are easy to confuse:

- The repository contains the PyRIT source tree under `pyrit/`. That is copied/vendored PyRIT code and includes many internal PyRIT imports, tests, targets, converters, memory classes, scorers, scenarios, datasets, and CLI entry points.
- SpriCO product flows only invoke a smaller subset of PyRIT runtime objects.

The inventory below is based on repository code inspection using `rg` searches for `from pyrit`, `import pyrit`, `PromptNormalizer`, `CentralMemory`, `TargetRegistry`, `PromptTarget`, `AttackResult`, `PromptConverter`, `Scorer`, `Dataset`, and SpriCO UI/API calls.

## Executive Summary

SpriCO is not currently "deeply PyRIT-powered" across every new product area. It genuinely uses PyRIT for:

- configured target creation, persistence, activation, and runtime lookup through `TargetRegistry` and `PromptTarget` objects;
- interactive/manual audit message sending through `PromptNormalizer`;
- attack history and conversation storage through `CentralMemory`, `AttackResult`, `Message`, and `MessagePiece`;
- structured audit execution by creating PyRIT-backed attack sessions and sending prompts through `AttackService`;
- converter registry and converter execution when converter IDs are supplied to attack messages;
- media persistence and serving for PyRIT memory artifacts.

The newer SpriCO pages use PyRIT unevenly:

- Red Team Campaigns does not currently run PyRIT orchestrators. Its mock path is SpriCO-native. Its real-target path sends HTTP directly through `urllib.request`, even when the UI engine value is `pyrit`.
- LLM Vulnerability Scanner is a garak scanner workflow. It validates selected targets through the shared target registry, but the scan execution path is garak-specific, not a PyRIT orchestrator/scenario path.
- SpriCO scoring uses native deterministic scoring and policy logic, not PyRIT scorers as final verdict engines.
- Evidence persistence uses `SpriCOEvidenceStore`, not PyRIT memory as the evidence store.

## Copied / Vendored PyRIT Code

| Path | What It Contains | Runtime Used By SpriCO |
|---|---|---|
| `pyrit/` | PyRIT package source, including targets, converters, memory, scorers, scenario/executor code, datasets, CLI, analytics, embeddings, UI/RPC, and tests support. | Partially. SpriCO product flows use target, converter, prompt normalizer, memory, model, identifier, and path pieces. Most PyRIT executor/scenario/dataset/scorer surfaces are present but not wired into SpriCO runtime workflows. |
| `tests/unit/target`, `tests/unit/converter`, `tests/unit/score`, `tests/unit/executor`, `tests/unit/scenarios`, `tests/integration/*` | PyRIT core tests and integration tests. | Test-only. These prove PyRIT package capabilities, not necessarily SpriCO feature wiring. |
| `build_scripts/evaluate_scorers.py` | Uses PyRIT scorer/target initializers and scorer registry for scorer evaluation scripts. | Script-only, not UI/API runtime. |

## Runtime Flow Map

| SpriCO Feature | Frontend Page | API Calls | PyRIT Runtime Objects Invoked | Status |
|---|---|---|---|---|
| Interactive Audit | `frontend/src/components/Chat/ChatWindow.tsx` | `/api/attacks`, `/api/attacks/{id}/messages`, `/api/audit/interactive/attacks/{id}` | `AttackService`, `TargetService`, `PromptNormalizer`, `PromptConverterConfiguration`, `CentralMemory`, `AttackResult`, `Message`, `MessagePiece` | Active PyRIT runtime use |
| Attack History | `frontend/src/components/History/AttackHistory.tsx` | `/api/attacks`, `/api/attacks/attack-options`, `/api/attacks/converter-options`, `/api/labels` | `CentralMemory.get_attack_results`, `get_unique_attack_class_names`, `get_unique_converter_class_names`, `get_unique_attack_labels` | Active PyRIT memory use |
| Configuration / Targets | `frontend/src/components/Config/TargetConfig.tsx` | `/api/targets`, `/api/targets/active`, `/api/targets/{id}/activate`, `/api/targets/{id}/config`, `/api/targets/{id}/archive` | `TargetRegistry`, `PromptTarget`, target classes from `pyrit.prompt_target`, `PersistentTargetStore` | Active PyRIT target use |
| Structured Audit Runs | `frontend/src/components/Audit/AuditPage.tsx` | `/api/audit/run`, `/api/audit/runs`, `/api/audit/results/{id}` | `AuditExecutor` creates attacks and sends turns through `AttackService` and PyRIT targets/memory | Active PyRIT target/memory use, SpriCO-native scoring |
| Benchmark Replay | `frontend/src/components/Audit/BenchmarkLibraryPage.tsx` | `/api/benchmarks/scenarios/{id}/replay` | `AuditExecutor` via `AttackService` | Active PyRIT target/memory use for replay execution |
| LLM Vulnerability Scanner | `frontend/src/components/SpriCO/GarakScannerPage.tsx` | `/api/garak/status`, `/api/integrations/garak/plugins`, `/api/scans/garak` | `TargetService` only for target config validation; garak runner handles scan execution | Partial PyRIT use. Not PyRIT scan/orchestrator-powered |
| Red Team Campaigns | `frontend/src/components/SpriCO/RedPage.tsx` | `/api/red/objectives`, `/api/red/scans` | `TargetService` only for real-target config validation. Real execution uses raw HTTP, not PyRIT target send methods | Partial. Red does not currently invoke PyRIT orchestrators or targets for execution |
| Evidence Center | `frontend/src/components/SpriCO/EvidencePage.tsx` | `/api/evidence` | None for persistence; `DB_DATA_PATH` path only | SpriCO-native evidence store |
| Shield | `frontend/src/components/SpriCO/ShieldPage.tsx` | `/api/shield/check` | None directly. Uses SpriCO policy/evidence stores | SpriCO-native |
| Policies / Projects / Conditions | `frontend/src/components/SpriCO/*` | `/api/policies`, `/api/projects`, `/api/conditions` | None directly, aside from shared path/storage imports | SpriCO-native |

## Detailed Usage Inventory

| File Path | Imported Module / Class / Function | Runtime Used | Page / API That Calls It | Category | Status | Red Uses It | LLM Scanner Uses It | Interactive Audit Uses It | Scoring Uses It | Evidence Persistence Uses It |
|---|---|---:|---|---|---|---:|---:|---:|---:|---:|
| `pyrit/backend/main.py` | `import pyrit`; `CentralMemory`; `SQLiteMemory`; `get_target_service` | Yes | Backend startup, all APIs | Utility, memory, target | Active | Indirect | Indirect | Indirect | No | Indirect |
| `pyrit/backend/services/target_service.py` | `pyrit.prompt_target`; `PromptTarget`; `TargetRegistry` | Yes | `/api/targets`, audit, scanner validation, Red validation | Target | Active | Validation only | Validation only | Yes | No | No |
| `pyrit/backend/services/persistent_target_store.py` | `DB_DATA_PATH`; backend target model constants | Yes | `/api/targets` | Target persistence utility | Active | Indirect | Indirect | Indirect | No | No |
| `pyrit/backend/mappers/target_mappers.py` | `PromptTarget` | Yes | `/api/targets` responses | Target utility | Active | Indirect | Indirect | Indirect | No | No |
| `pyrit/backend/routes/targets.py` | `get_target_service`; target DTOs | Yes | Target Configuration page, unified target selectors | Target API | Active | Validation/source list | Source list | Active target selection | No | No |
| `pyrit/backend/services/converter_service.py` | `pyrit.prompt_converter`; `PromptConverter`; `PromptDataType`; `ConverterRegistry` | Yes when converter API or converter IDs are used | `/api/converters`, attack message converter IDs | Converter | Partial active | No | No | Optional per-message | No | No |
| `pyrit/backend/mappers/converter_mappers.py` | `PromptConverter` | Yes | `/api/converters` | Converter utility | Partial active | No | No | Optional | No | No |
| `pyrit/backend/routes/converters.py` | `get_converter_service`; converter DTOs | Yes | Converter API; not a primary currentView page | Converter API | Partial active | No | No | Optional | No | No |
| `pyrit/backend/services/attack_service.py` | `ComponentIdentifier`; `build_atomic_attack_identifier`; `CentralMemory`; `AttackResult`; `AttackOutcome`; `ConversationStats`; `ConversationType`; `MessagePiece`; `PromptDataType`; `data_serializer_factory`; `PromptConverterConfiguration`; `PromptNormalizer` | Yes | `/api/attacks`; Interactive Audit; Structured Audit via `AuditExecutor` | Target, converter, memory, utility | Active | No | No | Yes | No | No |
| `pyrit/backend/mappers/attack_mappers.py` | `AttackResult`; `ChatMessageRole`; `PromptDataType`; `PyritMessage`; `PyritMessagePiece`; `PyritScore` | Yes | `/api/attacks` responses and requests | Memory/model/utility | Active | No | No | Yes | No | No |
| `pyrit/backend/routes/attacks.py` | `get_attack_service`; attack DTOs | Yes | Interactive Audit and Attack History | Attack/session API | Active | No | No | Yes | No | No |
| `audit/executor.py` | `AddMessageRequest`; `CreateAttackRequest`; `MessagePieceRequest`; `get_attack_service`; `get_target_service` | Yes | `/api/audit/run`, benchmark replay, prompt variants | Orchestration wrapper over PyRIT attack service | Active | No | No | Related through saved interactive audit | Uses SpriCO scorer after response | No |
| `audit/database.py` | `DB_DATA_PATH` | Yes | Audit, dashboards, benchmark library | Persistence utility | Active | No | No | Indirect for saved audit | Stores SpriCO audit results | No |
| `pyrit/backend/routes/audit.py` | `get_attack_service`; `get_target_service`; `SpriCOEvidenceStore` | Yes | Audit pages, dashboards, interactive audit scoring | Audit API, target, memory, evidence bridge | Active | No | No | Yes | SpriCO-native scoring | Yes, for normalized interactive evidence |
| `pyrit/backend/routes/labels.py` | `CentralMemory` | Yes | Attack History filters | Memory utility | Active | No | No | Indirect | No | No |
| `pyrit/backend/routes/media.py` | `CentralMemory` | Yes | Message media display/download | Memory/media utility | Active | No | No | Yes for media messages | No | No |
| `pyrit/backend/routes/version.py` | `import pyrit`; `CentralMemory` | Yes | App startup/version banner | Utility, memory diagnostics | Active | No | No | No | No | No |
| `pyrit/backend/sprico/evidence_store.py` | `DB_DATA_PATH`; SpriCO storage backend | Yes | `/api/evidence`; Shield, Red, garak, interactive evidence | Evidence persistence | Active, SpriCO-native | Yes | Yes for garak evidence | Yes for normalized scoring evidence | Consumes final score fields | Yes |
| `pyrit/backend/routes/evidence.py` | `SpriCOEvidenceStore` | Yes | Evidence Center | Evidence API | Active | Reads persisted Red evidence | Reads persisted scanner evidence | Reads interactive evidence | No | Yes |
| `pyrit/backend/sprico/red.py` | `DB_DATA_PATH`; `SpriCOEvidenceStore`; `SpriCOPolicyStore`; storage backends | Yes | `/api/red/scans` | Red campaign, evidence, policy | Active SpriCO-native | Yes | No | No | SpriCO-native `evaluate_response` | Yes |
| `pyrit/backend/routes/red.py` | `get_target_service`; `SpriCORedStore` | Yes | Red Team Campaigns | Red API, target validation | Active, but not PyRIT execution | Yes, validation only for real target | No | No | No | Indirect |
| `pyrit/backend/routes/garak.py` | `GarakScanRunner`; `get_garak_version_info`; `discover_plugins`; `get_target_service` | Yes | LLM Vulnerability Scanner | Scanner API, target validation | Active garak path, not PyRIT scan path | No | Yes, validation only | No | No | Indirect through runner |
| `pyrit/backend/sprico/integrations/garak/runner.py` | garak config/parser/normalizer/version; `SpriCOEvidenceStore`; `DB_DATA_PATH` | Yes when garak scans run | `/api/scans/garak` | External scanner/evidence | Active optional scanner path | No | Yes | No | SpriCO final verdict generated separately | Yes |
| `pyrit/backend/sprico/external_engines.py` | garak version info; static engine metadata | Yes | `/api/external-engines`, legal metadata | Utility/metadata | Active metadata | UI metadata only | UI metadata only | No | No | No |
| `pyrit/backend/sprico/pyrit_adapter/target_factory.py` | `get_target_service`; adapter error | Not called by current pages/routes except possible direct imports/tests | Target adapter | Code-only/partial | Partial | No | No | No | No | No |
| `pyrit/backend/sprico/pyrit_adapter/converter_factory.py` | Adapter error; local deterministic conversions | Not wired to product routes | Converter adapter | Code-only/partial | Partial | No | No | No | No | No |
| `pyrit/backend/sprico/pyrit_adapter/scorer_factory.py` | SpriCO scorer registry, adapter error | Not wired to product routes | Scorer adapter | Code-only/partial | Partial | No | No | No | SpriCO scorer only if runner used | No |
| `pyrit/backend/sprico/pyrit_adapter/orchestrator_factory.py` | Adapter error | Not wired to product routes | Orchestrator metadata adapter | Code-only/partial | Partial | No | No | No | No | No |
| `pyrit/backend/sprico/pyrit_adapter/dataset_factory.py` | None from PyRIT core | Not wired to product routes | Dataset placeholder | Code-only | No | No | No | No | No | No |
| `pyrit/backend/sprico/pyrit_adapter/memory_factory.py` | `CentralMemory` | Not wired to product routes | Memory adapter | Code-only/partial | No | No | No | No | No | No |
| `pyrit/backend/sprico/pyrit_adapter/runner.py` | Adapter factories; result normalizer | Not exposed by current UI/API | Generic scan runner placeholder | Code-only/partial | No | No | No | Uses SpriCO scorers if manually invoked | No |
| `pyrit/backend/sprico/pyrit_adapter/compatibility.py` | `importlib.import_module("pyrit")`; compatibility registry | Yes | `/api/pyrit/compatibility` | Utility/metadata | Active metadata | No | No | No | No | No |
| `pyrit/backend/routes/pyrit_compatibility.py` | `load_compatibility_matrix` | Yes | `/api/pyrit/compatibility` | Metadata API | Active metadata | No | No | No | No | No |
| `build_scripts/evaluate_scorers.py` | `ScorerRegistry`; `initialize_pyrit_async`; `ScorerInitializer`; `TargetInitializer` | Script-only | Manual build/eval script | Scorer utility | Not app runtime | No | No | No | Script-only | No |
| `tests/unit/backend/test_attack_service.py` | `ComponentIdentifier`; `AttackOutcome`; `AttackResult`; `ConversationStats`; patches `PromptNormalizer`, `CentralMemory`, `data_serializer_factory` | Test-only | Backend unit tests | Memory/attack/target/converter | Tests exist | No | No | Yes tests | No | No |
| `tests/unit/backend/test_target_service.py` | `TargetRegistry`; `ComponentIdentifier` | Test-only | Backend unit tests | Target | Tests exist | Indirect | Indirect | Yes target tests | No | No |
| `tests/unit/backend/test_converter_service.py` | `prompt_converter`; `PromptConverter`; `ConverterRegistry` | Test-only | Backend unit tests | Converter | Tests exist | No | No | Optional converter tests | No | No |
| `tests/unit/backend/test_pyrit_compatibility.py` | `load_compatibility_matrix`; `get_pyrit_version_info` | Test-only | Backend unit tests | Metadata | Tests exist | No | No | No | No | No |
| `tests/integration/ai_recruiter/test_ai_recruiter.py` | `XPIATestWorkflow`; `PDFConverter`; `PromptConverterConfiguration`; `HTTPXAPITarget`; `OpenAIChatTarget`; `SelfAskTrueFalseScorer`; `initialize_pyrit_async` | Test-only/integration | Not a SpriCO page/API | Workflow, target, converter, scorer | PyRIT example/integration, not product runtime | No | No | No | PyRIT scorer in test only | No |
| `tests/end_to_end/test_scenarios.py` | `pyrit.cli.pyrit_scan`; `ScenarioRegistry` | Test-only | CLI scenario tests | Scenario/dataset/orchestrator | PyRIT CLI test, not SpriCO UI runtime | No | No | No | No | No |

## Frontend Use of PyRIT-Backed APIs

These frontend files do not import Python PyRIT modules, but they call APIs backed by PyRIT runtime objects.

| Frontend File | APIs Called | Actual PyRIT Runtime Behind API | Status |
|---|---|---|---|
| `frontend/src/components/Chat/ChatWindow.tsx` | `attacksApi.createAttack`, `attacksApi.addMessage`, `attacksApi.getMessages`, `auditApi.getInteractiveAudit` | `AttackService`, `PromptNormalizer`, `CentralMemory`, target registry | Active |
| `frontend/src/components/History/AttackHistory.tsx` | `attacksApi.listAttacks`, `getAttackOptions`, `getConverterOptions`, `labelsApi.getLabels` | `CentralMemory` and PyRIT `AttackResult` records | Active |
| `frontend/src/components/Config/TargetConfig.tsx` | `targetsApi.listTargets`, `activateTarget`, `getTargetConfig`, `archiveTarget` | `TargetRegistry`, `PromptTarget` instances, target persistence | Active |
| `frontend/src/components/Audit/AuditPage.tsx` | `auditApi.createRun`, `listRuns`, `getStatus`, `getFindings` | `AuditExecutor` through `AttackService` and PyRIT targets/memory | Active |
| `frontend/src/components/Audit/BenchmarkLibraryPage.tsx` | benchmark replay APIs | `AuditExecutor` through `AttackService` for replay execution | Active for replay |
| `frontend/src/components/SpriCO/GarakScannerPage.tsx` | garak status/plugin/scan APIs | Shared target registry validation only; garak runner for execution | Partial PyRIT use |
| `frontend/src/components/SpriCO/RedPage.tsx` | Red objective/scan APIs | Shared target registry validation only for real target; raw HTTP execution | Partial PyRIT use |
| `frontend/src/components/SpriCO/EvidencePage.tsx` | `/api/evidence` | SpriCO evidence store, not PyRIT memory | No PyRIT runtime |

## Feature Matrix

| PyRIT Feature | Code Present | Runtime Used | UI Exposed | API Exposed | Evidence Persisted | Tests Exist | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Targets | Yes | Yes | Yes | Yes | Partial, via target metadata on audit/evidence records | Yes | Active |
| Orchestrators | Yes in PyRIT core; adapter metadata exists | No for SpriCO product flows | No | Metadata only through compatibility; no product scan route uses orchestrators | No | PyRIT core tests exist | Code-only / unused by SpriCO |
| Converters | Yes | Yes when converter IDs are used; preview API executes converters | Limited | Yes, `/api/converters`; attack messages accept converter IDs | Indirect in attack metadata, not normalized evidence | Yes | Partial active |
| Scorers | Yes in PyRIT core; SpriCO scorer adapter exists | PyRIT scorers are not used for SpriCO final verdicts; SpriCO deterministic scorers are used | Mentioned as evidence source if wired | Compatibility/metadata; SpriCO scoring routes | SpriCO score outputs persisted, not PyRIT scorer evidence by default | Yes for PyRIT core and SpriCO scoring | Partial / SpriCO-native active |
| Memory | Yes | Yes | Attack History, Interactive Audit | Yes through `/api/attacks`, `/api/labels`, `/api/media`, `/api/version` | No as Evidence Center store; yes as attack/conversation store | Yes | Active |
| Datasets | Yes in PyRIT core | No in SpriCO product flows | Benchmark Library is SpriCO SQLite, not PyRIT dataset runtime | Benchmark APIs are SpriCO-native | No | PyRIT dataset tests exist | Code-only / unused by SpriCO |
| Attack objectives | Yes in PyRIT core; SpriCO Red has native objectives | SpriCO Red uses native `BASELINE_OBJECTIVES` and `DOMAIN_OBJECTIVES`, not PyRIT scenario objectives | Yes in Red Team Campaigns | Yes, `/api/red/objectives` | Yes for Red results | Yes for SpriCO Red | Partial, SpriCO-native active |
| Multi-turn attacks | Yes in PyRIT core | Manual/structured multi-turn uses repeated `AttackService.add_message_async`; no PyRIT multi-turn attack strategy is invoked | Yes through Interactive Audit and Audit Runs | Yes through attack and audit APIs | Interactive evidence can persist scored turns | Yes | Partial active |
| Adaptive attacks | Yes in PyRIT core tests/executors | No SpriCO product path currently invokes adaptive PyRIT strategies | No | No product API | No | PyRIT core tests exist | Unused by SpriCO |

## Usage by Product Area

### Interactive Audit

Interactive Audit genuinely uses PyRIT runtime objects.

Code path:

1. `frontend/src/components/Chat/ChatWindow.tsx` calls `attacksApi.createAttack`.
2. `/api/attacks` calls `AttackService.create_attack_async`.
3. `AttackService` creates an `AttackResult`, builds a `ComponentIdentifier`, and stores it in `CentralMemory`.
4. `ChatWindow.tsx` calls `attacksApi.addMessage`.
5. `AttackService._send_and_store_message_async` resolves the configured target from `TargetService`, converts the request DTO into PyRIT `Message` / `MessagePiece`, optionally resolves `PromptConverterConfiguration`, then calls `PromptNormalizer().send_prompt_async(...)`.
6. `PromptNormalizer` sends to the PyRIT `PromptTarget` and stores request and response in PyRIT memory.
7. `frontend/src/components/Chat/ChatWindow.tsx` calls `auditApi.getInteractiveAudit` to produce SpriCO scoring and normalized evidence metadata.

This is active PyRIT usage.

### Structured Audit

Structured Audit uses PyRIT targets and memory, but not PyRIT orchestrators or scorers.

Code path:

1. `frontend/src/components/Audit/AuditPage.tsx` calls `auditApi.createRun`.
2. `/api/audit/run` creates an audit run in `AuditDatabase`.
3. `AuditExecutor.execute_run` iterates tests.
4. `AuditExecutor._execute_single_test` creates a PyRIT-backed attack via `AttackService.create_attack_async`.
5. It sends each prompt step through `AttackService.add_message_async`, which invokes `PromptNormalizer` and the configured PyRIT target.
6. The final response is scored with `audit.scorer.evaluate_response`, which is SpriCO-native.

This is active PyRIT target/memory use with SpriCO-native scoring.

### Red Team Campaigns

Red Team Campaigns currently does not genuinely execute PyRIT runtime objects for attacks.

Code path:

- `frontend/src/components/SpriCO/RedPage.tsx` exposes attack engine option `pyrit`.
- `/api/red/scans` validates target configuration through `get_target_service()`.
- `SpriCORedStore.create_scan` runs either `_execute_mock_scan` or `_execute_real_target_scan`.
- `_execute_mock_scan` uses built-in deterministic scenarios and `audit.scorer.evaluate_response`.
- `_execute_real_target_scan` uses `_send_http_prompt`, which posts JSON to the target endpoint using `urllib.request`.

Because `_execute_real_target_scan` does not resolve the PyRIT target object or call `PromptNormalizer`, `PromptTarget.send_prompt_async`, or any PyRIT orchestrator, the `pyrit` engine label is currently partial/misleading from a runtime perspective. It means "supported SpriCO/PyRIT target path" in validation language, not actual PyRIT attack execution.

### LLM Vulnerability Scanner

LLM Vulnerability Scanner is garak-first, not PyRIT-powered.

Code path:

- `frontend/src/components/SpriCO/GarakScannerPage.tsx` calls garak APIs.
- `/api/scans/garak` validates `target_id` with `TargetService.get_target_config_async`.
- `GarakScanRunner` constructs and runs garak when installed/configured, parses garak artifacts, normalizes scanner evidence, and persists evidence.

The scanner uses the shared SpriCO target registry, but it does not invoke PyRIT scan runners, scenarios, orchestrators, or scorers.

### Scoring

SpriCO scoring is native.

Relevant files:

- `audit/scorer.py`
- `scoring/registry.py`
- `scoring/packs/hospital_privacy/scorer.py`
- `pyrit/backend/routes/scoring.py`
- `pyrit/backend/sprico/red.py`
- `pyrit/backend/routes/audit.py`

PyRIT scorer code exists in the repo and PyRIT scorer tests exist, but SpriCO final verdicts are produced by SpriCO deterministic scoring and policy logic. External or PyRIT scorer outputs are not wired as final verdict authorities.

### Evidence Persistence

Evidence Center persistence is SpriCO-native.

Relevant files:

- `pyrit/backend/sprico/evidence_store.py`
- `pyrit/backend/routes/evidence.py`
- `pyrit/backend/sprico/red.py`
- `pyrit/backend/sprico/integrations/garak/runner.py`
- `pyrit/backend/routes/audit.py`
- `pyrit/backend/sprico/shield.py`

PyRIT memory stores attack sessions and messages. Evidence Center stores normalized audit/scanner/Shield/Red evidence separately through `SpriCOEvidenceStore`.

## Active, Partial, and Dead-Code Classification

### Active

- `TargetService` / `TargetRegistry` / `PromptTarget`
- `AttackService` / `CentralMemory` / `AttackResult`
- `PromptNormalizer` prompt sending
- PyRIT DTO mapping for attack messages and summaries
- media storage/serving through PyRIT memory results path
- structured audit execution through `AttackService`
- target configuration and archive/active target flows

### Partial

- Converter APIs and converter runtime: implemented and usable, but not strongly surfaced as a first-class currentView page.
- PyRIT compatibility API: metadata only.
- PyRIT adapter under `pyrit/backend/sprico/pyrit_adapter`: useful scaffolding, but not wired to current scanner/Red workflows.
- Red Team Campaigns `pyrit` engine option: exposed in UI/backend allowlist, but does not invoke PyRIT execution objects.
- PyRIT scorer evidence: represented in external engine metadata/UI language, but not a live evidence-producing path for SpriCO final verdicts.

### Code-Only / Unused by SpriCO Product Runtime

- PyRIT orchestrator/executor strategies as product flows.
- PyRIT scenario/dataset runtime as product flows.
- PyRIT adaptive attack strategies.
- `PyRITScanRunner` generic adapter route usage. The runner exists, but no current page/API calls it directly.

## Important Non-Claims

The current code does not support these claims:

- "Red Team Campaigns is powered by PyRIT orchestrators." It is not.
- "LLM Vulnerability Scanner is powered by PyRIT." It is garak-backed and uses PyRIT only for target registry validation.
- "SpriCO final verdicts are PyRIT scorer verdicts." They are not.
- "Evidence Center persists PyRIT memory as evidence." It persists SpriCO-normalized evidence separately.
- "PyRIT datasets power Benchmark Library." Benchmark Library uses `AuditDatabase` and SpriCO benchmark tables.

## Answers

### 1. Is SpriCO currently deeply using PyRIT?

No. SpriCO currently uses PyRIT deeply for the original interactive/manual attack substrate: targets, prompt normalization, attack sessions, memory, message models, media handling, and structured audit execution through the attack service.

It does not deeply use PyRIT for the newer external-engine scanner, Red Team Campaigns, custom conditions, policy, Shield, or Evidence Center workflows. Those are mostly SpriCO-native workflows layered beside the PyRIT-backed attack substrate.

### 2. Which SpriCO features genuinely use PyRIT?

Genuine PyRIT runtime usage exists in:

- Interactive Audit
- Attack History
- Target Configuration / Active Target selection
- Structured Audit Runs
- Benchmark replay execution
- Prompt Variants when they create replay runs
- media display for PyRIT-stored message artifacts
- converter APIs and attack-time converter IDs when used

### 3. Which PyRIT capabilities are present but not wired?

Present but not product-wired:

- PyRIT orchestrators and attack strategies
- PyRIT adaptive attacks
- PyRIT scenario/dataset execution
- PyRIT scorer execution as evidence
- PyRIT multi-turn strategy objects
- `PyRITScanRunner` generic adapter
- dataset factory and orchestrator factory under `pyrit/backend/sprico/pyrit_adapter`

Partially wired:

- converters
- compatibility metadata
- shared target registry for scanner/Red validation

### 4. What should be implemented next to make SpriCO truly PyRIT-powered?

1. Replace the Red Team Campaigns `pyrit` engine label with a real PyRIT execution path.
   - Resolve configured targets through `TargetService.get_target_object`.
   - Use PyRIT `PromptNormalizer` or PyRIT attack strategy objects, not raw `urllib.request`.
   - Persist PyRIT-generated turns as SpriCO evidence.

2. Add a product scan route around `PyRITScanRunner` or a better typed successor.
   - Expose only allowlisted orchestrators, converters, datasets, and scorers.
   - Normalize results into `SpriCOEvidenceStore`.
   - Keep SpriCO `PolicyDecisionEngine` as the final verdict authority.

3. Wire PyRIT datasets/scenarios into Benchmark Library as optional import/run sources.
   - Keep SpriCO `AuditDatabase` as product persistence.
   - Store source dataset metadata and license/source where relevant.

4. Turn PyRIT scorers into evidence engines only.
   - Record scorer class, score value, rationale, target, scan ID, and raw result.
   - Do not allow PyRIT scorer output to override final SpriCO verdict.

5. Add UI clarity for PyRIT-powered modes.
   - "Attack Engine: PyRIT" should only be selectable when the backend route actually invokes PyRIT runtime.
   - If the path is SpriCO-native, label it "SpriCO native".

6. Add regression tests that prove real PyRIT object invocation.
   - Patch/assert `PromptNormalizer.send_prompt_async` for interactive and structured audit.
   - Add Red tests that fail unless the PyRIT mode invokes a PyRIT target or attack strategy.
   - Add tests that Evidence Center records include PyRIT source metadata when PyRIT evidence engines are used.

## Audit Checklist

- PyRIT source tree identified: yes.
- Product-facing PyRIT imports inventoried: yes.
- Runtime use separated from code-only presence: yes.
- Red Team Campaigns PyRIT status classified: partial, not genuine PyRIT execution.
- LLM Vulnerability Scanner PyRIT status classified: target validation only, garak execution path.
- Interactive Audit PyRIT status classified: active genuine runtime use.
- SpriCO scoring classified: SpriCO-native, not PyRIT final verdict.
- Evidence persistence classified: SpriCO-native, not PyRIT memory.
- Feature matrix included: yes.
- No code changed: yes; this is a documentation-only report.
