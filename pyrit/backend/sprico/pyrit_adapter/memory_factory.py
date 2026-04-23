"""Memory backend resolver for scan execution."""

from __future__ import annotations

from typing import Any

from pyrit.memory import CentralMemory


class MemoryFactory:
    @staticmethod
    def create(config: dict[str, Any] | None = None) -> Any:
        _ = config or {}
        return CentralMemory.get_memory_instance()
