# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from unittest.mock import AsyncMock

import pytest

from pyrit.models import Message, MessagePiece
from pyrit.prompt_target import GeminiFileSearchTarget


@pytest.fixture
def dummy_text_message_piece() -> MessagePiece:
    return MessagePiece(
        role="user",
        conversation_id="gemini-file-search-conversation",
        original_value="Based only on the uploaded HR markdown files, list any recorded employee leave policy categories.",
        converted_value="Based only on the uploaded HR markdown files, list any recorded employee leave policy categories.",
        original_value_data_type="text",
        converted_value_data_type="text",
    )


@pytest.fixture
def target(patch_central_database) -> GeminiFileSearchTarget:
    return GeminiFileSearchTarget(
        model_name="gemini-2.5-flash",
        endpoint="https://generativelanguage.googleapis.com/v1beta/",
        api_key="AIza-test-key-123",
        retrieval_store_id="fileSearchStores/hr-demo",
        system_instructions="Answer only from the retrieved HR files.",
    )


def test_init_requires_retrieval_store_id(patch_central_database) -> None:
    with pytest.raises(ValueError, match="retrieval_store_id is required"):
        GeminiFileSearchTarget(
            model_name="gemini-2.5-flash",
            endpoint="https://generativelanguage.googleapis.com/v1beta/",
            api_key="AIza-test-key-123",
            retrieval_store_id="",
        )


def test_init_requires_gemini_store_shape(patch_central_database) -> None:
    with pytest.raises(ValueError, match="must look like 'fileSearchStores/"):
        GeminiFileSearchTarget(
            model_name="gemini-2.5-flash",
            endpoint="https://generativelanguage.googleapis.com/v1beta/",
            api_key="AIza-test-key-123",
            retrieval_store_id="vs_wrong_shape",
        )


def test_init_rejects_non_file_search_retrieval_mode(patch_central_database) -> None:
    with pytest.raises(ValueError, match="supports only retrieval_mode='file_search'"):
        GeminiFileSearchTarget(
            model_name="gemini-2.5-flash",
            endpoint="https://generativelanguage.googleapis.com/v1beta/",
            api_key="AIza-test-key-123",
            retrieval_store_id="fileSearchStores/hr-demo",
            retrieval_mode="custom",
        )


def test_build_identifier_includes_retrieval_fields(target: GeminiFileSearchTarget) -> None:
    identifier = target.get_identifier()
    assert identifier.params["retrieval_store_id"] == "fileSearchStores/hr-demo"
    assert identifier.params["retrieval_mode"] == "file_search"


def test_build_generate_content_url(target: GeminiFileSearchTarget) -> None:
    assert (
        target._build_generate_content_url()
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    )


def test_construct_request_body_includes_file_search_tool(
    target: GeminiFileSearchTarget,
    dummy_text_message_piece: MessagePiece,
) -> None:
    request = Message(message_pieces=[dummy_text_message_piece])
    body = target._build_request_body(conversation=[request])

    assert body["tools"] == [
        {
            "file_search": {
                "file_search_store_names": ["fileSearchStores/hr-demo"],
            }
        }
    ]
    assert body["contents"] == [
        {
            "role": "user",
            "parts": [
                {
                    "text": "Based only on the uploaded HR markdown files, list any recorded employee leave policy categories."
                }
            ],
        }
    ]
    assert body["systemInstruction"] == {
        "parts": [{"text": "Answer only from the retrieved HR files."}]
    }


def test_build_response_message_preserves_retrieval_evidence(
    target: GeminiFileSearchTarget,
    dummy_text_message_piece: MessagePiece,
) -> None:
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "The HR markdown files record employee requests under the Life event category."
                        }
                    ],
                    "role": "model",
                },
                "finishReason": "STOP",
                "index": 0,
                "groundingMetadata": {
                    "groundingChunks": [
                        {
                            "retrievedContext": {
                                "title": "Ticket15_Life_event_Health_issues_Silvestro_Pederiva.md",
                                "text": "# HR Ticket\\n\\n## Metadata\\n- Category: Life event\\n- Sub-category: Health issues",
                                "uri": "gs://hr-demo/Ticket15_Life_event_Health_issues_Silvestro_Pederiva.md",
                                "fileSearchStore": "fileSearchStores/hr-demo",
                            }
                        }
                    ],
                    "groundingSupports": [
                        {
                            "segment": {
                                "text": "The HR markdown files record employee requests under the Life event category."
                            },
                            "groundingChunkIndices": [0],
                        }
                    ],
                },
            }
        ],
        "usageMetadata": {"totalTokenCount": 42},
    }

    message = target._build_response_message(payload=payload, request_piece=dummy_text_message_piece)

    assert len(message.message_pieces) == 2
    assert message.message_pieces[0].original_value_data_type == "text"
    assert message.message_pieces[0].original_value.startswith("The HR markdown files record")
    assert message.message_pieces[1].original_value_data_type == "tool_call"
    retrieval = message.message_pieces[1].prompt_metadata["retrieval_evidence"]
    assert retrieval["source"] == "gemini_file_search_api"
    assert retrieval["results"][0]["document_name"] == "Ticket15_Life_event_Health_issues_Silvestro_Pederiva.md"
    assert retrieval["results"][0]["file_search_store"] == "fileSearchStores/hr-demo"
    assert retrieval["response_annotations"][0]["annotation_type"] == "grounding_support"


@pytest.mark.asyncio
async def test_send_prompt_async_uses_provider_specific_request_path(
    target: GeminiFileSearchTarget,
    dummy_text_message_piece: MessagePiece,
) -> None:
    payload = {
        "candidates": [
            {
                "content": {"parts": [{"text": "HR response"}], "role": "model"},
                "finishReason": "STOP",
                "groundingMetadata": {"groundingChunks": [], "groundingSupports": []},
            }
        ]
    }
    target._post_generate_content_async = AsyncMock(return_value=payload)  # type: ignore[method-assign]

    request = Message(message_pieces=[dummy_text_message_piece])
    responses = await target.send_prompt_async(message=request)

    assert len(responses) == 1
    assert responses[0].message_pieces[0].original_value == "HR response"
    target._post_generate_content_async.assert_awaited_once()
    request_body = target._post_generate_content_async.await_args.kwargs["body"]
    assert request_body["tools"][0]["file_search"]["file_search_store_names"] == ["fileSearchStores/hr-demo"]
