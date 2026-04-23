# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
SQLite-backed persistence for user-saved prompt targets.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken

from pyrit.backend.models.common import SENSITIVE_FIELD_PATTERNS
from pyrit.common.path import DB_DATA_PATH

logger = logging.getLogger(__name__)

TARGET_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_targets (
    id TEXT PRIMARY KEY,
    target_registry_name TEXT NOT NULL UNIQUE,
    target_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    model_name TEXT,
    endpoint TEXT,
    params_json TEXT NOT NULL,
    encrypted_secrets TEXT,
    credential_strategy TEXT NOT NULL DEFAULT 'none',
    is_active INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    archive_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_target_state (
    state_key TEXT PRIMARY KEY,
    active_target_registry_name TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_targets_active ON audit_targets(is_active);
"""

ACTIVE_TARGET_STATE_KEY = "active_target"
DEFAULT_SECRET_KEY_PATH = DB_DATA_PATH / "target_secrets.key"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(pattern in lowered for pattern in SENSITIVE_FIELD_PATTERNS)


class PersistentTargetStore:
    """Persist and restore user-created targets in SQLite."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        env_db_path = os.getenv("SPRICO_TARGET_DB_PATH")
        self._db_path = Path(db_path or env_db_path) if db_path or env_db_path else Path(DB_DATA_PATH) / "audit.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(self._load_or_create_secret_key())

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(TARGET_SCHEMA_SQL)
            self._ensure_schema_columns(conn)

    def list_targets(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        where_clause = "" if include_archived else "WHERE archived_at IS NULL"
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM audit_targets
                {where_clause}
                ORDER BY created_at DESC, target_registry_name ASC
                """
            ).fetchall()
        return [self._deserialize_row(dict(row)) for row in rows]

    def get_target(self, target_registry_name: str) -> Optional[dict[str, Any]]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM audit_targets WHERE target_registry_name = ?",
                (target_registry_name,),
            ).fetchone()
        if row is None:
            return None
        return self._deserialize_row(dict(row))

    def save_target(
        self,
        *,
        target_registry_name: str,
        target_type: str,
        display_name: str,
        model_name: Optional[str],
        endpoint: Optional[str],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        non_secret_params, secret_params = self._split_params(params)
        now = _utc_now()
        existing = self.get_target(target_registry_name)
        target_id = existing["id"] if existing else str(uuid.uuid4())
        created_at = existing["created_at"] if existing else now
        is_active = 1 if existing and existing.get("is_active") else 0
        encrypted_secrets = self._encrypt(secret_params) if secret_params else None
        credential_strategy = "encrypted_sqlite" if secret_params else "none"

        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO audit_targets (
                    id,
                    target_registry_name,
                    target_type,
                    display_name,
                    model_name,
                    endpoint,
                    params_json,
                    encrypted_secrets,
                    credential_strategy,
                    is_active,
                    archived_at,
                    archive_reason,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                ON CONFLICT(target_registry_name) DO UPDATE SET
                    target_type = excluded.target_type,
                    display_name = excluded.display_name,
                    model_name = excluded.model_name,
                    endpoint = excluded.endpoint,
                    params_json = excluded.params_json,
                    encrypted_secrets = excluded.encrypted_secrets,
                    credential_strategy = excluded.credential_strategy,
                    is_active = excluded.is_active,
                    archived_at = NULL,
                    archive_reason = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    target_id,
                    target_registry_name,
                    target_type,
                    display_name,
                    model_name,
                    endpoint,
                    json.dumps(non_secret_params, ensure_ascii=True),
                    encrypted_secrets,
                    credential_strategy,
                    is_active,
                    created_at,
                    now,
                ),
            )
        stored = self.get_target(target_registry_name)
        if stored is None:
            raise ValueError(f"Failed to persist target '{target_registry_name}'")
        return stored

    def update_target_config(
        self,
        *,
        target_registry_name: str,
        display_name: Optional[str] = None,
        special_instructions: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        row = self.get_target(target_registry_name)
        if row is None:
            return None

        params = self._merge_params(row)
        if special_instructions is not None:
            cleaned = special_instructions.strip()
            if cleaned:
                params["system_instructions"] = cleaned
            else:
                params.pop("system_instructions", None)

        non_secret_params, secret_params = self._split_params(params)
        encrypted_secrets = self._encrypt(secret_params) if secret_params else None
        credential_strategy = "encrypted_sqlite" if secret_params else "none"
        updated_display_name = display_name.strip() if isinstance(display_name, str) and display_name.strip() else row["display_name"]
        now = _utc_now()

        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE audit_targets
                SET display_name = ?,
                    params_json = ?,
                    encrypted_secrets = ?,
                    credential_strategy = ?,
                    updated_at = ?
                WHERE target_registry_name = ?
                """,
                (
                    updated_display_name,
                    json.dumps(non_secret_params, ensure_ascii=True),
                    encrypted_secrets,
                    credential_strategy,
                    now,
                    target_registry_name,
                ),
            )
        return self.get_target(target_registry_name)

    def archive_target(self, target_registry_name: str, *, reason: Optional[str] = None) -> Optional[dict[str, Any]]:
        row = self.get_target(target_registry_name)
        if row is None:
            return None
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE audit_targets
                SET archived_at = ?,
                    archive_reason = ?,
                    is_active = 0,
                    updated_at = ?
                WHERE target_registry_name = ?
                """,
                (now, reason, now, target_registry_name),
            )
            conn.execute(
                """
                UPDATE audit_target_state
                SET active_target_registry_name = NULL,
                    updated_at = ?
                WHERE state_key = ? AND active_target_registry_name = ?
                """,
                (now, ACTIVE_TARGET_STATE_KEY, target_registry_name),
            )
        return self.get_target(target_registry_name)

    def set_active_target(self, target_registry_name: str) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE audit_targets SET is_active = CASE WHEN target_registry_name = ? THEN 1 ELSE 0 END", (target_registry_name,))
            conn.execute(
                """
                INSERT INTO audit_target_state (state_key, active_target_registry_name, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    active_target_registry_name = excluded.active_target_registry_name,
                    updated_at = excluded.updated_at
                """,
                (ACTIVE_TARGET_STATE_KEY, target_registry_name, now),
            )

    def clear_active_target(self) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE audit_targets SET is_active = 0")
            conn.execute(
                """
                INSERT INTO audit_target_state (state_key, active_target_registry_name, updated_at)
                VALUES (?, NULL, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    active_target_registry_name = NULL,
                    updated_at = excluded.updated_at
                """,
                (ACTIVE_TARGET_STATE_KEY, now),
            )

    def get_active_target_name(self) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT active_target_registry_name FROM audit_target_state WHERE state_key = ?",
                (ACTIVE_TARGET_STATE_KEY,),
            ).fetchone()
        if row is None:
            return None
        return row["active_target_registry_name"]

    def get_restorable_targets(self) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = []
        for row in self.list_targets(include_archived=False):
            try:
                row["constructor_params"] = self._merge_params(row)
            except InvalidToken as exc:
                logger.error("Failed to decrypt stored credentials for target '%s'", row["target_registry_name"], exc_info=exc)
                continue
            targets.append(row)
        return targets

    def get_target_constructor_params(self, target_registry_name: str) -> Optional[dict[str, Any]]:
        row = self.get_target(target_registry_name)
        if row is None:
            return None
        return self._merge_params(row)

    def get_target_config_snapshot(self, target_registry_name: str) -> Optional[dict[str, Any]]:
        row = self.get_target(target_registry_name)
        if row is None:
            return None

        merged_params = self._merge_params(row)
        masked_params: dict[str, Any] = {}
        for key, value in merged_params.items():
            if _is_sensitive_key(key):
                masked_params[key] = self._mask_secret_value(value)
            else:
                masked_params[key] = value

        return {
            "id": row.get("id"),
            "target_registry_name": row.get("target_registry_name"),
            "target_type": row.get("target_type"),
            "display_name": row.get("display_name"),
            "model_name": row.get("model_name"),
            "endpoint": row.get("endpoint"),
            "params": masked_params,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "archived_at": row.get("archived_at"),
            "archive_reason": row.get("archive_reason"),
            "credential_strategy": row.get("credential_strategy"),
        }

    def _deserialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["params"] = json.loads(row.pop("params_json") or "{}")
        row["is_active"] = bool(row.get("is_active"))
        row["is_archived"] = bool(row.get("archived_at"))
        return row

    def _ensure_schema_columns(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(audit_targets)").fetchall()}
        if "archived_at" not in columns:
            conn.execute("ALTER TABLE audit_targets ADD COLUMN archived_at TEXT")
        if "archive_reason" not in columns:
            conn.execute("ALTER TABLE audit_targets ADD COLUMN archive_reason TEXT")

    def _merge_params(self, row: dict[str, Any]) -> dict[str, Any]:
        params = dict(row.get("params") or {})
        encrypted_secrets = row.get("encrypted_secrets")
        if encrypted_secrets:
            params.update(json.loads(self._decrypt(encrypted_secrets)))
        return params

    def _split_params(self, params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        non_secret: dict[str, Any] = {}
        secret: dict[str, Any] = {}
        for key, value in params.items():
            if value is None:
                continue
            if _is_sensitive_key(key):
                secret[key] = value
            else:
                non_secret[key] = value
        return non_secret, secret

    def _encrypt(self, payload: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(payload, ensure_ascii=True).encode("utf-8")).decode("utf-8")

    def _decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")

    def _mask_secret_value(self, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            return "********"

        trimmed = value.strip()
        if not trimmed:
            return ""

        suffix = trimmed[-4:] if len(trimmed) > 4 else trimmed
        prefix = trimmed[:3] if trimmed.startswith("sk-") else ""
        masked_core = "********"
        return f"{prefix}{masked_core}{suffix}"

    def _load_or_create_secret_key(self) -> bytes:
        env_key = None
        try:
            import os

            env_key = os.getenv("SIDDHI_TARGET_SECRET_KEY")
        except Exception:
            env_key = None

        if env_key:
            return env_key.encode("utf-8")

        key_path = DEFAULT_SECRET_KEY_PATH
        if key_path.exists():
            return key_path.read_bytes().strip()

        key = Fernet.generate_key()
        key_path.write_bytes(key)
        return key

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
