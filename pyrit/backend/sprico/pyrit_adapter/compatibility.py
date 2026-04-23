"""Compatibility metadata and version discovery for SpriCO's PyRIT adapter."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from pyrit.backend.sprico.pyrit_adapter.registry import default_feature_registry

_MATRIX_PATH = Path(__file__).with_name("compatibility_matrix.json")


def get_pyrit_version_info() -> dict[str, Any]:
    try:
        module = importlib.import_module("pyrit")
    except Exception as exc:  # pragma: no cover - defensive import guard
        return {
            "available": False,
            "import_path": None,
            "version": None,
            "commit": None,
            "source": "unknown",
            "error": str(exc),
        }

    import_path = str(Path(getattr(module, "__file__", "")).resolve()) if getattr(module, "__file__", None) else None
    repo_root = Path(__file__).resolve().parents[4]
    source = "unknown"
    if import_path and import_path.startswith(str((repo_root / "pyrit").resolve())):
        source = "vendored"
    elif import_path and "site-packages" in import_path:
        source = "pip"
    elif (repo_root / ".gitmodules").exists():
        source = "submodule"

    return {
        "available": True,
        "import_path": import_path,
        "version": getattr(module, "__version__", None),
        "commit": _read_git_commit(repo_root),
        "source": source,
        "error": None,
    }


def load_compatibility_matrix() -> dict[str, Any]:
    payload = _load_matrix_file()
    version_info = get_pyrit_version_info()
    pyrit_block = dict(payload.get("pyrit") or {})
    pyrit_block.update(
        {
            "source": version_info.get("source") or pyrit_block.get("source") or "",
            "version": version_info.get("version") or pyrit_block.get("version") or "",
            "commit": version_info.get("commit") or pyrit_block.get("commit") or "",
        }
    )
    features = payload.get("features") or []
    if not features:
        features = [feature.to_dict() for feature in default_feature_registry()]
    return {
        "pyrit": pyrit_block,
        "version_info": version_info,
        "features": features,
    }


def _load_matrix_file() -> dict[str, Any]:
    if not _MATRIX_PATH.exists():
        return {"pyrit": {}, "features": []}
    try:
        return json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"pyrit": {}, "features": []}


def _read_git_commit(repo_root: Path) -> str | None:
    git_dir = repo_root / ".git"
    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None
    head = head_path.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref_path = git_dir / head.split(" ", 1)[1].strip()
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8").strip()
        return None
    return head or None
