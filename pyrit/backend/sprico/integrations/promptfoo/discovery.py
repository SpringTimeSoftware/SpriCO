"""Promptfoo executable discovery and optional runtime status."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from functools import lru_cache
from typing import Any

from pyrit.backend.services.persistent_target_store import PersistentTargetStore

PROMPTFOO_INSTALL_HINT = (
    "Install promptfoo with npm, add it to PATH, or set SPRICO_PROMPTFOO_EXECUTABLE. "
    "SpriCO also supports local workspace installs via npx --no-install promptfoo."
)
PROMPTFOO_SUPPORTED_MODES = ["single_target", "multi_target_comparison", "suite_assertion_overlay", "policy_comparison"]
PROMPTFOO_OPENAI_SOURCE_TYPE_ENV = "SPRICO_PROMPTFOO_OPENAI_SOURCE_TYPE"
PROMPTFOO_OPENAI_SECRET_REF_ENV = "SPRICO_PROMPTFOO_OPENAI_SECRET_REF"
PROMPTFOO_OPENAI_SECRET_VALUE_ENV = "SPRICO_PROMPTFOO_OPENAI_SECRET_VALUE"
PROMPTFOO_OPENAI_TARGET_SECRET_REF_ENV = "SPRICO_PROMPTFOO_OPENAI_TARGET_SECRET_REF"
PROMPTFOO_OPENAI_TARGET_SECRET_FIELD_ENV = "SPRICO_PROMPTFOO_OPENAI_TARGET_SECRET_FIELD"
PROMPTFOO_OPENAI_ENV_VAR = "OPENAI_API_KEY"
PROMPTFOO_ALLOWED_CREDENTIAL_SOURCES = {"environment", "secret_ref", "target_secret_ref", "disabled"}


def clear_promptfoo_discovery_cache() -> None:
    _cached_promptfoo_status.cache_clear()
    _cached_promptfoo_plugins.cache_clear()
    _cached_promptfoo_catalog_discovery.cache_clear()


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
    provider_credentials = {"openai": get_promptfoo_provider_credentials()}
    if not command:
        return {
            "available": False,
            "version": None,
            "node_version": node_version,
            "install_hint": PROMPTFOO_INSTALL_HINT,
            "supported_modes": PROMPTFOO_SUPPORTED_MODES,
            "final_verdict_capable": False,
            "provider_credentials": provider_credentials,
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
            "supported_modes": PROMPTFOO_SUPPORTED_MODES,
            "final_verdict_capable": False,
            "provider_credentials": provider_credentials,
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
        "supported_modes": PROMPTFOO_SUPPORTED_MODES,
        "final_verdict_capable": False,
        "provider_credentials": provider_credentials,
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


def get_promptfoo_provider_credentials(*, include_value: bool = False) -> dict[str, Any]:
    source_type = _normalize_credential_source_type()
    source_label = "disabled"
    secret_value: str | None = None
    missing_reason: str | None = None

    if source_type == "environment":
        source_label = PROMPTFOO_OPENAI_ENV_VAR
        secret_value = _read_env_secret(PROMPTFOO_OPENAI_ENV_VAR)
        if not secret_value:
            missing_reason = f"{PROMPTFOO_OPENAI_ENV_VAR} is not configured in the backend runtime environment."
    elif source_type == "secret_ref":
        secret_ref = str(os.getenv(PROMPTFOO_OPENAI_SECRET_REF_ENV) or "").strip()
        source_label = f"secret:{secret_ref}" if secret_ref else "secret:unconfigured"
        secret_value = _read_env_secret(PROMPTFOO_OPENAI_SECRET_VALUE_ENV)
        if not secret_ref or not secret_value:
            missing_reason = (
                f"Set {PROMPTFOO_OPENAI_SECRET_REF_ENV} and {PROMPTFOO_OPENAI_SECRET_VALUE_ENV} "
                "to use a promptfoo provider secret reference."
            )
    elif source_type == "target_secret_ref":
        target_registry_name = str(os.getenv(PROMPTFOO_OPENAI_TARGET_SECRET_REF_ENV) or "").strip()
        source_label = f"target:{target_registry_name}" if target_registry_name else "target:unconfigured"
        preferred_field = str(os.getenv(PROMPTFOO_OPENAI_TARGET_SECRET_FIELD_ENV) or "api_key").strip() or "api_key"
        params = _get_target_store().get_target_constructor_params(target_registry_name) if target_registry_name else None
        secret_value = _extract_target_secret_value(params=params, preferred_field=preferred_field)
        if not target_registry_name or not secret_value:
            missing_reason = (
                f"Set {PROMPTFOO_OPENAI_TARGET_SECRET_REF_ENV} to an admin-approved saved target that contains "
                "provider credentials before running promptfoo."
            )

    payload: dict[str, Any] = {
        "configured": bool(secret_value) and source_type != "disabled",
        "source_type": source_type,
        "source_label": source_label,
        "value_visible": False,
    }
    if include_value:
        payload["secret_value"] = secret_value
        payload["missing_reason"] = missing_reason or "Promptfoo provider credentials are disabled."
    return payload


def get_promptfoo_catalog_discovery(timeout_seconds: int = 20) -> dict[str, Any]:
    if timeout_seconds == 20:
        return dict(_cached_promptfoo_catalog_discovery())
    return _compute_promptfoo_catalog_discovery(timeout_seconds=timeout_seconds)


@lru_cache(maxsize=1)
def _cached_promptfoo_catalog_discovery() -> dict[str, Any]:
    return _compute_promptfoo_catalog_discovery(timeout_seconds=20)


def _compute_promptfoo_catalog_discovery(*, timeout_seconds: int) -> dict[str, Any]:
    status = get_promptfoo_status(timeout_seconds=max(5, min(timeout_seconds, 15)))
    command = (status.get("advanced") or {}).get("command")
    discovered_plugins = _discover_promptfoo_plugins(command=command, status=status, timeout_seconds=max(5, timeout_seconds - 1))
    return {
        "promptfoo_version": status.get("version"),
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "discovered_plugins": discovered_plugins,
    }


def discover_promptfoo_plugins(timeout_seconds: int = 20) -> list[str]:
    if timeout_seconds == 20:
        return list(_cached_promptfoo_plugins())
    return list(get_promptfoo_catalog_discovery(timeout_seconds=timeout_seconds).get("discovered_plugins") or [])


@lru_cache(maxsize=1)
def _cached_promptfoo_plugins() -> tuple[str, ...]:
    return tuple(get_promptfoo_catalog_discovery(timeout_seconds=20).get("discovered_plugins") or [])


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


def _discover_promptfoo_plugins(*, command: Any, status: dict[str, Any], timeout_seconds: int) -> list[str]:
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
    seen: set[str] = set()
    for line in (result.stdout or "").splitlines():
        text = line.strip()
        if not text or text.startswith("promptfoo") or text in seen:
            continue
        seen.add(text)
        plugins.append(text)
    return plugins


def _normalize_credential_source_type() -> str:
    configured = str(os.getenv(PROMPTFOO_OPENAI_SOURCE_TYPE_ENV) or "").strip().lower()
    if configured in PROMPTFOO_ALLOWED_CREDENTIAL_SOURCES:
        return configured
    if str(os.getenv(PROMPTFOO_OPENAI_TARGET_SECRET_REF_ENV) or "").strip():
        return "target_secret_ref"
    if str(os.getenv(PROMPTFOO_OPENAI_SECRET_REF_ENV) or "").strip() or _read_env_secret(PROMPTFOO_OPENAI_SECRET_VALUE_ENV):
        return "secret_ref"
    if _read_env_secret(PROMPTFOO_OPENAI_ENV_VAR):
        return "environment"
    return "disabled"


def _read_env_secret(name: str) -> str | None:
    value = os.getenv(name)
    text = str(value or "").strip()
    return text or None


def _extract_target_secret_value(*, params: dict[str, Any] | None, preferred_field: str) -> str | None:
    if not isinstance(params, dict):
        return None
    preferred = str(preferred_field or "").strip()
    candidates = [preferred] if preferred else []
    candidates.extend(["api_key", "authorization", "access_token", "token"])
    seen: set[str] = set()
    for field in candidates:
        if field in seen:
            continue
        seen.add(field)
        value = params.get(field)
        text = str(value or "").strip()
        if text:
            return text
    return None


def _get_target_store() -> PersistentTargetStore:
    store = PersistentTargetStore()
    store.initialize()
    return store


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
