# PyRIT Code-Verified Capability Audit Report

**Generated:** March 23, 2026
**Repository:** Azure/PyRIT

## EXECUTIVE SUMMARY

6 named capabilities all found in code.

- Automated Red Teaming: implemented
- Scenario Framework: implemented
- CoPyRIT GUI: implemented
- Any Target: implemented
- Built-in Memory: implemented
- Flexible Scoring: implemented

## CAPABILITY 1: AUTOMATED RED TEAMING

### Key files
- `pyrit/executor/attack/core/attack_executor.py` (AttackExecutor, AttackExecutorResult)
- `pyrit/executor/attack/single_turn/` (prompt_sending.py, skeleton_key.py, flip_attack.py, role_play.py, many_shot_jailbreak.py, context_compliance.py)
- `pyrit/executor/attack/multi_turn/` (red_teaming.py, crescendo.py, tree_of_attacks.py, chunked_request.py, multi_prompt_sending.py)

### Main classes
- `AttackExecutor`, `AttackParameters`, `AttackStrategy`
- `PromptSendingAttack`, `SkeletonKeyAttack`, `RolePlayAttack`, `FlipAttack`, `ManyShotJailbreakAttack`, `ContextComplianceAttack`
- `RedTeamingAttack`, `CrescendoAttack`, `TreeOfAttacksWithPruningAttack`, `ChunkedRequestAttack`, `MultiPromptSendingAttack`

### Backend
- Yes, directly implemented.

### Frontend
- `frontend/src/components/Chat/*`, including `ChatWindow.tsx`, `ChatInputArea.tsx`, `MessageList.tsx`, `ConversationPanel.tsx`.

### Runable now
- Yes with CLI `pyrit_shell`, `pyrit_scan`, backend API.

### Config/env
- `PYRIT_CORS_ORIGINS`, `PYRIT_DEV_MODE`, `OPENAI_API_KEY`, `HUGGINGFACE_API_TOKEN`, Azure keys as needed.

### Persistence
- SQLite (`dbdata/pyrit.db` default), Azure SQL (if requested). Memory forms: `pyrit/memory/sqlite_memory.py`, `azure_sql_memory.py`, `memory_models.py`.

### Tests
- `tests/unit/executor/attack/` and integration tests.

### Notes
- GUI lacks some advanced multi-turn tuning but pipeline is coded.

## CAPABILITY 2: SCENARIO FRAMEWORK

### Key files
- `pyrit/scenario/core/scenario.py`, `scenario_strategy.py`
- `pyrit/scenario/scenarios/foundry/red_team_agent.py`
- `pyrit/scenario/scenarios/airt/*` (content_harms.py, cyber.py, jailbreak.py, leakage.py, psychosocial.py, scam.py)
- `pyrit/scenario/scenarios/garak/*`

### Main classes
- `Scenario`, `ScenarioStrategy`, `AtomicAttack`
- `FoundryScenario`, `RedTeamAgent`, `AIRT*Scenario` types

### Backend
- Yes with scenario registry and execution path.

### Frontend
- Partial; history display works; direct scenario selection not in UI (CLI-based).

### Runable now
- yes via `pyrit_scan foundry --initializers text_target` for local.

### Config/env
- standard target and memory environment variables.

### Persistence
- `ScenarioResultEntry`, stored via `CentralMemory` and SQL models.

### Tests
- `tests/unit/scenario/`, integration scenarios.

## CAPABILITY 3: CoPyRIT GUI

### Key files
- Backend: `pyrit/backend/main.py`, `pyrit/backend/routes/*.py`, `pyrit/backend/services/*.py`
- Frontend: `frontend/src/App.tsx`, `frontend/src/components/`, `frontend/src/services/api.ts`, `frontend/src/hooks/*`

### Main components
- API routes: attacks, targets, converters, labels, health, media, version.
- Frontend: `ChatWindow`, `TargetConfig`, `AttackHistory`, `ConnectionBanner`, etc.

### Backend support
- Full FastAPI implementation.

### Frontend support
- Full React UI with attack input, target config, history filters.

### Runable now
- `pyrit_backend` + `cd frontend && npm run dev`.

## CAPABILITY 4: Any Target

### Key files
- `pyrit/prompt_target/` containing: openai, azure_ml, hugging_face, playwright, websocket_copilot, text_target, http_target, prompt_shield, gandalf, crucible, rpc_client.

### Main classes
- `PromptTarget`, `PromptChatTarget`, and target-specific classes.

### Runable now
- `TextTarget` requires no credentials.

## CAPABILITY 5: Built-in Memory

### Key files
- `pyrit/memory/memory_interface.py`, `central_memory.py`, `sqlite_memory.py`, `azure_sql_memory.py`, `memory_models.py`

### Main components
- CentralMemory singleton
- SQLAlchemy ORM models storing prompt history, scores, attack/scenario results

### Tests
- `tests/unit/memory/` etc.

## CAPABILITY 6: Flexible Scoring

### Key files
- `pyrit/score/scorer.py`, `conversation_scorer.py`, `batch_scorer.py`, `true_false/` folder, `video_scorer.py`.

### Main classes
- `Scorer`, `TrueFalseScorer`, `ConversationScorer`, `BatchScorer`, and many implementations.

### Runable now
- Pattern scorers yes; LLM scorers require keys.

---

## SUMMARY

- All 6 capabilities found in code, with backend and partial/full frontend support as documented.
- `CAPABILITY_AUDIT_VERIFIED.md` now recreated.
