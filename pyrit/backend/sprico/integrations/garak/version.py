"""garak version and installation discovery."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
from pathlib import Path
import subprocess
import sys
from typing import Any

INSTALL_HINT = 'Install optional garak support with: python -m pip install -e ".[garak]"'


def get_garak_version_info() -> dict[str, Any]:
    """Return garak availability without raising when garak is absent."""

    spec = importlib.util.find_spec("garak")
    if spec is None:
        return _status_payload(
            available=False,
            version=None,
            python=sys.version,
            executable=sys.executable,
            import_error="garak is not importable",
            cli_error=_cli_error(),
            install_hint=INSTALL_HINT,
            import_path=None,
            install_mode="absent",
            error="garak is not importable",
        )

    try:
        module = importlib.import_module("garak")
        version = getattr(module, "__version__", None) or importlib.metadata.version("garak")
        import_path = str(Path(getattr(module, "__file__", "")).resolve()) if getattr(module, "__file__", None) else None
        return _status_payload(
            available=True,
            version=version,
            python=sys.version,
            executable=sys.executable,
            import_error=None,
            cli_error=_cli_error(),
            install_hint=INSTALL_HINT,
            import_path=import_path,
            install_mode=_install_mode(import_path),
            error=None,
        )
    except Exception as exc:  # pragma: no cover - defensive integration boundary
        return _status_payload(
            available=False,
            version=None,
            python=sys.version,
            executable=sys.executable,
            import_error=str(exc),
            cli_error=_cli_error(),
            install_hint=INSTALL_HINT,
            import_path=None,
            install_mode="unknown",
            error=str(exc),
        )


def _status_payload(**payload: Any) -> dict[str, Any]:
    """Return the public status shape while preserving legacy top-level fields."""

    payload["advanced"] = {
        "python_executable": payload.get("executable"),
        "python_version": payload.get("python"),
        "import_error": payload.get("import_error"),
        "cli_error": payload.get("cli_error"),
        "import_path": payload.get("import_path"),
        "install_mode": payload.get("install_mode"),
    }
    return payload


def _install_mode(import_path: str | None) -> str:
    if not import_path:
        return "unknown"
    lowered = import_path.lower()
    if "site-packages" in lowered:
        return "pip"
    if "\\garak\\" in lowered or "/garak/" in lowered:
        return "vendored"
    return "unknown"


def _cli_error() -> str | None:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "garak", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
    except Exception as exc:  # pragma: no cover - environment-specific boundary
        return str(exc)
    if completed.returncode == 0:
        return None
    return (completed.stderr or completed.stdout or f"garak CLI returned {completed.returncode}").strip()[:500]
