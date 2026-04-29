"""Unified run registry APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from pyrit.backend.sprico.runs import SpriCORunRegistry

router = APIRouter(tags=["runs"])
_registry = SpriCORunRegistry()


@router.get("/runs")
async def list_runs(
    limit: int = Query(250, ge=1, le=2000),
    run_type: str | None = None,
    target_id: str | None = None,
    source_page: str | None = None,
    status_value: str | None = Query(None, alias="status"),
    final_verdict: str | None = None,
) -> list[dict[str, Any]]:
    return _registry.list_runs(
        limit=limit,
        run_type=run_type,
        target_id=target_id,
        source_page=source_page,
        status=status_value,
        final_verdict=final_verdict,
    )


@router.get("/runs/summary")
async def get_runs_summary() -> dict[str, Any]:
    return _registry.summary()


@router.get("/runs/by-target/{target_id}")
async def get_runs_by_target(target_id: str, limit: int = Query(250, ge=1, le=2000)) -> list[dict[str, Any]]:
    return _registry.list_runs(limit=limit, target_id=target_id)


@router.get("/runs/{run_id}/evidence")
async def get_run_evidence(run_id: str, limit: int = Query(500, ge=1, le=5000)) -> list[dict[str, Any]]:
    run = _registry.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")
    return _registry.evidence_for_run(run_id, limit=limit)


@router.get("/runs/{run_id}/findings")
async def get_run_findings(run_id: str, limit: int = Query(500, ge=1, le=5000)) -> list[dict[str, Any]]:
    run = _registry.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")
    return _registry.findings_for_run(run_id, limit=limit)


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    run = _registry.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found")
    return run
