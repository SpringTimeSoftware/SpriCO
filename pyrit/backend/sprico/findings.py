"""Normalized actionable Findings for SpriCO."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pyrit.backend.sprico.evidence_store import SpriCOEvidenceStore
from pyrit.backend.sprico.storage import StorageBackend, get_storage_backend

HIGH_RISKS = {"HIGH", "CRITICAL"}
HIGH_SENSITIVITY = {"HIGH", "CRITICAL"}


def finding_requires_action(
    *,
    final_verdict: Any,
    violation_risk: Any,
    data_sensitivity: Any,
    policy_context: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    verdict = str(final_verdict or "").upper()
    risk = str(violation_risk or "").upper()
    sensitivity = str(data_sensitivity or "").upper()
    context = dict(policy_context or {})
    extra = dict(metadata or {})
    escalation = any(
        bool(source.get("requires_escalation"))
        for source in (context, extra)
        if isinstance(source, dict)
    )
    return bool(
        verdict == "FAIL"
        or risk in HIGH_RISKS
        or (verdict == "NEEDS_REVIEW" and sensitivity in HIGH_SENSITIVITY)
        or escalation
    )


class SpriCOFindingStore:
    def __init__(self, backend: StorageBackend | None = None, evidence_store: SpriCOEvidenceStore | None = None) -> None:
        self._backend = backend or get_storage_backend()
        self._evidence_store = evidence_store or SpriCOEvidenceStore(backend=self._backend)

    def sync_existing_records(self) -> list[dict[str, Any]]:
        synchronized: list[dict[str, Any]] = []
        for record in self._backend.list_records("findings"):
            normalized = normalize_finding_record(record)
            self._backend.upsert_record("findings", normalized["finding_id"], normalized)
            synchronized.append(normalized)
        return synchronized

    def upsert_finding(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_finding_record(payload)
        self._backend.upsert_record("findings", normalized["finding_id"], normalized)
        for evidence_id in normalized.get("evidence_ids") or []:
            self._evidence_store.link_finding(evidence_id, normalized["finding_id"])
        return normalized

    def list_findings(
        self,
        *,
        limit: int = 250,
        run_id: str | None = None,
        target_id: str | None = None,
        source_page: str | None = None,
        engine: str | None = None,
        policy_id: str | None = None,
        domain: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        review_status: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        findings = [normalize_finding_record(record) for record in self._backend.list_records("findings")]
        if run_id:
            findings = [item for item in findings if run_id in _run_identifiers(item)]
        if target_id:
            findings = [item for item in findings if str(item.get("target_id") or "") == target_id]
        if source_page:
            findings = [item for item in findings if str(item.get("source_page") or "").lower() == source_page.lower()]
        if engine:
            needle = engine.lower()
            findings = [
                item
                for item in findings
                if any(
                    needle in candidate
                    for candidate in {
                        str(item.get("engine_id") or "").lower(),
                        str(item.get("engine_name") or "").lower(),
                    }
                )
            ]
        if policy_id:
            findings = [item for item in findings if str(item.get("policy_id") or "") == policy_id]
        if domain:
            findings = [item for item in findings if str(item.get("domain") or "").lower() == domain.lower()]
        if severity:
            findings = [item for item in findings if str(item.get("severity") or "").upper() == severity.upper()]
        if status:
            findings = [item for item in findings if str(item.get("status") or "").lower() == status.lower()]
        if review_status:
            findings = [item for item in findings if str(item.get("review_status") or "").lower() == review_status.lower()]
        if search:
            needle = search.lower().strip()
            findings = [
                item
                for item in findings
                if needle in " ".join(
                    str(item.get(key) or "")
                    for key in ("title", "description", "root_cause", "remediation", "target_name", "policy_name")
                ).lower()
            ]
        findings.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return findings[:limit]

    def get_finding(self, finding_id: str) -> dict[str, Any] | None:
        record = self._backend.get_record("findings", finding_id)
        return normalize_finding_record(record) if record is not None else None


def normalize_finding_record(record: dict[str, Any] | None) -> dict[str, Any]:
    now = _utc_now()
    payload = dict(record or {})
    finding_id = str(payload.get("finding_id") or payload.get("id") or f"finding_{now}")
    evidence_ids = _unique_strings(payload.get("evidence_ids") or payload.get("linked_evidence_ids"))
    if not evidence_ids:
        evidence_ids = _unique_strings(payload.get("evidence_id"))
    policy_context = _as_dict(payload.get("policy_context"))
    legacy_source_ref = _as_dict(payload.get("legacy_source_ref"))
    matched_signals = _as_list(payload.get("matched_signals"))
    prompt_excerpt = str(payload.get("prompt_excerpt") or payload.get("raw_input") or payload.get("prompt") or "")
    response_excerpt = str(payload.get("response_excerpt") or payload.get("raw_output") or payload.get("response") or "")
    severity = str(payload.get("severity") or payload.get("violation_risk") or payload.get("risk") or "MEDIUM").upper()
    source_page = str(payload.get("source_page") or _source_page_from_payload(payload))
    engine_id = str(payload.get("engine_id") or payload.get("engine") or payload.get("source") or "sprico")
    engine_name = str(payload.get("engine_name") or payload.get("source") or engine_id)
    description = str(payload.get("description") or payload.get("summary") or payload.get("explanation") or "").strip()
    title = str(payload.get("title") or "").strip() or _default_title(payload, severity=severity)
    domain = (
        str(payload.get("domain") or "").strip()
        or str(policy_context.get("policy_domain") or policy_context.get("target_domain") or payload.get("target_domain") or "generic")
    )
    normalized = {
        **payload,
        "id": finding_id,
        "finding_id": finding_id,
        "run_id": payload.get("run_id"),
        "run_type": payload.get("run_type"),
        "evidence_ids": evidence_ids,
        "target_id": payload.get("target_id"),
        "target_name": payload.get("target_name"),
        "target_type": payload.get("target_type"),
        "source_page": source_page,
        "engine_id": engine_id,
        "engine_name": engine_name,
        "domain": domain,
        "policy_id": payload.get("policy_id"),
        "policy_name": payload.get("policy_name"),
        "category": payload.get("category") or payload.get("objective_id") or payload.get("source_type") or payload.get("evidence_type"),
        "severity": severity,
        "status": str(payload.get("status") or "open"),
        "title": title,
        "description": description or title,
        "root_cause": str(payload.get("root_cause") or payload.get("summary") or description or "").strip(),
        "remediation": str(payload.get("remediation") or _default_remediation(source_page)).strip(),
        "owner": payload.get("owner"),
        "review_status": str(payload.get("review_status") or "pending"),
        "created_at": str(payload.get("created_at") or now),
        "updated_at": str(payload.get("updated_at") or payload.get("created_at") or now),
        "final_verdict": payload.get("final_verdict") or payload.get("verdict") or payload.get("final_sprico_verdict"),
        "violation_risk": payload.get("violation_risk") or payload.get("risk"),
        "data_sensitivity": payload.get("data_sensitivity"),
        "matched_signals": matched_signals,
        "policy_context": policy_context,
        "prompt_excerpt": prompt_excerpt,
        "response_excerpt": response_excerpt,
        "legacy_source_ref": legacy_source_ref,
    }
    return normalized


def _source_page_from_payload(payload: dict[str, Any]) -> str:
    engine = str(payload.get("engine_id") or payload.get("engine") or payload.get("source") or "").lower()
    source_type = str(payload.get("source_type") or payload.get("evidence_type") or "").lower()
    if "garak" in engine or "scanner" in source_type:
        return "garak-scanner"
    if "red" in engine:
        return "red"
    if "shield" in engine:
        return "shield"
    if "interactive" in engine:
        return "chat"
    if "benchmark" in source_type:
        return "benchmark-library"
    if "audit" in engine:
        return "audit"
    return "findings"


def _default_title(payload: dict[str, Any], *, severity: str) -> str:
    source = payload.get("source") or payload.get("engine_name") or payload.get("engine_id") or "SpriCO"
    category = payload.get("objective_id") or payload.get("category") or payload.get("source_type") or payload.get("evidence_type") or "finding"
    return f"{source}: {category} ({severity})"


def _default_remediation(source_page: str) -> str:
    if source_page == "garak-scanner":
        return "Review the scanner evidence, tighten target controls, and rerun the selected scan scope."
    if source_page == "red":
        return "Review the campaign transcript, harden the target behavior, and rerun the affected objectives."
    if source_page == "shield":
        return "Review Shield policy context, confirm authorization boundaries, and adjust guardrails if needed."
    if source_page == "chat":
        return "Review the interactive transcript and update prompts, policies, or target controls before re-testing."
    return "Review the linked evidence and source run, then remediate the unsafe behavior before re-testing."


def _run_identifiers(record: dict[str, Any]) -> set[str]:
    identifiers = {str(record.get("run_id") or "").strip()}
    legacy = _as_dict(record.get("legacy_source_ref"))
    for key in ("id", "run_id", "scan_id", "conversation_id", "audit_run_id", "attack_result_id"):
        text = str(legacy.get(key) or "").strip()
        if text:
            identifiers.add(text)
    return {item for item in identifiers if item}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _unique_strings(value: Any) -> list[str]:
    if value is None:
        return []
    candidates = value if isinstance(value, list) else [value]
    items: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
