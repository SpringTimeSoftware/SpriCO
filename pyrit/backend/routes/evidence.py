"""SpriCO evidence APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from pyrit.backend.sprico.evidence_store import SpriCOEvidenceStore
from pyrit.backend.sprico.runs import SpriCORunRegistry

router = APIRouter(tags=["evidence"])
_store = SpriCOEvidenceStore()
_run_registry = SpriCORunRegistry(evidence_store=_store)


@router.get("/evidence")
async def list_evidence(
    limit: int = Query(100, ge=1, le=1000),
    scan_id: str | None = None,
    engine: str | None = None,
    engine_type: str | None = None,
    policy_id: str | None = None,
    risk: str | None = None,
    final_verdict: str | None = None,
    evidence_id: str | None = None,
    run_id: str | None = None,
    target_id: str | None = None,
    source_page: str | None = None,
) -> list[dict[str, Any]]:
    _run_registry.backfill()
    events = [_run_registry.enrich_evidence_event(item) for item in _store.list_events(limit=10_000)]
    if evidence_id:
        events = [item for item in events if item.get("finding_id") == evidence_id or item.get("evidence_id") == evidence_id or item.get("id") == evidence_id]
    if run_id:
        matched_run = _run_registry.get_run(run_id)
        if matched_run is not None:
            run_refs = {str(matched_run.get("run_id") or "")}
            run_refs.update(str(value) for value in (matched_run.get("legacy_source_ref") or {}).values() if str(value or "").strip())
            events = [
                item for item in events
                if str(item.get("run_id") or "") in run_refs
                or str(item.get("scan_id") or "") in run_refs
                or str(item.get("conversation_id") or "") in run_refs
                or str(item.get("session_id") or "") in run_refs
            ]
        else:
            events = [item for item in events if str(item.get("run_id") or "") == run_id]
    if scan_id:
        events = [
            item for item in events
            if scan_id in {
                str(item.get("scan_id") or ""),
                str(item.get("session_id") or ""),
                str(item.get("conversation_id") or ""),
                str((item.get("raw_result") or {}).get("conversation_id") or ""),
                str((item.get("raw_engine_result") or {}).get("conversation_id") or ""),
            }
        ]
    if engine:
        engine_lower = engine.lower()
        events = [
            item for item in events
            if any(engine_lower in candidate for candidate in {
                str(item.get("engine") or "").lower(),
                str(item.get("engine_id") or "").lower(),
                str(item.get("engine_name") or "").lower(),
            })
        ]
    if engine_type:
        events = [item for item in events if str(item.get("engine_type") or "").lower() == engine_type.lower()]
    if policy_id:
        events = [item for item in events if item.get("policy_id") == policy_id]
    if target_id:
        events = [item for item in events if str(item.get("target_id") or "") == target_id]
    if source_page:
        events = [item for item in events if str(item.get("source_page") or "").lower() == source_page.lower()]
    if risk:
        events = [item for item in events if str(item.get("violation_risk") or "").upper() == risk.upper()]
    if final_verdict:
        events = [
            item for item in events
            if str(item.get("final_verdict") or (item.get("sprico_final_verdict") or {}).get("verdict") or "").upper()
            == final_verdict.upper()
        ]
    return events[:limit]
