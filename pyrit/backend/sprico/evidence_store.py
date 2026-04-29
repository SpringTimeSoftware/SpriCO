"""JSONL evidence store for SpriCO runtime/scanner events."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any

from pyrit.common.path import DB_DATA_PATH
from pyrit.backend.sprico.storage import StorageBackend, get_storage_backend


class SpriCOEvidenceStore:
    def __init__(self, path: Path | None = None, backend: StorageBackend | None = None) -> None:
        self.path = path or (DB_DATA_PATH / "sprico_evidence.jsonl")
        self._backend = backend or (None if path is not None else get_storage_backend())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._backend is None:
            self.path.touch(exist_ok=True)

    def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        evidence_id = str(event.get("evidence_id") or event.get("finding_id") or f"evidence_{uuid.uuid4().hex[:12]}")
        engine = event.get("engine") or event.get("engine_id") or "native"
        raw_result = event.get("raw_result") or event.get("raw_engine_result") or {}
        normalized_signal = event.get("normalized_signal") or event.get("matched_signals") or []
        policy_context = event.get("policy_context") or {}
        authorization_context = event.get("authorization_context") or {
            "policy_mode": (event.get("sprico_final_verdict") or {}).get("policy_mode") or policy_context.get("policy_mode"),
            "access_context": (event.get("sprico_final_verdict") or {}).get("access_context") or policy_context.get("access_context"),
            "authorization_source": (event.get("sprico_final_verdict") or {}).get("authorization_source") or policy_context.get("authorization_source"),
        }
        artifact_refs = event.get("artifact_refs") or event.get("scanner_artifact_refs") or []
        linked_finding_ids = _string_list(event.get("linked_finding_ids"))
        payload = {
            "id": evidence_id,
            "evidence_id": evidence_id,
            "finding_id": evidence_id,
            "created_at": created_at,
            "timestamp": event.get("timestamp") or created_at,
            "run_id": event.get("run_id"),
            "run_type": event.get("run_type"),
            "source_page": event.get("source_page"),
            "engine": engine,
            "engine_id": event.get("engine_id") or engine,
            "engine_name": event.get("engine_name") or str(engine),
            "engine_type": event.get("engine_type") or "evidence",
            "source_type": event.get("source_type"),
            "engine_version": event.get("engine_version") or "v1",
            "license_id": event.get("license_id"),
            "source_url": event.get("source_url"),
            "source_file": event.get("source_file"),
            "target_id": event.get("target_id"),
            "target_name": event.get("target_name"),
            "target_type": event.get("target_type"),
            "scan_id": event.get("scan_id"),
            "session_id": event.get("session_id"),
            "conversation_id": event.get("conversation_id"),
            "turn_id": event.get("turn_id"),
            "evidence_type": event.get("evidence_type"),
            "project_id": event.get("project_id"),
            "policy_id": event.get("policy_id"),
            "policy_name": event.get("policy_name"),
            "policy_context": policy_context,
            "authorization_context": authorization_context,
            "raw_input": event.get("raw_input"),
            "raw_output": event.get("raw_output"),
            "retrieved_context": event.get("retrieved_context") or [],
            "tool_calls": event.get("tool_calls") or [],
            "raw_result": raw_result,
            "raw_engine_result": raw_result,
            "scanner_result": event.get("scanner_result"),
            "artifact_refs": artifact_refs,
            "scanner_artifact_refs": artifact_refs,
            "assertion_results": event.get("assertion_results") or [],
            "normalized_signal": normalized_signal,
            "normalized_signals": event.get("normalized_signals") or normalized_signal,
            "matched_signals": event.get("matched_signals") or normalized_signal,
            "matched_conditions": event.get("matched_conditions") or [],
            "final_verdict": event.get("final_verdict"),
            "violation_risk": event.get("violation_risk"),
            "data_sensitivity": event.get("data_sensitivity"),
            "sprico_final_verdict": event.get("sprico_final_verdict")
            or {
                "verdict": event.get("final_verdict"),
                "violation_risk": event.get("violation_risk"),
                "data_sensitivity": event.get("data_sensitivity"),
                "policy_mode": (event.get("policy_context") or {}).get("policy_mode"),
                "access_context": (event.get("policy_context") or {}).get("access_context"),
                "authorization_source": (event.get("policy_context") or {}).get("authorization_source"),
                "matched_signals": event.get("matched_signals") or normalized_signal,
                "explanation": event.get("explanation"),
            },
            "reviewer_override": event.get("reviewer_override"),
            "redaction_status": event.get("redaction_status") or "redacted",
            "hash": event.get("hash"),
            "linked_finding_ids": linked_finding_ids,
        }
        if self._backend is not None:
            stored = self._backend.upsert_record("evidence_items", payload["evidence_id"], payload)
            if str(payload.get("engine") or "").startswith("sprico.shield"):
                self._backend.upsert_record("shield_events", payload["evidence_id"], payload)
            return stored
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return payload

    def get_event(self, evidence_id: str) -> dict[str, Any] | None:
        if self._backend is None:
            return next((item for item in self.list_events(limit=10_000) if item.get("evidence_id") == evidence_id), None)
        return self._backend.get_record("evidence_items", evidence_id)

    def update_event(self, evidence_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        if self._backend is None:
            return None
        existing = self._backend.get_record("evidence_items", evidence_id)
        if existing is None:
            return None
        payload = dict(existing)
        payload.update(updates)
        payload["id"] = evidence_id
        payload["evidence_id"] = evidence_id
        payload["finding_id"] = evidence_id
        return self._backend.upsert_record("evidence_items", evidence_id, payload)

    def link_finding(self, evidence_id: str, finding_id: str) -> dict[str, Any] | None:
        existing = self.get_event(evidence_id)
        if existing is None:
            return None
        linked = _string_list(existing.get("linked_finding_ids"))
        if finding_id not in linked:
            linked.append(finding_id)
        return self.update_event(evidence_id, {"linked_finding_ids": linked})

    def list_events(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if self._backend is not None:
            events = self._backend.list_records("evidence_items")
            return events[:limit]
        lines = self.path.read_text(encoding="utf-8").splitlines()
        events = []
        for line in lines[-limit:]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items
