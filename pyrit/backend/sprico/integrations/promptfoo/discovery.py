"""Promptfoo executable discovery and optional runtime status."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from functools import lru_cache
from typing import Any

PROMPTFOO_INSTALL_HINT = (
    "Install promptfoo with npm, add it to PATH, or set SPRICO_PROMPTFOO_EXECUTABLE. "
    "SpriCO also supports local workspace installs via npx --no-install promptfoo."
)


def get_promptfoo_status(timeout_seconds: int = 10) -> dict[str, Any]:
    if timeout_seconds == 10:
        return dict(_cached_promptfoo_status())
    return _compute_promptfoo_status(timeout_seconds=timeout_seconds)


@lru_cache(maxsize=1)
def _cached_promptfoo_status() -> dict[str, Any]:
    return _compute_promptfoo_status(timeout_seconds=10)


def _compute_promptfoo_status(*, timeout_seconds: int) -> dict[str, Any]:
    command, executable_path = resolve_promptfoo_command()
    node_version = _command_stdout(["node", "--version"], timeout_seconds=timeout_seconds)
    if not command:
        return {
            "available": False,
            "version": None,
            "node_version": node_version,
            "install_hint": PROMPTFOO_INSTALL_HINT,
            "supported_modes": ["single_target", "multi_target_comparison", "suite_assertion_overlay", "policy_comparison"],
            "final_verdict_capable": False,
            "advanced": {
                "executable_path": None,
                "command": None,
                "python_executable": sys.executable,
                "node_version": node_version,
            },
        }

    try:
        result = subprocess.run(
            [*command, "--version"],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "available": False,
            "version": None,
            "node_version": node_version,
            "error": str(exc),
            "install_hint": PROMPTFOO_INSTALL_HINT,
            "supported_modes": ["single_target", "multi_target_comparison", "suite_assertion_overlay", "policy_comparison"],
            "final_verdict_capable": False,
            "advanced": {
                "executable_path": executable_path,
                "command": command,
                "python_executable": sys.executable,
                "node_version": node_version,
            },
        }

    output = (result.stdout or result.stderr or "").strip()
    available = result.returncode == 0
    return {
        "available": available,
        "version": output.splitlines()[0].strip() if output else None,
        "node_version": node_version,
        "install_hint": None if available else PROMPTFOO_INSTALL_HINT,
        "supported_modes": ["single_target", "multi_target_comparison", "suite_assertion_overlay", "policy_comparison"],
        "final_verdict_capable": False,
        "advanced": {
            "executable_path": executable_path,
            "command": command,
            "python_executable": sys.executable,
            "node_version": node_version,
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
            "returncode": result.returncode,
        },
    }


def discover_promptfoo_plugins(timeout_seconds: int = 20) -> list[str]:
    if timeout_seconds == 20:
        return list(_cached_promptfoo_plugins())
    status = get_promptfoo_status(timeout_seconds=max(5, min(timeout_seconds, 15)))
    command = (status.get("advanced") or {}).get("command")
    if not status.get("available") or not isinstance(command, list) or not command:
        return []
    try:
        result = subprocess.run(
            [*command, "redteam", "plugins", "--ids-only"],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    plugins: list[str] = []
    for line in (result.stdout or "").splitlines():
        text = line.strip()
        if not text or text.startswith("promptfoo"):
            continue
        plugins.append(text)
    return plugins


@lru_cache(maxsize=1)
def _cached_promptfoo_plugins() -> tuple[str, ...]:
    return tuple(discover_promptfoo_plugins(timeout_seconds=19))


def resolve_promptfoo_command() -> tuple[list[str] | None, str | None]:
    configured = str(os.getenv("SPRICO_PROMPTFOO_EXECUTABLE") or "").strip()
    if configured:
        return _split_executable(configured)
    promptfoo = shutil.which("promptfoo")
    if promptfoo:
        return [promptfoo], promptfoo
    workspace_promptfoo = _workspace_promptfoo_executable()
    if workspace_promptfoo:
        return [workspace_promptfoo], workspace_promptfoo
    npx = shutil.which("npx")
    if npx and (_repo_root() / "node_modules" / "promptfoo").exists():
        return [npx, "--no-install", "promptfoo"], npx
    return None, None


def _split_executable(value: str) -> tuple[list[str] | None, str | None]:
    path = Path(value)
    if path.exists():
        return [str(path)], str(path)
    parts = shlex.split(value, posix=False)
    if not parts:
        return None, None
    executable = shutil.which(parts[0]) or parts[0]
    return [executable, *parts[1:]], executable


def _command_stdout(command: list[str], *, timeout_seconds: int) -> str | None:
    executable = shutil.which(command[0])
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, *command[1:]],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stdout or result.stderr or "").strip()
    return text.splitlines()[0].strip() if text else None


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parents[6]


def _workspace_promptfoo_executable() -> str | None:
    root = _repo_root()
    candidates = [
        root / "node_modules" / ".bin" / "promptfoo",
        root / "node_modules" / ".bin" / "promptfoo.cmd",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None
