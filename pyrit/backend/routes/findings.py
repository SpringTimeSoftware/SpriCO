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
    return _store.list_findings(
        limit=limit,
        run_id=run_id,
        target_id=target_id,
        source_page=source_page,
        engine=engine,
        policy_id=policy_id,
        domain=domain,
        severity=severity,
        status=status_value,
        review_status=review_status,
        search=search,
    )


@router.get("/findings/{finding_id}")
async def get_finding(finding_id: str) -> dict[str, Any]:
    _run_registry.backfill()
    finding = _store.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Finding '{finding_id}' not found")
    return finding
