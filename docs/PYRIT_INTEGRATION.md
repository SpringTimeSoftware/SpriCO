# PyRIT Integration

## Where PyRIT lives
- Vendored runtime code remains under [`pyrit/`](../pyrit).
- SpriCO-specific adapter code lives under [`pyrit/backend/sprico/pyrit_adapter/`](../pyrit/backend/sprico/pyrit_adapter).
- Domain scoring extensions live under [`scoring/`](../scoring).

## How SpriCO imports PyRIT
- SpriCO routes and services should not import random PyRIT classes directly.
- The adapter layer is the stable integration seam for:
  - target resolution
  - orchestrator mapping
  - converter mapping
  - scorer mapping
  - compatibility discovery

Use:
- `get_pyrit_version_info()`
- `load_compatibility_matrix()`
- `PyRITTargetFactory`
- `PyRITScanRunner`

## Supported features
The authoritative support surface is exposed by:
- `GET /api/pyrit/compatibility`

That matrix describes which features are:
- code present
- backend supported
- API supported
- UI supported
- persisted
- tested

Do not assume full PyRIT feature parity unless the compatibility matrix says so.

## Adding a target
1. Productize the target through the existing SpriCO target registry.
2. Ensure it is restorable through `TargetService`.
3. Add an explicit compatibility-matrix entry.
4. If needed, extend `PyRITTargetFactory`.

## Adding an orchestrator
1. Add a stable mapping in `orchestrator_factory.py`.
2. If the PyRIT orchestrator is optional, fail with a clear unsupported error rather than crashing the app.

## Adding a converter
1. Extend `converter_factory.py`.
2. Keep deterministic conversion traces so audits can replay the exact transformed prompt.

## Adding a scorer
1. Implement a scorer under `scoring/`.
2. Register it through `scoring.registry`.
3. Bridge it in `scorer_factory.py` if it should be available to scan requests.

## Deterministic vs optional LLM scoring
- Deterministic scoring is the default and must work without Azure AI or OpenAI judge configuration.
- Optional judge-model scoring can be layered on later, but deterministic critical privacy rules must still override it.

## Azure AI API requirement
Azure/OpenAI judge scoring is optional. SpriCO’s deterministic policy scoring does not require Azure AI API access.

## Running tests
- `pytest tests/unit/audit/test_hospital_privacy_scoring.py`
- `pytest tests/unit/backend/test_pyrit_compatibility.py`
- `python -m py_compile audit\\scorer.py pyrit\\backend\\routes\\audit.py pyrit\\backend\\sprico\\pyrit_adapter\\compatibility.py`
