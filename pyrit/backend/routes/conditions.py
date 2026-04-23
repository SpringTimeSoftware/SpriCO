"""SpriCO custom condition lifecycle APIs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from pyrit.backend.sprico.conditions import (
    ALLOWED_CONDITION_TYPES,
    ConditionLifecycleError,
    SpriCOConditionStore,
)

router = APIRouter(tags=["conditions"])
_store = SpriCOConditionStore()


class ConditionRequest(BaseModel):
    condition_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    condition_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    author: str = "system"
    domain: str = "generic"
    policy_modes: list[str] = Field(default_factory=lambda: ["REDTEAM_STRICT"])
    data_sensitivity: str = "HIGH"
    violation_risk: str = "HIGH"
    requires_authorization: bool = True
    requires_minimum_necessary: bool = True
    rollback_target: Optional[str] = None


class ConditionSimulationRequest(BaseModel):
    text: str = ""
    policy_context: dict[str, Any] = Field(default_factory=dict)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    actor: Optional[str] = None


class ConditionTestRequest(BaseModel):
    id: Optional[str] = None
    name: str = "Condition test"
    input_text: str
    expected_match: bool
    policy_context: dict[str, Any] = Field(default_factory=dict)
    actor: Optional[str] = None


class ConditionApprovalRequest(BaseModel):
    approver: str
    notes: Optional[str] = None


class ConditionActionRequest(BaseModel):
    actor: Optional[str] = None
    reason: Optional[str] = None
    rollback_target: Optional[str] = None


@router.get("/conditions/types")
async def condition_types() -> dict[str, Any]:
    return {
        "allowed_condition_types": sorted(ALLOWED_CONDITION_TYPES),
        "final_verdict_authority": "sprico_policy_decision_engine",
        "code_execution_allowed": False,
    }


@router.get("/conditions")
async def list_conditions() -> list[dict[str, Any]]:
    return _store.list_conditions()


@router.post("/conditions", status_code=status.HTTP_201_CREATED)
async def create_condition(request: ConditionRequest) -> dict[str, Any]:
    try:
        return _store.create_condition(request.model_dump(exclude_none=True))
    except ConditionLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/conditions/{condition_id}")
async def get_condition(condition_id: str) -> dict[str, Any]:
    condition = _store.get_condition(condition_id)
    if condition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found")
    return condition


@router.post("/conditions/{condition_id}/simulate")
async def simulate_condition(condition_id: str, request: ConditionSimulationRequest) -> dict[str, Any]:
    try:
        return _store.simulate_condition(condition_id, request.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found") from exc


@router.post("/conditions/{condition_id}/tests")
async def add_condition_test(condition_id: str, request: ConditionTestRequest) -> dict[str, Any]:
    try:
        return _store.add_test_case(condition_id, request.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found") from exc
    except ConditionLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/conditions/{condition_id}/approve")
async def approve_condition(condition_id: str, request: ConditionApprovalRequest) -> dict[str, Any]:
    try:
        return _store.approve_condition(condition_id, request.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found") from exc
    except ConditionLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/conditions/{condition_id}/activate")
async def activate_condition(condition_id: str, request: ConditionActionRequest | None = None) -> dict[str, Any]:
    try:
        return _store.activate_condition(condition_id, request.model_dump(exclude_none=True) if request else {})
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found") from exc
    except ConditionLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/conditions/{condition_id}/retire")
async def retire_condition(condition_id: str, request: ConditionActionRequest | None = None) -> dict[str, Any]:
    try:
        return _store.retire_condition(condition_id, request.model_dump(exclude_none=True) if request else {})
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found") from exc


@router.post("/conditions/{condition_id}/rollback")
async def rollback_condition(condition_id: str, request: ConditionActionRequest) -> dict[str, Any]:
    try:
        return _store.rollback_condition(condition_id, request.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found") from exc
    except ConditionLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/conditions/{condition_id}/versions")
async def condition_versions(condition_id: str) -> dict[str, Any]:
    if _store.get_condition(condition_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found")
    return {"condition_id": condition_id, "versions": _store.versions(condition_id)}


@router.get("/conditions/{condition_id}/audit-history")
async def condition_audit_history(condition_id: str) -> dict[str, Any]:
    try:
        return {"condition_id": condition_id, "audit_history": _store.audit_history(condition_id)}
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Condition '{condition_id}' not found") from exc
