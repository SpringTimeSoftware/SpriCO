"""Converter mapping for SpriCO scan requests."""

from __future__ import annotations

import base64
import codecs
from typing import Any

from pyrit.backend.sprico.pyrit_adapter.errors import UnsupportedPyRITFeatureError


class ConverterFactory:
    """Expose deterministic prompt converters without hard-coding them into routes."""

    @staticmethod
    def available() -> list[str]:
        return ["no_op", "base64", "rot13", "custom_prompt_wrapper"]

    @staticmethod
    def build(converter_config: dict[str, Any]) -> dict[str, Any]:
        name = str(converter_config.get("name") or "no_op").strip().lower()
        config = dict(converter_config.get("config") or {})
        if name in {"no_op", "base64", "rot13", "custom_prompt_wrapper"}:
            return {"name": name, "config": config}
        raise UnsupportedPyRITFeatureError(f"Unsupported converter '{name}'.")

    @staticmethod
    def apply(prompt: str, converter_chain: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        current = prompt
        traces: list[dict[str, Any]] = []
        for item in converter_chain:
            name = item["name"]
            config = item.get("config") or {}
            if name == "no_op":
                transformed = current
            elif name == "base64":
                transformed = base64.b64encode(current.encode("utf-8")).decode("ascii")
            elif name == "rot13":
                transformed = codecs.encode(current, "rot_13")
            elif name == "custom_prompt_wrapper":
                prefix = str(config.get("prefix") or "")
                suffix = str(config.get("suffix") or "")
                transformed = f"{prefix}{current}{suffix}"
            else:  # pragma: no cover - guarded by build()
                raise UnsupportedPyRITFeatureError(f"Unsupported converter '{name}'.")
            traces.append({"name": name, "input_length": len(current), "output_length": len(transformed)})
            current = transformed
        return current, traces
