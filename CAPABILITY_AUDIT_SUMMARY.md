# PyRIT Capability Audit - Summary

## High-level status
All 6 core capabilities are implemented in code and can be demonstrated locally:
- Automated Red Teaming
- Scenario Framework
- CoPyRIT GUI
- Any Target
- Built-in Memory
- Flexible Scoring

## File locations recreated
- CAPABILITY_AUDIT_VERIFIED.md
- CAPABILITY_AUDIT_APPENDICES.md
- CAPABILITY_AUDIT_SUMMARY.md

## Recommended immediate run

1. `pyrit_backend --database InMemory --port 8000`
2. `cd frontend && npm install && npm run dev`
3. `pyrit_shell`

## Notes
- Local `TextTarget` works without API keys.
- OpenAI/HuggingFace/Azure targets require credentials.
- GUI has nearly complete coverage; advanced scenario selection is CLI-only.
