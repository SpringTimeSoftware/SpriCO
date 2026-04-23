"""Dynamic garak plugin discovery."""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from pyrit.backend.sprico.integrations.garak.version import get_garak_version_info

PLUGIN_CATEGORIES = ("probes", "detectors", "generators", "buffs")
_PLUGIN_TOKEN_RE = re.compile(r"\b[a-zA-Z_][\w]*\.[a-zA-Z_][\w.*-]*\b")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def discover_plugins(timeout_seconds: int = 30) -> dict[str, Any]:
    """Discover installed garak plugins with CLI fallback and no hardcoded final list."""

    version_info = get_garak_version_info()
    if not version_info.get("available"):
        return {
            "available": False,
            "version_info": version_info,
            "plugins": {category: [] for category in PLUGIN_CATEGORIES},
            "errors": {"garak": version_info.get("error")},
        }

    plugins: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    for category in PLUGIN_CATEGORIES:
        try:
            discovered = _discover_category_cli(category=category, timeout_seconds=timeout_seconds)
            plugins[category] = discovered
        except Exception as exc:  # pragma: no cover - depends on installed garak shape
            plugins[category] = []
            errors[category] = str(exc)

    return {
        "available": True,
        "version_info": version_info,
        "plugins": plugins,
        "errors": errors,
    }


def _discover_category_cli(*, category: str, timeout_seconds: int) -> list[str]:
    command = [sys.executable, "-m", "garak", f"--list_{category}"]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    if completed.returncode != 0 and not output.strip():
        raise RuntimeError(f"garak list command failed for {category} with exit code {completed.returncode}")
    return _parse_plugin_listing(output)


def _parse_plugin_listing(output: str) -> list[str]:
    plugins: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        stripped = _ANSI_RE.sub("", line).strip()
        if not stripped or stripped.startswith(("#", "[", "{")):
            continue
        for token in _PLUGIN_TOKEN_RE.findall(stripped):
            normalized = token.strip(" ,;:")
            if normalized.lower() in {"github.com"}:
                continue
            for prefix in ("probes.", "detectors.", "generators.", "buffs."):
                if normalized.startswith(prefix):
                    normalized = normalized[len(prefix):]
                    break
            if normalized in seen:
                continue
            seen.add(normalized)
            plugins.append(normalized)
    return plugins
