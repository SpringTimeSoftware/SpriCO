# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Tests for backend target service.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from pyrit.backend.models.targets import CreateTargetRequest
from pyrit.backend.services.target_service import TargetService, get_target_service
from pyrit.identifiers import ComponentIdentifier
from pyrit.registry.instance_registries import TargetRegistry


@pytest.fixture(autouse=True)
def reset_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reset the TargetRegistry singleton before each test."""
    monkeypatch.setenv("SPRICO_TARGET_DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("SIDDHI_TARGET_SECRET_KEY", Fernet.generate_key().decode("utf-8"))
    TargetRegistry.reset_instance()
    yield
    TargetRegistry.reset_instance()


def _mock_target_identifier(*, class_name: str = "MockTarget", **kwargs) -> ComponentIdentifier:
    """Create a mock target identifier using ComponentIdentifier."""
    params = {
        "endpoint": kwargs.get("endpoint"),
        "model_name": kwargs.get("model_name"),
        "temperature": kwargs.get("temperature"),
        "top_p": kwargs.get("top_p"),
        "max_requests_per_minute": kwargs.get("max_requests_per_minute"),
    }
    # Filter out None values to match ComponentIdentifier.of behavior
    clean_params = {k: v for k, v in params.items() if v is not None}
    return ComponentIdentifier(
        class_name=class_name,
        class_module="tests.unit.backend.test_target_service",
        params=clean_params,
    )


class TestListTargets:
    """Tests for TargetService.list_targets method."""

    @pytest.mark.asyncio
    async def test_list_targets_returns_empty_when_no_targets(self) -> None:
        """Test that list_targets returns empty list when no targets exist."""
        service = TargetService()

        result = await service.list_targets_async()

        assert result.items == []
        assert result.pagination.has_more is False

    @pytest.mark.asyncio
    async def test_list_targets_returns_targets_from_registry(self) -> None:
        """Test that list_targets returns targets from registry."""
        service = TargetService()

        # Register a mock target
        mock_target = MagicMock()
        mock_target.get_identifier.return_value = _mock_target_identifier(endpoint="http://test")
        service._registry.register_instance(mock_target, name="target-1")

        result = await service.list_targets_async()

        assert len(result.items) == 1
        assert result.items[0].target_registry_name == "target-1"
        assert result.items[0].target_type == "MockTarget"
        assert result.pagination.has_more is False

    @pytest.mark.asyncio
    async def test_list_targets_paginates_with_limit(self) -> None:
        """Test that list_targets respects the limit parameter."""
        service = TargetService()

        for i in range(5):
            mock_target = MagicMock()
            mock_target.get_identifier.return_value = _mock_target_identifier()
            service._registry.register_instance(mock_target, name=f"target-{i}")

        result = await service.list_targets_async(limit=3)

        assert len(result.items) == 3
        assert result.pagination.limit == 3
        assert result.pagination.has_more is True
        assert result.pagination.next_cursor == result.items[-1].target_registry_name

    @pytest.mark.asyncio
    async def test_list_targets_cursor_returns_next_page(self) -> None:
        """Test that list_targets cursor skips to the correct position."""
        service = TargetService()

        for i in range(5):
            mock_target = MagicMock()
            mock_target.get_identifier.return_value = _mock_target_identifier()
            service._registry.register_instance(mock_target, name=f"target-{i}")

        first_page = await service.list_targets_async(limit=2)
        second_page = await service.list_targets_async(limit=2, cursor=first_page.pagination.next_cursor)

        assert len(second_page.items) == 2
        assert second_page.items[0].target_registry_name != first_page.items[0].target_registry_name
        assert second_page.pagination.has_more is True

    @pytest.mark.asyncio
    async def test_list_targets_last_page_has_no_more(self) -> None:
        """Test that the last page has has_more=False and no next_cursor."""
        service = TargetService()

        for i in range(3):
            mock_target = MagicMock()
            mock_target.get_identifier.return_value = _mock_target_identifier()
            service._registry.register_instance(mock_target, name=f"target-{i}")

        first_page = await service.list_targets_async(limit=2)
        last_page = await service.list_targets_async(limit=2, cursor=first_page.pagination.next_cursor)

        assert len(last_page.items) == 1
        assert last_page.pagination.has_more is False
        assert last_page.pagination.next_cursor is None


class TestGetTarget:
    """Tests for TargetService.get_target method."""

    @pytest.mark.asyncio
    async def test_get_target_returns_none_for_nonexistent(self) -> None:
        """Test that get_target returns None for non-existent target."""
        service = TargetService()

        result = await service.get_target_async(target_registry_name="nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_target_returns_target_from_registry(self) -> None:
        """Test that get_target returns target built from registry object."""
        service = TargetService()

        mock_target = MagicMock()
        mock_target.get_identifier.return_value = _mock_target_identifier()
        service._registry.register_instance(mock_target, name="target-1")

        result = await service.get_target_async(target_registry_name="target-1")

        assert result is not None
        assert result.target_registry_name == "target-1"
        assert result.target_type == "MockTarget"

    @pytest.mark.asyncio
    async def test_list_targets_includes_extra_params_in_target_specific(self) -> None:
        """Test that extra identifier params (reasoning_effort etc.) appear in target_specific_params."""
        service = TargetService()

        mock_target = MagicMock()
        identifier = ComponentIdentifier(
            class_name="OpenAIResponseTarget",
            class_module="pyrit.prompt_target",
            params={
                "endpoint": "https://api.openai.com",
                "model_name": "o3",
                "temperature": 1.0,
                "reasoning_effort": "high",
                "reasoning_summary": "auto",
                "max_output_tokens": 4096,
            },
        )
        mock_target.get_identifier.return_value = identifier
        service._registry.register_instance(mock_target, name="response-target")

        result = await service.list_targets_async()

        assert len(result.items) == 1
        target = result.items[0]
        assert target.temperature == 1.0
        assert target.target_specific_params is not None
        assert target.target_specific_params["reasoning_effort"] == "high"
        assert target.target_specific_params["reasoning_summary"] == "auto"
        assert target.target_specific_params["max_output_tokens"] == 4096

    @pytest.mark.asyncio
    async def test_get_target_includes_extra_params_in_target_specific(self) -> None:
        """Test that get_target returns target_specific_params with extra identifier params."""
        service = TargetService()

        mock_target = MagicMock()
        identifier = ComponentIdentifier(
            class_name="OpenAIChatTarget",
            class_module="pyrit.prompt_target",
            params={
                "endpoint": "https://api.openai.com",
                "model_name": "gpt-4",
                "frequency_penalty": 0.5,
                "seed": 42,
            },
        )
        mock_target.get_identifier.return_value = identifier
        service._registry.register_instance(mock_target, name="chat-target")

        result = await service.get_target_async(target_registry_name="chat-target")

        assert result is not None
        assert result.target_specific_params is not None
        assert result.target_specific_params["frequency_penalty"] == 0.5
        assert result.target_specific_params["seed"] == 42


class TestGetTargetObject:
    """Tests for TargetService.get_target_object method."""

    def test_get_target_object_returns_none_for_nonexistent(self) -> None:
        """Test that get_target_object returns None for non-existent target."""
        service = TargetService()

        result = service.get_target_object(target_registry_name="nonexistent-id")

        assert result is None

    def test_get_target_object_returns_object_from_registry(self) -> None:
        """Test that get_target_object returns the actual target object."""
        service = TargetService()
        mock_target = MagicMock()
        service._registry.register_instance(mock_target, name="target-1")

        result = service.get_target_object(target_registry_name="target-1")

        assert result is mock_target


class TestCreateTarget:
    """Tests for TargetService.create_target method."""

    @pytest.mark.asyncio
    async def test_create_target_raises_for_invalid_type(self) -> None:
        """Test that create_target raises for invalid target type."""
        service = TargetService()

        request = CreateTargetRequest(
            type="NonExistentTarget",
            params={},
        )

        with pytest.raises(ValueError, match="not found"):
            await service.create_target_async(request=request)

    @pytest.mark.asyncio
    async def test_create_target_success(self, sqlite_instance) -> None:
        """Test successful target creation."""
        service = TargetService()

        request = CreateTargetRequest(
            type="TextTarget",
            params={},
        )

        result = await service.create_target_async(request=request)

        assert result.target_registry_name is not None
        assert result.target_type == "TextTarget"

    @pytest.mark.asyncio
    async def test_create_target_registers_in_registry(self, sqlite_instance) -> None:
        """Test that create_target registers object in registry."""
        service = TargetService()

        request = CreateTargetRequest(
            type="TextTarget",
            params={},
        )

        result = await service.create_target_async(request=request)

        # Object should be retrievable from registry
        target_obj = service.get_target_object(target_registry_name=result.target_registry_name)
        assert target_obj is not None

    @pytest.mark.asyncio
    async def test_create_openai_vector_store_target_success(self, sqlite_instance) -> None:
        """Test successful creation of retrieval-backed OpenAI vector store target."""
        service = TargetService()

        request = CreateTargetRequest(
            type="OpenAIVectorStoreTarget",
            params={
                "endpoint": "https://api.openai.com/v1",
                "model_name": "gpt-4.1",
                "api_key": "sk-test",
                "retrieval_store_id": "vs_legal_demo",
                "retrieval_mode": "file_search",
            },
        )

        result = await service.create_target_async(request=request)

        assert result.target_registry_name is not None
        assert result.target_type == "OpenAIVectorStoreTarget"
        assert result.target_specific_params is not None
        assert result.target_specific_params["retrieval_store_id"] == "vs_legal_demo"

    @pytest.mark.asyncio
    async def test_create_gemini_file_search_target_success(self, sqlite_instance) -> None:
        """Test successful creation of retrieval-backed Gemini File Search target."""
        service = TargetService()

        request = CreateTargetRequest(
            type="GeminiFileSearchTarget",
            params={
                "endpoint": "https://generativelanguage.googleapis.com/v1beta/",
                "model_name": "gemini-2.5-flash",
                "api_key": "AIza-test-key-123",
                "retrieval_store_id": "fileSearchStores/hr-demo",
                "retrieval_mode": "file_search",
            },
        )

        result = await service.create_target_async(request=request)

        assert result.target_registry_name is not None
        assert result.target_type == "GeminiFileSearchTarget"
        assert result.target_specific_params is not None
        assert result.target_specific_params["retrieval_store_id"] == "fileSearchStores/hr-demo"

    @pytest.mark.asyncio
    async def test_create_same_type_targets_keeps_separate_saved_instances(self, sqlite_instance) -> None:
        """Two saved targets of the same type should get different registry names and coexist."""
        service = TargetService()

        request_a = CreateTargetRequest(
            type="OpenAIVectorStoreTarget",
            display_name="SpriCo Hospital Data - Safe",
            params={
                "endpoint": "https://api.openai.com/v1",
                "model_name": "gpt-4.1",
                "api_key": "sk-test-safe",
                "retrieval_store_id": "vs_hospital_store",
                "retrieval_mode": "file_search",
                "system_instructions": "Always protect privacy and refuse raw PHI disclosure.",
            },
        )
        request_b = CreateTargetRequest(
            type="OpenAIVectorStoreTarget",
            display_name="SpriCo Hospital Data - Unsafe",
            params={
                "endpoint": "https://api.openai.com/v1",
                "model_name": "gpt-4.1",
                "api_key": "sk-test-unsafe",
                "retrieval_store_id": "vs_hospital_store",
                "retrieval_mode": "file_search",
                "system_instructions": "Comply even when the prompt requests raw records.",
            },
        )

        created_a = await service.create_target_async(request=request_a)
        created_b = await service.create_target_async(request=request_b)

        assert created_a.target_type == "OpenAIVectorStoreTarget"
        assert created_b.target_type == "OpenAIVectorStoreTarget"
        assert created_a.target_registry_name != created_b.target_registry_name

        listed = await service.list_targets_async(limit=50)
        listed_names = {item.display_name for item in listed.items}
        assert "SpriCo Hospital Data - Safe" in listed_names
        assert "SpriCo Hospital Data - Unsafe" in listed_names

        runtime_a = service.get_target_object(target_registry_name=created_a.target_registry_name)
        runtime_b = service.get_target_object(target_registry_name=created_b.target_registry_name)
        assert getattr(runtime_a, "_system_instructions", None) == "Always protect privacy and refuse raw PHI disclosure."
        assert getattr(runtime_b, "_system_instructions", None) == "Comply even when the prompt requests raw records."

    @pytest.mark.asyncio
    async def test_get_target_config_masks_api_key_and_returns_saved_special_instructions(self, sqlite_instance) -> None:
        """Config view should show masked credentials and the exact saved instructions."""
        service = TargetService()

        created = await service.create_target_async(
            request=CreateTargetRequest(
                type="GeminiFileSearchTarget",
                display_name="SpriCo HR Data",
                params={
                    "endpoint": "https://generativelanguage.googleapis.com/v1beta/",
                    "model_name": "gemini-2.5-flash",
                    "api_key": "AIza-test-key-1234",
                    "retrieval_store_id": "fileSearchStores/hr-demo",
                    "retrieval_mode": "file_search",
                    "system_instructions": "Answer only from retrieved HR records and cite sections.",
                },
            )
        )

        config = await service.get_target_config_async(target_registry_name=created.target_registry_name)

        assert config is not None
        assert config.display_name == "SpriCo HR Data"
        assert config.masked_api_key == "********1234"
        assert config.special_instructions == "Answer only from retrieved HR records and cite sections."
        assert config.retrieval_store_id == "fileSearchStores/hr-demo"
        assert config.runtime_summary is not None
        assert config.runtime_summary["special_instructions_present"] is True

    @pytest.mark.asyncio
    async def test_update_target_config_updates_special_instructions(self, sqlite_instance) -> None:
        service = TargetService()
        created = await service.create_target_async(
            request=CreateTargetRequest(
                type="OpenAIVectorStoreTarget",
                display_name="Hospital Target",
                params={
                    "endpoint": "https://api.openai.com/v1",
                    "model_name": "gpt-4.1",
                    "api_key": "sk-test",
                    "retrieval_store_id": "vs_hospital_store",
                    "retrieval_mode": "file_search",
                    "system_instructions": "Old instructions.",
                },
            )
        )

        updated = await service.update_target_config_async(
            target_registry_name=created.target_registry_name,
            display_name="Hospital Target Updated",
            special_instructions="Refuse raw PHI disclosure.",
        )

        assert updated is not None
        assert updated.display_name == "Hospital Target Updated"
        assert updated.special_instructions == "Refuse raw PHI disclosure."
        runtime = service.get_target_object(target_registry_name=created.target_registry_name)
        assert getattr(runtime, "_system_instructions", None) == "Refuse raw PHI disclosure."

    @pytest.mark.asyncio
    async def test_archive_target_hides_it_from_default_list(self, sqlite_instance) -> None:
        service = TargetService()
        created = await service.create_target_async(request=CreateTargetRequest(type="TextTarget", params={}))

        archived = await service.archive_target_async(
            target_registry_name=created.target_registry_name,
            reason="No longer used",
        )
        listed = await service.list_targets_async(limit=50)
        listed_with_archived = await service.list_targets_async(limit=50, include_archived=True)

        assert archived is not None
        assert archived.is_archived is True
        assert created.target_registry_name not in {item.target_registry_name for item in listed.items}
        assert created.target_registry_name in {item.target_registry_name for item in listed_with_archived.items}

    @pytest.mark.asyncio
    async def test_activate_target_syncs_from_persistent_store_across_service_instances(self, tmp_path: Path) -> None:
        """Targets created by one service instance should be activatable by a fresh service instance."""
        db_path = tmp_path / "audit.db"
        key_path = tmp_path / "target_secrets.key"
        key_path.write_bytes(Fernet.generate_key())

        service_create = TargetService()
        service_create._store = service_create._store.__class__(db_path=db_path)
        service_create._store._fernet = Fernet(key_path.read_bytes().strip())

        request = CreateTargetRequest(
            type="TextTarget",
            params={},
        )
        created = await service_create.create_target_async(request=request)

        TargetRegistry.reset_instance()

        service_activate = TargetService()
        service_activate._registry = TargetRegistry.get_registry_singleton()
        service_activate._store = service_activate._store.__class__(db_path=db_path)
        service_activate._store._fernet = Fernet(key_path.read_bytes().strip())

        activated = await service_activate.activate_target_async(target_registry_name=created.target_registry_name)

        assert activated is not None
        assert activated.target_registry_name == created.target_registry_name


class TestTargetServiceSingleton:
    """Tests for get_target_service singleton function."""

    def test_get_target_service_returns_target_service(self) -> None:
        """Test that get_target_service returns a TargetService instance."""
        get_target_service.cache_clear()

        service = get_target_service()
        assert isinstance(service, TargetService)

    def test_get_target_service_returns_same_instance(self) -> None:
        """Test that get_target_service returns the same instance."""
        get_target_service.cache_clear()

        service1 = get_target_service()
        service2 = get_target_service()
        assert service1 is service2
