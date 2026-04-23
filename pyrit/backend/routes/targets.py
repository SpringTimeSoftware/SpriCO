# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Target API routes.

Provides endpoints for managing target instances.
Target types are set at app startup via initializers - you cannot add new types at runtime.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from pyrit.backend.models.common import ProblemDetail
from pyrit.backend.models.targets import (
    ArchiveTargetRequest,
    CreateTargetRequest,
    TargetConfigView,
    TargetInstance,
    TargetListResponse,
    UpdateTargetConfigRequest,
)
from pyrit.backend.services.target_service import get_target_service

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get(
    "",
    response_model=TargetListResponse,
    responses={
        500: {"model": ProblemDetail, "description": "Internal server error"},
    },
)
async def list_targets(
    limit: int = Query(50, ge=1, le=200, description="Maximum items per page"),
    cursor: Optional[str] = Query(None, description="Pagination cursor (target_registry_name)"),
    include_archived: bool = Query(False, description="Include archived targets in the response"),
) -> TargetListResponse:
    """
    List target instances with pagination.

    Returns paginated target instances.

    Returns:
        TargetListResponse: Paginated list of target instances.
    """
    service = get_target_service()
    return await service.list_targets_async(limit=limit, cursor=cursor, include_archived=include_archived)


@router.get(
    "/active",
    response_model=TargetInstance,
    responses={
        404: {"model": ProblemDetail, "description": "No active target configured"},
    },
)
async def get_active_target() -> TargetInstance:
    """Get the currently active target persisted by the backend."""
    service = get_target_service()
    target = await service.get_active_target_async()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active target configured",
        )
    return target


@router.post(
    "",
    response_model=TargetInstance,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ProblemDetail, "description": "Invalid target type or parameters"},
    },
)
async def create_target(request: CreateTargetRequest) -> TargetInstance:
    """
    Create a new target instance.

    Instantiates a target with the given type and parameters.
    The target becomes available for use in attacks.

    Note: Sensitive parameters (API keys, tokens) are filtered from the response.

    Returns:
        CreateTargetResponse: The created target instance details.
    """
    service = get_target_service()

    try:
        return await service.create_target_async(request=request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create target: {str(e)}",
        ) from e


@router.post(
    "/{target_registry_name}/activate",
    response_model=TargetInstance,
    responses={
        404: {"model": ProblemDetail, "description": "Target not found"},
    },
)
async def activate_target(target_registry_name: str) -> TargetInstance:
    """Persist the selected active target so it survives reloads and restarts."""
    service = get_target_service()
    target = await service.activate_target_async(target_registry_name=target_registry_name)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{target_registry_name}' not found",
        )
    return target


@router.get(
    "/{target_registry_name}/config",
    response_model=TargetConfigView,
    responses={
        404: {"model": ProblemDetail, "description": "Target not found"},
    },
)
async def get_target_config(target_registry_name: str) -> TargetConfigView:
    """Return the saved target configuration plus a low-noise runtime summary."""
    service = get_target_service()
    config = await service.get_target_config_async(target_registry_name=target_registry_name)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{target_registry_name}' not found",
        )
    return config


@router.patch(
    "/{target_registry_name}/config",
    response_model=TargetConfigView,
    responses={
        404: {"model": ProblemDetail, "description": "Target not found"},
    },
)
async def update_target_config(target_registry_name: str, request: UpdateTargetConfigRequest) -> TargetConfigView:
    """Update editable saved target configuration fields."""
    service = get_target_service()
    config = await service.update_target_config_async(
        target_registry_name=target_registry_name,
        display_name=request.display_name,
        special_instructions=request.special_instructions,
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{target_registry_name}' not found",
        )
    return config


@router.post(
    "/{target_registry_name}/archive",
    response_model=TargetInstance,
    responses={
        404: {"model": ProblemDetail, "description": "Target not found"},
    },
)
async def archive_target(target_registry_name: str, request: ArchiveTargetRequest | None = None) -> TargetInstance:
    """Archive a saved target without deleting its stored configuration."""
    service = get_target_service()
    target = await service.archive_target_async(
        target_registry_name=target_registry_name,
        reason=request.reason if request else None,
    )
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{target_registry_name}' not found",
        )
    return target


@router.get(
    "/{target_registry_name}",
    response_model=TargetInstance,
    responses={
        404: {"model": ProblemDetail, "description": "Target not found"},
    },
)
async def get_target(target_registry_name: str) -> TargetInstance:
    """
    Get a target instance by registry name.

    Returns:
        TargetInstance: The target instance details.
    """
    service = get_target_service()

    target = await service.get_target_async(target_registry_name=target_registry_name)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target '{target_registry_name}' not found",
        )

    return target
