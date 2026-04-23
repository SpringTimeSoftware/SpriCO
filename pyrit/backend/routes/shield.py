"""SpriCO Shield runtime screening API."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from pyrit.backend.sprico.shield import SpriCOShieldService

router = APIRouter(tags=["shield"])
_service = SpriCOShieldService()


class ShieldMessage(BaseModel):
    role: str
    content: str


class ShieldCheckRequest(BaseModel):
    messages: list[ShieldMessage]
    project_id: Optional[str] = None
    target_id: Optional[str] = None
    policy_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload: bool = False
    breakdown: bool = True
    dev_info: bool = False


@router.post("/shield/check")
async def shield_check(request: ShieldCheckRequest) -> dict[str, Any]:
    try:
        return _service.check(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
