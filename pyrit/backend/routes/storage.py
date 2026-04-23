"""Storage diagnostics APIs for SpriCO operators."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from fastapi import APIRouter

from audit.database import AuditDatabase
from pyrit.backend.services.persistent_target_store import PersistentTargetStore
from pyrit.backend.sprico.storage import COLLECTIONS, get_storage_backend
from pyrit.common.path import DB_DATA_PATH
from pyrit.memory import CentralMemory

router = APIRouter(tags=["storage"])


@router.get("/storage/status")
async def get_storage_status() -> dict[str, Any]:
    backend = get_storage_backend()
    sprico_path = getattr(backend, "path", None)
    audit_db_path = AuditDatabase().db_path
    target_store_path = PersistentTargetStore().db_path
    pyrit_memory = CentralMemory.get_memory_instance()
    pyrit_memory_path = getattr(pyrit_memory, "db_path", None)
    counts = _sprico_counts(backend)
    counts.update(
        {
            "pyrit_attacks": _count_pyrit_attacks(pyrit_memory),
            "audit_runs": _count_sqlite_rows(audit_db_path, "audit_runs"),
        }
    )
    return {
        "storage_backend": getattr(backend, "name", "unknown"),
        "sprico_sqlite_path": _path_text(sprico_path),
        "pyrit_memory_path": _path_text(pyrit_memory_path),
        "audit_db_path": _path_text(audit_db_path),
        "target_config_store_path": _path_text(target_store_path),
        "policy_project_condition_store_path": _path_text(sprico_path),
        "garak_artifacts_path": str((DB_DATA_PATH / "garak_scans").resolve()),
        "uploaded_artifacts_path": str(Path(DB_DATA_PATH).resolve()),
        "record_counts": counts,
    }


def _sprico_counts(backend: Any) -> dict[str, int]:
    aliases = {
        "garak_runs": "scanner_runs",
        "red_scans": "red_scans",
        "shield_events": "shield_events",
        "evidence_items": "evidence",
        "findings": "findings",
        "policies": "policies",
        "projects": "projects",
        "custom_conditions": "conditions",
    }
    counts: dict[str, int] = {
        "scanner_runs": 0,
        "red_scans": 0,
        "shield_events": 0,
        "evidence": 0,
        "findings": 0,
        "policies": 0,
        "projects": 0,
        "conditions": 0,
    }
    for collection in COLLECTIONS:
        alias = aliases.get(collection)
        if not alias:
            continue
        try:
            counts[alias] = len(backend.list_records(collection))
        except Exception:
            counts[alias] = 0
    return counts


def _count_pyrit_attacks(memory: Any) -> int:
    try:
        return len(memory.get_attack_results())
    except Exception:
        return 0


def _count_sqlite_rows(path: Path, table: str) -> int:
    if not path.exists():
        return 0
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


def _path_text(value: Any) -> str:
    if value is None:
        return ""
    if str(value) == ":memory:":
        return ":memory:"
    try:
        return str(Path(value).resolve())
    except TypeError:
        return str(value)
