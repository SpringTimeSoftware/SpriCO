"""Dataset resolver placeholder for future scan datasets."""

from __future__ import annotations

from typing import Any


class DatasetFactory:
    @staticmethod
    def create(dataset_id: str | None, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "dataset_id": dataset_id,
            "config": config or {},
            "resolved": dataset_id is not None,
        }
