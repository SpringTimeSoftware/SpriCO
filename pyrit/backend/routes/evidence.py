"""SpriCO evidence APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from pyrit.backend.sprico.evidence_store import SpriCOEvidenceStore

router = APIRouter(tags=["evidence"])
_store = SpriCOEvidenceStore()


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
) -> list[dict[str, Any]]:
    events = _store.list_events(limit=limit)
    if evidence_id:
        events = [item for item in events if item.get("finding_id") == evidence_id or item.get("id") == evidence_id]
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
    if risk:
        events = [item for item in events if str(item.get("violation_risk") or "").upper() == risk.upper()]
    if final_verdict:
        events = [
            item for item in events
            if str(item.get("final_verdict") or (item.get("sprico_final_verdict") or {}).get("verdict") or "").upper()
            == final_verdict.upper()
        ]
    return events
