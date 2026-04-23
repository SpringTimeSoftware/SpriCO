# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Target service for managing runtime and persisted target instances.
"""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from typing import Any, Optional

from pyrit import prompt_target
from pyrit.backend.mappers.target_mappers import target_object_to_instance
from pyrit.backend.models.common import PaginationInfo
from pyrit.backend.models.targets import CreateTargetRequest, TargetConfigView, TargetInstance, TargetListResponse
from pyrit.backend.services.persistent_target_store import PersistentTargetStore
from pyrit.prompt_target import PromptTarget
from pyrit.registry.instance_registries import TargetRegistry

logger = logging.getLogger(__name__)


def _build_target_class_registry() -> dict[str, type]:
    """Build a mapping of PromptTarget class names to their classes."""
    registry: dict[str, type] = {}
    for name in prompt_target.__all__:
        cls = getattr(prompt_target, name, None)
        if cls is not None and isinstance(cls, type) and issubclass(cls, PromptTarget):
            registry[name] = cls
    return registry


_TARGET_CLASS_REGISTRY: dict[str, type] = _build_target_class_registry()


class TargetService:
    """Service layer for target creation, persistence, activation, and lookup."""

    def __init__(self) -> None:
        self._registry = TargetRegistry.get_registry_singleton()
        self._store = PersistentTargetStore()
        self._initialized = False

    def initialize_persistent_targets(self) -> None:
        """Ensure SQLite-backed target storage is initialized and restored into the registry."""
        if self._initialized:
            return

        self._store.initialize()
        self._sync_persistent_targets()
        self._initialized = True

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize_persistent_targets()
            return

        # The target registry is process-local while the target store is shared.
        # Re-sync on normal requests so a target created by another worker becomes
        # available for activation/listing without requiring a restart or page reload.
        self._sync_persistent_targets()

    def _sync_persistent_targets(self) -> None:
        for target_record in self._store.get_restorable_targets():
            target_registry_name = str(target_record["target_registry_name"])
            if self._registry.get_instance_by_name(target_registry_name) is not None:
                continue

            try:
                target_class = self._get_target_class(target_type=str(target_record["target_type"]))
                target_obj = target_class(**target_record["constructor_params"])
            except Exception as exc:
                logger.error(
                    "Failed to restore persisted target '%s' into TargetRegistry",
                    target_registry_name,
                    exc_info=exc,
                )
                continue

            self._registry.register_instance(target_obj, name=target_registry_name)
            logger.info("Restored persisted target '%s' into TargetRegistry", target_registry_name)

    def _get_target_class(self, *, target_type: str) -> type:
        cls = _TARGET_CLASS_REGISTRY.get(target_type)
        if cls is None:
            raise ValueError(
                f"Target type '{target_type}' not found. Available types: {sorted(_TARGET_CLASS_REGISTRY.keys())}"
            )
        return cls

    def _build_instance_from_object(self, *, target_registry_name: str, target_obj: Any) -> TargetInstance:
        saved = self._store.get_target(target_registry_name)
        return target_object_to_instance(
            target_registry_name=target_registry_name,
            target_obj=target_obj,
            display_name=saved.get("display_name") if saved else target_registry_name,
            is_active=self._store.get_active_target_name() == target_registry_name,
            created_at=saved.get("created_at") if saved else None,
            persistence_scope="saved" if saved else "runtime",
            credential_strategy=saved.get("credential_strategy") if saved else "runtime_only",
            is_archived=bool(saved.get("is_archived")) if saved else False,
            archived_at=saved.get("archived_at") if saved else None,
        )

    def _build_instance_from_saved_record(self, saved: dict[str, Any]) -> TargetInstance:
        return TargetInstance(
            target_registry_name=str(saved["target_registry_name"]),
            display_name=saved.get("display_name"),
            target_type=str(saved["target_type"]),
            endpoint=saved.get("endpoint"),
            model_name=saved.get("model_name"),
            target_specific_params=dict(saved.get("params") or {}) or None,
            is_active=bool(saved.get("is_active")) and not bool(saved.get("is_archived")),
            created_at=saved.get("created_at"),
            persistence_scope="saved",
            credential_strategy=saved.get("credential_strategy"),
            is_archived=bool(saved.get("is_archived")),
            archived_at=saved.get("archived_at"),
        )

    def _generate_target_registry_name(self, *, target_type: str) -> str:
        for _ in range(16):
            candidate = f"{target_type}::{uuid.uuid4().hex[:8]}"
            if self._registry.get_instance_by_name(candidate) is None and self._store.get_target(candidate) is None:
                return candidate
        raise ValueError(f"Failed to allocate a unique saved target name for '{target_type}'")

    def _build_runtime_summary(self, *, target_obj: Any) -> dict[str, Any]:
        target_type = target_obj.__class__.__name__
        special_instructions = getattr(target_obj, "_system_instructions", None)
        special_instructions_present = bool(isinstance(special_instructions, str) and special_instructions.strip())
        summary: dict[str, Any] = {
            "target_type": target_type,
            "endpoint": getattr(target_obj, "_endpoint", None),
            "model_name": getattr(target_obj, "_model_name", None),
            "retrieval_store_id": getattr(target_obj, "_retrieval_store_id", None),
            "retrieval_mode": getattr(target_obj, "_retrieval_mode", None),
            "api_key_present": bool(getattr(target_obj, "_api_key", None)),
            "special_instructions_present": special_instructions_present,
        }

        if target_type == "OpenAIVectorStoreTarget":
            extra_body = getattr(target_obj, "_extra_body_parameters", None)
            summary["instruction_transport"] = "responses.instructions"
            summary["request_includes_special_instructions"] = bool(
                isinstance(extra_body, dict) and extra_body.get("instructions")
            )
        elif target_type == "GeminiFileSearchTarget":
            summary["instruction_transport"] = "systemInstruction.parts[].text"
            summary["request_includes_special_instructions"] = special_instructions_present

        return {key: value for key, value in summary.items() if value is not None}

    async def get_target_config_async(self, *, target_registry_name: str) -> Optional[TargetConfigView]:
        self._ensure_initialized()
        snapshot = self._store.get_target_config_snapshot(target_registry_name)
        target_obj = self.get_target_object(target_registry_name=target_registry_name)
        if snapshot is None and target_obj is None:
            return None

        runtime_summary = self._build_runtime_summary(target_obj=target_obj) if target_obj is not None else None
        if snapshot is None:
            identifier_params = target_obj.get_identifier().params if target_obj is not None else {}
            params = dict(identifier_params or {})
            snapshot = {
                "target_registry_name": target_registry_name,
                "target_type": target_obj.__class__.__name__ if target_obj is not None else "PromptTarget",
                "display_name": target_registry_name,
                "endpoint": params.get("endpoint") or getattr(target_obj, "_endpoint", None),
                "model_name": params.get("model_name") or getattr(target_obj, "_model_name", None),
                "params": params,
                "created_at": None,
                "updated_at": None,
            }
        else:
            params = dict(snapshot.get("params") or {})

        masked_api_key = (
            params.get("api_key")
            or params.get("authorization")
            or params.get("access_token")
            or params.get("token")
        )
        provider_settings = {
            key: value
            for key, value in params.items()
            if key
            not in {
                "api_key",
                "authorization",
                "access_token",
                "token",
                "model_name",
                "endpoint",
                "retrieval_store_id",
                "retrieval_mode",
                "system_instructions",
            }
        }

        return TargetConfigView(
            target_registry_name=str(snapshot["target_registry_name"]),
            display_name=str(snapshot["display_name"]),
            target_type=str(snapshot["target_type"]),
            endpoint=snapshot.get("endpoint"),
            model_name=snapshot.get("model_name") or params.get("model_name"),
            retrieval_store_id=params.get("retrieval_store_id"),
            retrieval_mode=params.get("retrieval_mode"),
            masked_api_key=masked_api_key,
            special_instructions=params.get("system_instructions")
            or (getattr(target_obj, "_system_instructions", None) if target_obj is not None else None),
            provider_settings=provider_settings,
            runtime_summary=runtime_summary,
            created_at=snapshot.get("created_at"),
            updated_at=snapshot.get("updated_at"),
        )

    async def list_targets_async(
        self,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
        include_archived: bool = False,
    ) -> TargetListResponse:
        self._ensure_initialized()
        archived_names = {
            str(item["target_registry_name"])
            for item in self._store.list_targets(include_archived=True)
            if item.get("is_archived")
        }
        items = [
            self._build_instance_from_object(target_registry_name=name, target_obj=obj)
            for name, obj in self._registry.get_all_instances().items()
            if include_archived or name not in archived_names
        ]
        if include_archived:
            present = {item.target_registry_name for item in items}
            for saved in self._store.list_targets(include_archived=True):
                name = str(saved["target_registry_name"])
                if name in present:
                    continue
                items.append(self._build_instance_from_saved_record(saved))
        page, has_more = self._paginate(items, cursor, limit)
        next_cursor = page[-1].target_registry_name if has_more and page else None
        return TargetListResponse(
            items=page,
            pagination=PaginationInfo(limit=limit, has_more=has_more, next_cursor=next_cursor, prev_cursor=cursor),
        )

    @staticmethod
    def _paginate(items: list[TargetInstance], cursor: Optional[str], limit: int) -> tuple[list[TargetInstance], bool]:
        start_idx = 0
        if cursor:
            for i, item in enumerate(items):
                if item.target_registry_name == cursor:
                    start_idx = i + 1
                    break

        page = items[start_idx : start_idx + limit]
        has_more = len(items) > start_idx + limit
        return page, has_more

    async def get_target_async(self, *, target_registry_name: str) -> Optional[TargetInstance]:
        self._ensure_initialized()
        obj = self._registry.get_instance_by_name(target_registry_name)
        if obj is None:
            return None
        return self._build_instance_from_object(target_registry_name=target_registry_name, target_obj=obj)

    async def get_active_target_async(self) -> Optional[TargetInstance]:
        self._ensure_initialized()
        active_target_name = self._store.get_active_target_name()
        if not active_target_name:
            return None
        return await self.get_target_async(target_registry_name=active_target_name)

    def get_target_object(self, *, target_registry_name: str) -> Optional[Any]:
        self._ensure_initialized()
        return self._registry.get_instance_by_name(target_registry_name)

    async def create_target_async(self, *, request: CreateTargetRequest) -> TargetInstance:
        self._ensure_initialized()
        target_class = self._get_target_class(target_type=request.type)
        target_obj = target_class(**request.params)
        target_registry_name = self._generate_target_registry_name(target_type=request.type)
        display_name = (request.display_name or "").strip() or target_registry_name

        persisted = self._store.save_target(
            target_registry_name=target_registry_name,
            target_type=request.type,
            display_name=display_name,
            model_name=getattr(target_obj, "_model_name", None) or request.params.get("model_name"),
            endpoint=request.params.get("endpoint"),
            params=request.params,
        )
        self._registry.register_instance(target_obj, name=target_registry_name)

        return target_object_to_instance(
            target_registry_name=target_registry_name,
            target_obj=target_obj,
            display_name=str(persisted["display_name"]),
            is_active=bool(persisted["is_active"]),
            created_at=persisted.get("created_at"),
            persistence_scope="saved",
            credential_strategy=persisted.get("credential_strategy"),
        )

    async def activate_target_async(self, *, target_registry_name: str) -> Optional[TargetInstance]:
        self._ensure_initialized()
        saved = self._store.get_target(target_registry_name)
        if saved and saved.get("is_archived"):
            return None
        target = await self.get_target_async(target_registry_name=target_registry_name)
        if target is None:
            return None

        self._store.set_active_target(target_registry_name)
        return await self.get_target_async(target_registry_name=target_registry_name)

    async def update_target_config_async(
        self,
        *,
        target_registry_name: str,
        display_name: Optional[str] = None,
        special_instructions: Optional[str] = None,
    ) -> Optional[TargetConfigView]:
        self._ensure_initialized()
        saved = self._store.update_target_config(
            target_registry_name=target_registry_name,
            display_name=display_name,
            special_instructions=special_instructions,
        )
        if saved is None:
            return None
        target_obj = self._registry.get_instance_by_name(target_registry_name)
        if target_obj is not None and special_instructions is not None:
            self._apply_runtime_special_instructions(target_obj=target_obj, special_instructions=special_instructions)
        return await self.get_target_config_async(target_registry_name=target_registry_name)

    async def archive_target_async(self, *, target_registry_name: str, reason: Optional[str] = None) -> Optional[TargetInstance]:
        self._ensure_initialized()
        archived = self._store.archive_target(target_registry_name, reason=reason)
        if archived is None:
            return None
        unregister = getattr(self._registry, "unregister", None)
        if callable(unregister):
            unregister(target_registry_name)
        return TargetInstance(
            target_registry_name=str(archived["target_registry_name"]),
            display_name=archived.get("display_name"),
            target_type=str(archived["target_type"]),
            endpoint=archived.get("endpoint"),
            model_name=archived.get("model_name"),
            target_specific_params=dict(archived.get("params") or {}),
            is_active=False,
            created_at=archived.get("created_at"),
            persistence_scope="saved",
            credential_strategy=archived.get("credential_strategy"),
            is_archived=True,
            archived_at=archived.get("archived_at"),
        )

    def _apply_runtime_special_instructions(self, *, target_obj: Any, special_instructions: str) -> None:
        cleaned = special_instructions.strip() or None
        if hasattr(target_obj, "_system_instructions"):
            setattr(target_obj, "_system_instructions", cleaned)

        extra_body = getattr(target_obj, "_extra_body_parameters", None)
        if isinstance(extra_body, dict):
            if cleaned:
                extra_body["instructions"] = cleaned
            else:
                extra_body.pop("instructions", None)


@lru_cache(maxsize=1)
def get_target_service() -> TargetService:
    """Get the singleton target service."""
    return TargetService()
