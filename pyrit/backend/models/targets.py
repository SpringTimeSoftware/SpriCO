# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Target instance models.

Targets have two concepts:
- Types: Static metadata bundled with frontend (from registry)
- Instances: Runtime objects created via API with specific configuration

This module defines the Instance models for runtime target management.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from pyrit.backend.models.common import PaginationInfo


class TargetInstance(BaseModel):
    """
    A runtime target instance.

    Created either by an initializer (at startup) or by user (via API).
    Also used as the create-target response (same shape as GET).
    """

    target_registry_name: str = Field(..., description="Target registry key (e.g., 'azure_openai_chat')")
    display_name: Optional[str] = Field(None, description="User-facing display label for the target")
    target_type: str = Field(..., description="Target class name (e.g., 'OpenAIChatTarget')")
    endpoint: Optional[str] = Field(None, description="Target endpoint URL")
    model_name: Optional[str] = Field(None, description="Model or deployment name")
    temperature: Optional[float] = Field(None, description="Temperature parameter for generation")
    top_p: Optional[float] = Field(None, description="Top-p parameter for generation")
    max_requests_per_minute: Optional[int] = Field(None, description="Maximum requests per minute")
    supports_multi_turn: bool = Field(True, description="Whether the target supports multi-turn conversation history")
    target_specific_params: Optional[dict[str, Any]] = Field(None, description="Additional target-specific parameters")
    is_active: bool = Field(False, description="Whether this target is currently active")
    created_at: Optional[str] = Field(None, description="Timestamp when the target was saved")
    persistence_scope: Optional[str] = Field(
        None,
        description="Persistence classification such as 'saved' for SQLite-backed targets or 'runtime' for initializer-only targets",
    )
    credential_strategy: Optional[str] = Field(
        None,
        description="How sensitive credentials are handled for this target",
    )
    is_archived: bool = Field(False, description="Whether this target has been archived")
    archived_at: Optional[str] = Field(None, description="Timestamp when the target was archived")


class TargetListResponse(BaseModel):
    """Response for listing target instances."""

    items: list[TargetInstance] = Field(..., description="List of target instances")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


class CreateTargetRequest(BaseModel):
    """Request to create a new target instance."""

    type: str = Field(..., description="Target type (e.g., 'OpenAIChatTarget')")
    display_name: Optional[str] = Field(None, description="Optional user-facing display label")
    params: dict[str, Any] = Field(default_factory=dict, description="Target constructor parameters")


class UpdateTargetConfigRequest(BaseModel):
    """Patch request for editable target configuration fields."""

    display_name: Optional[str] = Field(None, description="Updated user-facing display label")
    special_instructions: Optional[str] = Field(None, description="Updated special/system instructions")


class ArchiveTargetRequest(BaseModel):
    """Request to archive a saved target without deleting its stored configuration."""

    reason: Optional[str] = Field(None, description="Optional archive reason")


class TargetConfigView(BaseModel):
    """Readable saved target configuration for inspection in the existing target UI."""

    target_registry_name: str = Field(..., description="Saved target instance identifier")
    display_name: str = Field(..., description="User-facing display label")
    target_type: str = Field(..., description="Target class name")
    endpoint: Optional[str] = Field(None, description="Saved endpoint URL")
    model_name: Optional[str] = Field(None, description="Saved model or deployment name")
    retrieval_store_id: Optional[str] = Field(None, description="Saved retrieval store identifier")
    retrieval_mode: Optional[str] = Field(None, description="Saved retrieval mode")
    masked_api_key: Optional[str] = Field(None, description="Masked API key or token")
    special_instructions: Optional[str] = Field(None, description="Saved special instructions as configured")
    provider_settings: dict[str, Any] = Field(default_factory=dict, description="Additional saved provider-specific settings")
    runtime_summary: Optional[dict[str, Any]] = Field(
        None,
        description="Low-noise runtime config summary derived from the loaded target object",
    )
    created_at: Optional[str] = Field(None, description="When the target was first saved")
    updated_at: Optional[str] = Field(None, description="When the target was last updated")
