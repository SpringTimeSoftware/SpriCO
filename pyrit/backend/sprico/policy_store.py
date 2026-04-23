"""SpriCO project and policy store."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any

from pyrit.common.path import DB_DATA_PATH
from pyrit.backend.sprico.storage import JsonStorageBackend, StorageBackend, default_policy, get_storage_backend


class SpriCOPolicyStore:
    """Durable store for project/policy APIs with SQLite default and JSON fallback."""

    def __init__(self, path: Path | None = None, backend: StorageBackend | None = None) -> None:
        self.path = path or (DB_DATA_PATH / "sprico_policy_store.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = backend or (JsonStorageBackend(path=self.path) if path is not None else get_storage_backend())

    def list_projects(self) -> list[dict[str, Any]]:
        return self._backend.list_records("projects")

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        project_id = str(payload.get("id") or f"proj_{uuid.uuid4().hex[:12]}")
        policy_id = str(payload.get("policy_id") or "policy_public_default")
        if self._backend.get_record("policies", policy_id) is None:
            raise ValueError(f"Policy '{policy_id}' does not exist")
        project = {
            "id": project_id,
            "name": str(payload.get("name") or project_id),
            "description": payload.get("description"),
            "application_id": payload.get("application_id"),
            "environment": payload.get("environment") or "dev",
            "target_ids": list(payload.get("target_ids") or []),
            "policy_id": policy_id,
            "metadata_tags": dict(payload.get("metadata_tags") or {}),
            "created_at": now,
            "updated_at": now,
        }
        self._backend.upsert_record("projects", project_id, project)
        return project

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self._backend.get_record("projects", project_id)

    def patch_project(self, project_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        project = self._backend.get_record("projects", project_id)
        if project is None:
            return None
        if "policy_id" in patch and self._backend.get_record("policies", patch["policy_id"]) is None:
            raise ValueError(f"Policy '{patch['policy_id']}' does not exist")
        for key in ("name", "description", "application_id", "environment", "target_ids", "policy_id", "metadata_tags"):
            if key in patch:
                project[key] = patch[key]
        project["updated_at"] = _now()
        self._backend.upsert_record("projects", project_id, project)
        return project

    def list_policies(self) -> list[dict[str, Any]]:
        return self._backend.list_records("policies")

    def create_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        _validate_list_entries(payload)
        now = _now()
        policy_id = str(payload.get("id") or f"policy_{uuid.uuid4().hex[:12]}")
        policy = default_policy(policy_id=policy_id, name=str(payload.get("name") or policy_id), mode=payload.get("mode") or "UNKNOWN")
        policy.update({key: value for key, value in payload.items() if value is not None})
        policy["id"] = policy_id
        policy["version"] = str(policy.get("version") or "1.0.0")
        policy["created_at"] = now
        policy["updated_at"] = now
        policy["audit_history"] = [
            {
                "timestamp": now,
                "action": "created",
                "actor": payload.get("created_by") or "system",
                "changes": deepcopy(payload),
            }
        ]
        self._backend.upsert_record("policies", policy_id, policy)
        self._persist_policy_version(policy, action="created", actor=payload.get("created_by") or "system", changes=deepcopy(payload))
        return policy

    def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        return self._backend.get_record("policies", policy_id)

    def patch_policy(self, policy_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        _validate_list_entries(patch)
        policy = self._backend.get_record("policies", policy_id)
        if policy is None:
            return None
        before = deepcopy(policy)
        for key, value in patch.items():
            if key in {"id", "created_at", "audit_history"}:
                continue
            policy[key] = value
        policy["version"] = _bump_patch(str(policy.get("version") or "1.0.0"))
        policy["updated_at"] = _now()
        policy.setdefault("audit_history", []).append(
            {
                "timestamp": policy["updated_at"],
                "action": "patched",
                "actor": patch.get("updated_by") or "system",
                "changes": _diff(before, policy),
            }
        )
        changes = _diff(before, policy)
        self._backend.upsert_record("policies", policy_id, policy)
        self._persist_policy_version(policy, action="patched", actor=patch.get("updated_by") or "system", changes=changes)
        return policy

    def get_policy_for_request(self, *, policy_id: str | None = None, project_id: str | None = None) -> dict[str, Any]:
        if policy_id:
            policy = self._backend.get_record("policies", policy_id)
            if policy is not None:
                return policy
        if project_id:
            project = self._backend.get_record("projects", project_id)
            project_policy_id = project.get("policy_id") if project else None
            if project_policy_id:
                policy = self._backend.get_record("policies", str(project_policy_id))
                if policy is not None:
                    return policy
        default = self._backend.get_record("policies", "policy_public_default")
        if default is None:
            default = default_policy("policy_public_default", "Public Default", "PUBLIC")
            self._backend.upsert_record("policies", "policy_public_default", default)
        return default

    def audit_history(self, policy_id: str) -> list[dict[str, Any]] | None:
        policy = self.get_policy(policy_id)
        if policy is None:
            return None
        history = [
            item
            for item in self._backend.list_records("audit_history")
            if item.get("policy_id") == policy_id
        ]
        if history:
            return sorted(history, key=lambda item: str(item.get("timestamp") or ""))
        return list(policy.get("audit_history") or [])

    def policy_versions(self, policy_id: str) -> list[dict[str, Any]]:
        versions = [
            item
            for item in self._backend.list_records("policy_versions")
            if item.get("policy_id") == policy_id
        ]
        return sorted(versions, key=lambda item: str(item.get("created_at") or ""))

    def _ensure(self) -> None:
        if self.path.exists():
            return
        now = _now()
        data = {
            "projects": {},
            "policies": {
                "policy_public_default": _default_policy("policy_public_default", "Public Default", "PUBLIC", now=now),
                "policy_hospital_strict_v1": _default_policy("policy_hospital_strict_v1", "Hospital Strict", "REDTEAM_STRICT", now=now),
            },
        }
        data["policies"]["policy_hospital_strict_v1"]["sensitivity"] = "L4"
        data["policies"]["policy_hospital_strict_v1"]["target_domain"] = "hospital"
        self._save(data)

    def _load(self) -> dict[str, Any]:
        self._ensure()
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _persist_policy_version(self, policy: dict[str, Any], *, action: str, actor: str, changes: dict[str, Any]) -> None:
        now = str(policy.get("updated_at") or _now())
        version_id = f"{policy['id']}:{policy.get('version') or '1.0.0'}"
        self._backend.upsert_record(
            "policy_versions",
            version_id,
            {
                "id": version_id,
                "policy_id": policy["id"],
                "version": policy.get("version") or "1.0.0",
                "policy": deepcopy(policy),
                "created_at": now,
            },
        )
        audit_id = f"{policy['id']}:{now}:{action}"
        self._backend.upsert_record(
            "audit_history",
            audit_id,
            {
                "id": audit_id,
                "policy_id": policy["id"],
                "timestamp": now,
                "action": action,
                "actor": actor,
                "changes": deepcopy(changes),
            },
        )


def _default_policy(policy_id: str, name: str, mode: str, now: str | None = None) -> dict[str, Any]:
    return default_policy(policy_id, name, mode, now=now)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bump_patch(version: str) -> str:
    parts = [int(part) if part.isdigit() else 0 for part in version.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    parts[2] += 1
    return ".".join(str(part) for part in parts)


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for key, value in after.items():
        if key == "audit_history":
            continue
        if before.get(key) != value:
            changes[key] = {"before": before.get(key), "after": value}
    return changes


def _validate_list_entries(payload: dict[str, Any]) -> None:
    for list_name in ("allow_list", "deny_list"):
        if list_name not in payload:
            continue
        for index, item in enumerate(payload.get(list_name) or []):
            if not isinstance(item, dict):
                raise ValueError(f"{list_name}[{index}] must be an object")
            missing = [field for field in ("reason", "expiry", "created_by") if not item.get(field)]
            if missing:
                raise ValueError(f"{list_name}[{index}] is missing required fields: {', '.join(missing)}")
