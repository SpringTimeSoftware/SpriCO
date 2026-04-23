# SpriCO garak Adapter

This adapter treats garak as scanner evidence, not as SpriCO's final verdict engine.

Flow:

1. Discover installed garak version and plugins dynamically.
2. Run garak through CLI fallback in an isolated scan directory.
3. Persist stdout, stderr, config, command, JSONL/hitlog/HTML artifacts.
4. Parse raw artifacts into `RawScannerFinding`.
5. Normalize findings into `SensitiveSignal`.
6. Call `PolicyDecisionEngine` for the final SpriCO verdict.

If garak is absent, status and plugin endpoints return an unavailable response instead of crashing the app.
