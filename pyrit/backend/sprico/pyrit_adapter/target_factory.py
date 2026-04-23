"""Target factory that resolves SpriCO target configs into runtime objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyrit.backend.services.target_service import get_target_service
from pyrit.backend.sprico.pyrit_adapter.errors import UnsupportedPyRITFeatureError


@dataclass(slots=True)
class MockTarget:
    target_type: str = "MockTarget"
    model_name: str = "mock-model"
    endpoint: str | None = None

    async def send_prompt_async(self, message: Any) -> list[Any]:  # pragma: no cover - utility surface
        return [message]


class PyRITTargetFactory:
    """Build or resolve productized target objects."""

    @staticmethod
    def create(target_config: dict[str, Any]) -> Any:
        service = get_target_service()
        registry_name = str(target_config.get("target_registry_name") or "").strip()
        if registry_name:
            target = service.get_target_object(target_registry_name=registry_name)
            if target is None:
                raise UnsupportedPyRITFeatureError(f"Target '{registry_name}' is not available in the registry.")
            return target

        target_type = str(target_config.get("target_type") or target_config.get("type") or "").strip()
        params = dict(target_config.get("params") or {})
        if target_type == "MockTarget":
            return MockTarget(model_name=str(params.get("model_name") or "mock-model"), endpoint=params.get("endpoint"))

        if target_type:
            raise UnsupportedPyRITFeatureError(
                f"Dynamic target creation for '{target_type}' is not exposed through the adapter yet. "
                "Create the target through SpriCO target management and reference target_registry_name instead."
            )
        raise UnsupportedPyRITFeatureError("Target configuration did not include target_registry_name or a supported target_type.")
