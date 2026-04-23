"""SpriCO Red objective and scan APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from pyrit.backend.services.target_service import get_target_service
from pyrit.backend.sprico.red import METADATA_ONLY_ENGINES, MOCK_HOSPITAL_TARGET_ID, REAL_TARGET_ENGINES, SpriCORedStore

router = APIRouter(tags=["red"])
_store = SpriCORedStore()


class RedScanRequest(BaseModel):
    target_id: str = ""
    objective_ids: list[str] = Field(default_factory=list)
    policy_id: str = "policy_hospital_strict_v1"
    engine: str = "sprico"
    max_turns: int = Field(default=5, ge=1, le=100)
    max_objectives: int = Field(default=10, ge=1, le=100)
    converters: list[str] = Field(default_factory=list)
    scorers: list[str] = Field(default_factory=list)
    recon_context: dict[str, Any] = Field(default_factory=dict)
    strategies: list[str] = Field(default_factory=list)
    policy_context: dict[str, Any] = Field(default_factory=dict)
    permission_attestation: bool = False


class RedCompareRequest(BaseModel):
    scan_id: str


@router.get("/red/objectives")
async def red_objectives() -> list[dict[str, Any]]:
    return _store.objectives()


@router.post("/red/scans", status_code=status.HTTP_201_CREATED)
async def create_red_scan(request: RedScanRequest) -> dict[str, Any]:
    payload = request.model_dump()
    target_id = request.target_id.strip()
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_id is required for Red Team Campaigns. Use mock_hospital_target for demo scans.",
        )
    payload["target_id"] = target_id

    if target_id != MOCK_HOSPITAL_TARGET_ID:
        if not request.permission_attestation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must confirm authorization before running this scan.",
            )
        engine = str(request.engine or "sprico")
        if engine == "garak":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "garak is a scanner evidence engine in this phase. Run garak diagnostics separately; "
                    "Red Team Campaigns real target execution supports SpriCO/PyRIT target paths only."
                ),
            )
        if engine in METADATA_ONLY_ENGINES or "deepteam" in engine or "promptfoo" in engine:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This engine is registered as metadata/evidence only and cannot execute campaigns yet.",
            )
        if engine not in REAL_TARGET_ENGINES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported Red Team Campaigns engine '{engine}'.",
            )

        target_config = await get_target_service().get_target_config_async(target_registry_name=target_id)
        if target_config is None or not target_config.endpoint:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected target is missing an endpoint and cannot be used for real campaign execution.",
            )
        payload["_target_config"] = target_config.model_dump()
    try:
        return _store.create_scan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/red/scans")
async def list_red_scans() -> list[dict[str, Any]]:
    return _store.list_scans()


@router.get("/red/scans/{scan_id}")
async def get_red_scan(scan_id: str) -> dict[str, Any]:
    scan = _store.get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Red scan '{scan_id}' not found")
    return scan


@router.get("/red/scans/{scan_id}/results")
async def get_red_scan_results(scan_id: str) -> dict[str, Any]:
    scan = _store.get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Red scan '{scan_id}' not found")
    return {"scan_id": scan_id, "results": scan.get("results") or [], "risk": scan.get("risk") or {}}


@router.post("/red/scans/{scan_id}/compare")
async def compare_red_scans(scan_id: str, request: RedCompareRequest) -> dict[str, Any]:
    comparison = _store.compare(scan_id, request.scan_id)
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or both Red scans were not found")
    return comparison
