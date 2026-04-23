"""Orchestrator mapping for SpriCO scan requests."""

from __future__ import annotations

from typing import Any

from pyrit.backend.sprico.pyrit_adapter.errors import UnsupportedPyRITFeatureError


class OrchestratorFactory:
    """Map SpriCO scan configuration to supported execution modes."""

    @staticmethod
    def create(orchestrator_name: str | None) -> dict[str, Any]:
        name = str(orchestrator_name or "single_turn").strip().lower()
        if name in {"single_turn", "multi_turn", "red_team"}:
            return {"name": name, "mode": name}
        if name.startswith("pyrit:"):
            return {"name": name, "mode": "pyrit_named"}
        raise UnsupportedPyRITFeatureError(f"Unsupported orchestrator '{orchestrator_name}'.")
