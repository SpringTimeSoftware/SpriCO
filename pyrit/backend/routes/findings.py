"""Unified platform Findings APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from pyrit.backend.sprico.findings import SpriCOFindingStore
from pyrit.backend.sprico.runs import SpriCORunRegistry

router = APIRouter(tags=["findings"])
_store = SpriCOFindingStore()
_run_registry = SpriCORunRegistry(finding_store=_store)


@router.get("/findings")
async def list_findings(
    limit: int = Query(250, ge=1, le=2000),
    run_id: str | None = None,
    target_id: str | None = None,
    source_page: str | None = None,
    engine: str | None = None,
    policy_id: str | None = None,
    domain: str | None = None,
    severity: str | None = None,
    status_value: str | None = Query(None, alias="status"),
    review_status: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    _run_registry.backfill()
    findings = [_run_registry.enrich_finding_record(item) for item in _store.list_findings(limit=10_000)]
    if run_id:
        findings = [item for item in findings if run_id in {str(item.get("run_id") or "").strip(), str((item.get("legacy_source_ref") or {}).get("run_id") or "").strip(), str(item.get("scan_id") or "").strip(), str(item.get("conversation_id") or "").strip()}]
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
    if isinstance(status_value, str) and status_value:
        findings = [item for item in findings if str(item.get("status") or "").lower() == status_value.lower()]
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
    return findings[:limit]


@router.get("/findings/{finding_id}")
async def get_finding(finding_id: str) -> dict[str, Any]:
    _run_registry.backfill()
    finding = _store.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Finding '{finding_id}' not found")
    return _run_registry.enrich_finding_record(finding)
