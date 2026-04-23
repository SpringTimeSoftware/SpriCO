"""SpriCO project APIs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from pyrit.backend.sprico.policy_store import SpriCOPolicyStore

router = APIRouter(tags=["projects"])
_store = SpriCOPolicyStore()


class ProjectRequest(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    application_id: Optional[str] = None
    environment: str = "dev"
    target_ids: list[str] = Field(default_factory=list)
    policy_id: str = "policy_public_default"
    metadata_tags: dict[str, Any] = Field(default_factory=dict)


@router.get("/projects")
async def list_projects() -> list[dict[str, Any]]:
    return _store.list_projects()


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(request: ProjectRequest) -> dict[str, Any]:
    try:
        return _store.create_project(request.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    project = _store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    return project


@router.patch("/projects/{project_id}")
async def patch_project(project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    try:
        project = _store.patch_project(project_id, patch)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    return project
