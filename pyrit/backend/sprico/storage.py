"""Storage backends for SpriCO project, policy, evidence, and scan records."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Protocol

from pyrit.common.path import DB_DATA_PATH

COLLECTIONS = (
    "projects",
    "policies",
    "policy_versions",
    "custom_conditions",
    "condition_versions",
    "condition_simulations",
    "condition_approvals",
    "condition_tests",
    "condition_audit_history",
    "scans",
    "scan_results",
    "findings",
    "evidence_items",
    "runs",
    "audit_history",
    "shield_events",
    "garak_runs",
    "garak_artifacts",
    "red_scans",
    "promptfoo_runs",
)

DEFAULT_POLICY_IDS = ("policy_public_default", "policy_hospital_strict_v1")


class StorageBackend(Protocol):
    name: str

    def list_records(self, collection: str) -> list[dict[str, Any]]:
        ...

    def get_record(self, collection: str, record_id: str) -> dict[str, Any] | None:
        ...

    def upsert_record(self, collection: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def append_record(self, collection: str, payload: dict[str, Any], *, record_id: str | None = None) -> dict[str, Any]:
        ...


class JsonStorageBackend:
    """JSON-file fallback for local development and explicit opt-out from SQLite."""

    name = "json"

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (DB_DATA_PATH / "sprico_storage.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def list_records(self, collection: str) -> list[dict[str, Any]]:
        data = self._load()
        return list(data[_collection(collection)].values())

    def get_record(self, collection: str, record_id: str) -> dict[str, Any] | None:
        data = self._load()
        record = data[_collection(collection)].get(record_id)
        return deepcopy(record) if record is not None else None

    def upsert_record(self, collection: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        data[_collection(collection)][record_id] = deepcopy(payload)
        self._save(data)
        return deepcopy(payload)

    def append_record(self, collection: str, payload: dict[str, Any], *, record_id: str | None = None) -> dict[str, Any]:
        key = record_id or str(payload.get("id") or payload.get("finding_id") or f"{collection}_{_compact_now()}")
        item = dict(payload)
        item.setdefault("id", key)
        return self.upsert_record(collection, key, item)

    def _ensure(self) -> None:
        if self.path.exists():
            data = self._load()
        else:
            data = {collection: {} for collection in COLLECTIONS}
        changed = False
        for collection in COLLECTIONS:
            if collection not in data:
                data[collection] = {}
                changed = True
        changed = _seed_defaults(data) or changed
        if changed or not self.path.exists():
            self._save(data)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {collection: {} for collection in COLLECTIONS}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


class SqliteStorageBackend:
    """SQLite-backed SpriCO storage using JSON payload columns per collection."""

    name = "sqlite"

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.getenv("SPRICO_SQLITE_PATH") or DB_DATA_PATH / "sprico.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure()

    def list_records(self, collection: str) -> list[dict[str, Any]]:
        table = _collection(collection)
        with self._connect() as conn:
            rows = conn.execute(f"SELECT data FROM {table} ORDER BY updated_at DESC, id ASC").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def get_record(self, collection: str, record_id: str) -> dict[str, Any] | None:
        table = _collection(collection)
        with self._connect() as conn:
            row = conn.execute(f"SELECT data FROM {table} WHERE id = ?", (record_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def upsert_record(self, collection: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        table = _collection(collection)
        now = _now()
        data = json.dumps(payload, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {table} (id, data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = excluded.updated_at
                """,
                (record_id, data, str(payload.get("created_at") or now), now),
            )
        return deepcopy(payload)

    def append_record(self, collection: str, payload: dict[str, Any], *, record_id: str | None = None) -> dict[str, Any]:
        key = record_id or str(payload.get("id") or payload.get("finding_id") or f"{collection}_{_compact_now()}")
        item = dict(payload)
        item.setdefault("id", key)
        return self.upsert_record(collection, key, item)

    def _ensure(self) -> None:
        with self._connect() as conn:
            for table in COLLECTIONS:
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
            data = {collection: {} for collection in COLLECTIONS}
            for collection in COLLECTIONS:
                rows = conn.execute(f"SELECT id, data FROM {collection}").fetchall()
                data[collection] = {row["id"]: json.loads(row["data"]) for row in rows}
            if _seed_defaults(data):
                now = _now()
                for collection in ("policies", "policy_versions", "audit_history"):
                    for record_id, payload in data[collection].items():
                        conn.execute(
                            f"""
                            INSERT INTO {collection} (id, data, created_at, updated_at)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(id) DO NOTHING
                            """,
                            (
                                record_id,
                                json.dumps(payload, sort_keys=True),
                                str(payload.get("created_at") or now),
                                str(payload.get("updated_at") or now),
                            ),
                        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


_DEFAULT_BACKEND: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    global _DEFAULT_BACKEND
    backend_name = os.getenv("SPRICO_STORAGE_BACKEND", "sqlite").strip().lower()
    if _DEFAULT_BACKEND is not None and getattr(_DEFAULT_BACKEND, "name", None) == backend_name:
        return _DEFAULT_BACKEND
    if backend_name == "json":
        _DEFAULT_BACKEND = JsonStorageBackend()
    else:
        _DEFAULT_BACKEND = SqliteStorageBackend()
    return _DEFAULT_BACKEND


def reset_storage_backend_cache() -> None:
    global _DEFAULT_BACKEND
    _DEFAULT_BACKEND = None


def default_policy(policy_id: str, name: str, mode: str, now: str | None = None) -> dict[str, Any]:
    now = now or _now()
    return {
        "id": policy_id,
        "name": name,
        "version": "1.0.0",
        "description": None,
        "mode": mode,
        "sensitivity": "L2",
        "target_domain": "general",
        "enabled_guardrails": {
            "prompt_defense": True,
            "dlp": True,
            "content_moderation": True,
            "malicious_links": True,
            "custom_detectors": True,
        },
        "apply_to": ["input", "output", "tool_input", "tool_output", "rag_context", "memory_write"],
        "custom_detectors": [],
        "allowed_domains": [],
        "deny_domains": [],
        "allow_list": [],
        "deny_list": [],
        "retention": {"log_days": 30, "region": "default"},
        "redaction": {"default": True},
        "audit_history": [{"timestamp": now, "action": "seeded", "actor": "system", "changes": {}}],
        "created_at": now,
        "updated_at": now,
    }


def _seed_defaults(data: dict[str, dict[str, Any]]) -> bool:
    changed = False
    now = _now()
    if "policy_public_default" not in data["policies"]:
        policy = default_policy("policy_public_default", "Public Default", "PUBLIC", now=now)
        data["policies"][policy["id"]] = policy
        data["policy_versions"][f"{policy['id']}:1.0.0"] = _policy_version_payload(policy)
        data["audit_history"][f"{policy['id']}:{now}:seeded"] = {
            "id": f"{policy['id']}:{now}:seeded",
            "policy_id": policy["id"],
            "timestamp": now,
            "action": "seeded",
            "actor": "system",
            "changes": {},
        }
        changed = True
    if "policy_hospital_strict_v1" not in data["policies"]:
        policy = default_policy("policy_hospital_strict_v1", "Hospital Strict", "REDTEAM_STRICT", now=now)
        policy["sensitivity"] = "L4"
        policy["target_domain"] = "hospital"
        data["policies"][policy["id"]] = policy
        data["policy_versions"][f"{policy['id']}:1.0.0"] = _policy_version_payload(policy)
        data["audit_history"][f"{policy['id']}:{now}:seeded"] = {
            "id": f"{policy['id']}:{now}:seeded",
            "policy_id": policy["id"],
            "timestamp": now,
            "action": "seeded",
            "actor": "system",
            "changes": {},
        }
        changed = True
    return changed


def _policy_version_payload(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"{policy['id']}:{policy.get('version') or '1.0.0'}",
        "policy_id": policy["id"],
        "version": policy.get("version") or "1.0.0",
        "policy": deepcopy(policy),
        "created_at": policy.get("updated_at") or _now(),
    }


def _collection(collection: str) -> str:
    if collection not in COLLECTIONS:
        raise ValueError(f"Unknown SpriCO storage collection '{collection}'")
    return collection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
