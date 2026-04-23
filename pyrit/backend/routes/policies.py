"""SpriCO policy APIs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from pyrit.backend.sprico.policy_store import SpriCOPolicyStore
from pyrit.backend.sprico.shield import SpriCOShieldService

router = APIRouter(tags=["policies"])
_store = SpriCOPolicyStore()
_shield = SpriCOShieldService(_store)


class PolicyRequest(BaseModel):
    id: Optional[str] = None
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    mode: str = "UNKNOWN"
    sensitivity: str = "L2"
    target_domain: str = "general"
    enabled_guardrails: dict[str, bool] = Field(default_factory=dict)
    apply_to: list[str] = Field(default_factory=list)
    custom_detectors: list[dict[str, Any]] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    deny_domains: list[str] = Field(default_factory=list)
    allow_list: list[dict[str, Any]] = Field(default_factory=list)
    deny_list: list[dict[str, Any]] = Field(default_factory=list)
    retention: dict[str, Any] = Field(default_factory=dict)
    redaction: dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = None


class PolicySimulationRequest(BaseModel):
    messages: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/policies")
async def list_policies() -> list[dict[str, Any]]:
    return _store.list_policies()


@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(request: PolicyRequest) -> dict[str, Any]:
    try:
        return _store.create_policy(request.model_dump(exclude_none=True, exclude_defaults=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str) -> dict[str, Any]:
    policy = _store.get_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found")
    return policy


@router.patch("/policies/{policy_id}")
async def patch_policy(policy_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    try:
        policy = _store.patch_policy(policy_id, patch)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found")
    return policy


@router.post("/policies/{policy_id}/simulate")
async def simulate_policy(policy_id: str, request: PolicySimulationRequest) -> dict[str, Any]:
    policy = _store.get_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found")
    return _shield.check(
        {
            "messages": request.messages,
            "policy_id": policy_id,
            "metadata": request.metadata,
            "payload": True,
            "breakdown": True,
            "dev_info": True,
        }
    )


@router.get("/policies/{policy_id}/audit-history")
async def policy_audit_history(policy_id: str) -> dict[str, Any]:
    history = _store.audit_history(policy_id)
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found")
    return {"policy_id": policy_id, "audit_history": history}


@router.get("/policies/{policy_id}/versions")
async def policy_versions(policy_id: str) -> dict[str, Any]:
    if _store.get_policy(policy_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found")
    return {"policy_id": policy_id, "versions": _store.policy_versions(policy_id)}
