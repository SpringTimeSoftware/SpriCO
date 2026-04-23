# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from types import SimpleNamespace

import pytest

from pyrit.models import Message, MessagePiece
from pyrit.models.json_response_config import _JsonResponseConfig
from pyrit.prompt_target import OpenAIVectorStoreTarget


@pytest.fixture
def dummy_text_message_piece() -> MessagePiece:
    return MessagePiece(
        role="user",
        conversation_id="vector-store-conversation",
        original_value="Summarize the judgment.",
        converted_value="Summarize the judgment.",
        original_value_data_type="text",
        converted_value_data_type="text",
    )


@pytest.fixture
def target(patch_central_database) -> OpenAIVectorStoreTarget:
    return OpenAIVectorStoreTarget(
        model_name="gpt-4.1",
        endpoint="https://api.openai.com/v1",
        api_key="sk-test",
        retrieval_store_id="vs_legal_demo",
        system_instructions="Use only retrieved legal materials.",
    )


def test_init_requires_retrieval_store_id(patch_central_database) -> None:
    with pytest.raises(ValueError, match="retrieval_store_id is required"):
        OpenAIVectorStoreTarget(
            model_name="gpt-4.1",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
            retrieval_store_id="",
        )


def test_init_rejects_non_file_search_retrieval_mode(patch_central_database) -> None:
    with pytest.raises(ValueError, match="supports only retrieval_mode='file_search'"):
        OpenAIVectorStoreTarget(
            model_name="gpt-4.1",
            endpoint="https://api.openai.com/v1",
            api_key="sk-test",
            retrieval_store_id="vs_legal_demo",
            retrieval_mode="custom",
        )


@pytest.mark.asyncio
async def test_construct_request_body_includes_file_search_tool(
    target: OpenAIVectorStoreTarget,
    dummy_text_message_piece: MessagePiece,
) -> None:
    request = Message(message_pieces=[dummy_text_message_piece])
    body = await target._construct_request_body(
        conversation=[request],
        json_config=_JsonResponseConfig(enabled=False),
    )

    assert body["model"] == "gpt-4.1"
    assert body["instructions"] == "Use only retrieved legal materials."
    assert body["include"] == ["file_search_call.results"]
    assert body["tools"] == [
        {
            "type": "file_search",
            "vector_store_ids": ["vs_legal_demo"],
        }
    ]


@pytest.mark.asyncio
async def test_construct_request_body_includes_max_num_results(
    patch_central_database,
    dummy_text_message_piece: MessagePiece,
) -> None:
    target = OpenAIVectorStoreTarget(
        model_name="gpt-4.1",
        endpoint="https://api.openai.com/v1",
        api_key="sk-test",
        retrieval_store_id="vs_legal_demo",
        max_num_results=7,
    )
    request = Message(message_pieces=[dummy_text_message_piece])
    body = await target._construct_request_body(
        conversation=[request],
        json_config=_JsonResponseConfig(enabled=False),
    )

    assert body["tools"] == [
        {
            "type": "file_search",
            "vector_store_ids": ["vs_legal_demo"],
            "max_num_results": 7,
        }
    ]
    assert body["include"] == ["file_search_call.results"]


@pytest.mark.asyncio
async def test_saved_special_instructions_are_merged_with_existing_openai_instructions(
    patch_central_database,
    dummy_text_message_piece: MessagePiece,
) -> None:
    target = OpenAIVectorStoreTarget(
        model_name="gpt-4.1",
        endpoint="https://api.openai.com/v1",
        api_key="sk-test",
        retrieval_store_id="vs_legal_demo",
        system_instructions="Use only retrieved legal materials.",
        extra_body_parameters={"instructions": "Return short bullet points."},
    )
    request = Message(message_pieces=[dummy_text_message_piece])
    body = await target._construct_request_body(
        conversation=[request],
        json_config=_JsonResponseConfig(enabled=False),
    )

    assert body["instructions"] == "Use only retrieved legal materials.\n\nReturn short bullet points."


def test_build_identifier_includes_retrieval_fields(target: OpenAIVectorStoreTarget) -> None:
    identifier = target.get_identifier()
    assert identifier.params["retrieval_store_id"] == "vs_legal_demo"
    assert identifier.params["retrieval_mode"] == "file_search"
    assert "system_instructions" not in identifier.params


def test_parse_file_search_call_preserves_retrieval_evidence(
    target: OpenAIVectorStoreTarget,
    dummy_text_message_piece: MessagePiece,
) -> None:
    section = SimpleNamespace(
        type="file_search_call",
        model_dump=lambda: {
            "type": "file_search_call",
            "id": "fsc_123",
            "status": "completed",
            "queries": ["What was the final relief?"],
            "results": [
                {
                    "file_id": "file_123",
                    "filename": "osfc-judgment.pdf",
                    "score": 0.91,
                    "content": [{"text": "This civil appeal is decided in terms of compromise deed/application 25C."}],
                }
            ],
        },
    )

    piece = target._parse_response_output_section(section=section, message_piece=dummy_text_message_piece, error=None)

    assert piece is not None
    assert piece.original_value_data_type == "tool_call"
    assert piece.prompt_metadata is not None
    retrieval = piece.prompt_metadata["retrieval_evidence"]
    assert retrieval["tool_type"] == "file_search_call"
    assert retrieval["file_search_call"]["id"] == "fsc_123"
    assert retrieval["results"][0]["file_id"] == "file_123"


def test_parse_message_preserves_response_annotations(
    target: OpenAIVectorStoreTarget,
    dummy_text_message_piece: MessagePiece,
) -> None:
    annotation = {
        "type": "file_citation",
        "file_id": "file_123",
        "filename": "osfc-judgment.pdf",
        "index": 0,
    }
    content_item = SimpleNamespace(
        text="The final relief was disposal of the appeal in terms of the compromise deed.",
        model_dump=lambda: {
            "type": "output_text",
            "text": "The final relief was disposal of the appeal in terms of the compromise deed.",
            "annotations": [annotation],
        },
    )
    section = SimpleNamespace(
        type="message",
        content=[content_item],
    )

    piece = target._parse_response_output_section(section=section, message_piece=dummy_text_message_piece, error=None)

    assert piece is not None
    assert piece.prompt_metadata is not None
    retrieval = piece.prompt_metadata["retrieval_evidence"]
    assert retrieval["source"] == "openai_responses_api"
    assert retrieval["response_annotations"][0]["file_id"] == "file_123"


@pytest.mark.asyncio
async def test_build_input_skips_file_search_call_replay_but_keeps_assistant_text(
    target: OpenAIVectorStoreTarget,
    dummy_text_message_piece: MessagePiece,
) -> None:
    conversation_id = dummy_text_message_piece.conversation_id
    user_message = Message(message_pieces=[dummy_text_message_piece])

    assistant_text = MessagePiece(
        role="assistant",
        conversation_id=conversation_id,
        original_value="I could not find that patient record.",
        converted_value="I could not find that patient record.",
        original_value_data_type="text",
        converted_value_data_type="text",
    )
    file_search_call = MessagePiece(
        role="assistant",
        conversation_id=conversation_id,
        original_value=(
            '{"type":"file_search_call","id":"fsc_123","status":"completed",'
            '"queries":["Find patient MRN-10427"],"call_id":"call_123"}'
        ),
        original_value_data_type="tool_call",
        converted_value_data_type="tool_call",
    )
    assistant_message = Message(message_pieces=[assistant_text, file_search_call])

    replayed_input = await target._build_input_for_multi_modal_async([user_message, assistant_message])

    assert replayed_input[0]["role"] == "user"
    assert len(replayed_input) == 2
    assert replayed_input[1]["role"] == "assistant"
    assert replayed_input[1]["content"][0]["text"] == "I could not find that patient record."
