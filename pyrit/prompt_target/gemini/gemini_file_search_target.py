# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from __future__ import annotations

import json
import logging
from collections.abc import MutableSequence
from typing import Any, Optional

import httpx

from pyrit.common import default_values
from pyrit.exceptions import EmptyResponseException, PyritException, RateLimitException, pyrit_target_retry
from pyrit.identifiers import ComponentIdentifier
from pyrit.models import Message, MessagePiece
from pyrit.prompt_target.common.prompt_chat_target import PromptChatTarget
from pyrit.prompt_target.common.utils import limit_requests_per_minute

logger = logging.getLogger(__name__)


class GeminiFileSearchTarget(PromptChatTarget):
    """
    Gemini File Search target for retrieval-backed audits.

    This target uses Gemini's native generateContent request semantics with the file_search tool
    and preserves retrieval evidence in the same metadata shape the existing SpriCo UI already consumes.
    """

    model_name_environment_variable = "GEMINI_FILE_SEARCH_MODEL"
    endpoint_environment_variable = "GEMINI_FILE_SEARCH_ENDPOINT"
    api_key_environment_variable = "GEMINI_FILE_SEARCH_API_KEY"

    def __init__(
        self,
        *,
        retrieval_store_id: str,
        retrieval_mode: Optional[str] = None,
        system_instructions: Optional[str] = None,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        max_requests_per_minute: Optional[int] = None,
        httpx_client_kwargs: Optional[dict[str, Any]] = None,
        underlying_model: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        retrieval_store_id = retrieval_store_id.strip()
        if not retrieval_store_id:
            raise ValueError("retrieval_store_id is required for GeminiFileSearchTarget.")
        if not retrieval_store_id.startswith("fileSearchStores/"):
            raise ValueError(
                "retrieval_store_id for GeminiFileSearchTarget must look like 'fileSearchStores/...'."
            )

        normalized_mode = (retrieval_mode or "file_search").strip() or "file_search"
        if normalized_mode != "file_search":
            raise ValueError("GeminiFileSearchTarget currently supports only retrieval_mode='file_search'.")

        resolved_model_name = default_values.get_required_value(
            env_var_name=self.model_name_environment_variable,
            passed_value=model_name,
        )
        resolved_endpoint = default_values.get_required_value(
            env_var_name=self.endpoint_environment_variable,
            passed_value=endpoint,
        ).strip()
        resolved_api_key = default_values.get_required_value(
            env_var_name=self.api_key_environment_variable,
            passed_value=api_key,
        )

        self._api_key = resolved_api_key
        self._retrieval_store_id = retrieval_store_id
        self._retrieval_mode = normalized_mode
        self._system_instructions = (system_instructions or "").strip() or None
        self._httpx_client_kwargs = dict(httpx_client_kwargs or {})
        self._httpx_client_kwargs.setdefault("timeout", httpx.Timeout(90.0, connect=15.0))

        super().__init__(
            endpoint=resolved_endpoint,
            model_name=resolved_model_name,
            underlying_model=underlying_model,
            max_requests_per_minute=max_requests_per_minute,
            **kwargs,
        )

    def _build_identifier(self) -> ComponentIdentifier:
        return self._create_identifier(
            params={
                "retrieval_store_id": self._retrieval_store_id,
                "retrieval_mode": self._retrieval_mode,
            }
        )

    def is_json_response_supported(self) -> bool:
        return False

    def _validate_request(self, *, message: Message) -> None:
        for piece in message.message_pieces:
            if piece.converted_value_data_type != "text":
                raise ValueError(
                    f"GeminiFileSearchTarget supports only text prompts. Received {piece.converted_value_data_type}."
                )

    def _build_generate_content_url(self) -> str:
        endpoint = self._endpoint.rstrip("/")
        if ":generateContent" in endpoint:
            return endpoint
        if "/models/" in endpoint:
            return f"{endpoint}:generateContent"
        return f"{endpoint}/models/{self._model_name}:generateContent"

    def _extract_error_message(self, *, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            return response.text or f"Gemini request failed with status {response.status_code}."

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                status_text = error.get("status")
                if message and status_text:
                    return f"{message} ({status_text})"
                if message:
                    return str(message)
            message = payload.get("message")
            if message:
                return str(message)

        return response.text or f"Gemini request failed with status {response.status_code}."

    def _build_system_instruction(self, *, conversation: MutableSequence[Message]) -> Optional[dict[str, Any]]:
        parts: list[str] = []
        if self._system_instructions:
            parts.append(self._system_instructions)

        for message in conversation:
            if not message.message_pieces:
                continue
            if message.message_pieces[0].api_role not in {"system", "developer"}:
                continue
            text = self._collect_text_from_message(message=message)
            if text:
                parts.append(text)

        if not parts:
            return None

        return {"parts": [{"text": "\n\n".join(parts)}]}

    def _collect_text_from_message(self, *, message: Message) -> str:
        values = [
            piece.converted_value.strip()
            for piece in message.message_pieces
            if piece.converted_value_data_type == "text" and piece.converted_value.strip()
        ]
        return "\n\n".join(values)

    def _build_request_body(self, *, conversation: MutableSequence[Message]) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []

        for message in conversation:
            if not message.message_pieces:
                continue

            role = message.message_pieces[0].api_role
            if role in {"system", "developer", "tool"}:
                continue

            text = self._collect_text_from_message(message=message)
            if not text:
                continue

            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": text}]})

        if not contents:
            raise ValueError("GeminiFileSearchTarget requires at least one text content item.")

        body: dict[str, Any] = {
            "contents": contents,
            "tools": [
                {
                    "file_search": {
                        "file_search_store_names": [self._retrieval_store_id],
                    }
                }
            ],
        }

        system_instruction = self._build_system_instruction(conversation=conversation)
        if system_instruction:
            body["systemInstruction"] = system_instruction

        return body

    async def _post_generate_content_async(self, *, body: dict[str, Any]) -> dict[str, Any]:
        url = self._build_generate_content_url()
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        logger.debug(
            "GeminiFileSearchTarget sending prompt with model=%s endpoint=%s retrieval_store_id=%s api_key_present=%s special_instructions_present=%s",
            self._model_name,
            self._endpoint,
            self._retrieval_store_id,
            bool(self._api_key),
            bool(self._system_instructions),
        )

        try:
            async with httpx.AsyncClient(**self._httpx_client_kwargs) as client:
                response = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise PyritException(status_code=502, message=f"Gemini request failed: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitException(message=self._extract_error_message(response=response))
        if response.status_code >= 400:
            raise PyritException(status_code=response.status_code, message=self._extract_error_message(response=response))

        try:
            payload = response.json()
        except ValueError as exc:
            raise PyritException(status_code=502, message="Gemini response was not valid JSON.") from exc

        if not isinstance(payload, dict):
            raise PyritException(status_code=502, message="Gemini response payload was not an object.")

        return payload

    def _extract_text_from_candidate(self, *, candidate: dict[str, Any]) -> str:
        content = candidate.get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""

        texts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
        return "\n\n".join(texts)

    @staticmethod
    def _coerce_retrieved_context(chunk: dict[str, Any]) -> dict[str, Any]:
        context = chunk.get("retrievedContext")
        if not isinstance(context, dict):
            return {}
        return {
            "document_name": context.get("title"),
            "title": context.get("title"),
            "text": context.get("text"),
            "source_uri": context.get("uri"),
            "file_search_store": context.get("fileSearchStore"),
            "custom_metadata": context.get("customMetadata") or [],
        }

    def _normalize_retrieval_results(self, *, grounding_chunks: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, chunk in enumerate(grounding_chunks):
            if not isinstance(chunk, dict):
                continue
            context = self._coerce_retrieved_context(chunk)
            if not context:
                continue
            context["rank"] = index
            normalized.append(context)
        return normalized

    def _normalize_grounding_supports(
        self,
        *,
        grounding_supports: list[Any],
        retrieval_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        annotations: list[dict[str, Any]] = []
        for index, support in enumerate(grounding_supports):
            if not isinstance(support, dict):
                continue

            segment = support.get("segment")
            if not isinstance(segment, dict):
                segment = {}

            chunk_indices = support.get("groundingChunkIndices")
            if not isinstance(chunk_indices, list):
                chunk_indices = []

            cited_titles = [
                retrieval_results[idx].get("document_name")
                for idx in chunk_indices
                if isinstance(idx, int) and 0 <= idx < len(retrieval_results)
            ]
            cited_titles = [title for title in cited_titles if isinstance(title, str) and title]

            annotations.append(
                {
                    "annotation_type": "grounding_support",
                    "label": f"Support {index + 1}",
                    "document_name": cited_titles[0] if len(cited_titles) == 1 else ", ".join(cited_titles[:3]) or None,
                    "quote": segment.get("text"),
                    "text": segment.get("text"),
                    "index": chunk_indices[0] if chunk_indices else None,
                    "grounding_chunk_indices": chunk_indices,
                }
            )
        return annotations

    def _build_response_message(self, *, payload: dict[str, Any], request_piece: MessagePiece) -> Message:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise EmptyResponseException(message="Gemini returned no candidates.")

        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise EmptyResponseException(message="Gemini returned an invalid candidate payload.")

        response_text = self._extract_text_from_candidate(candidate=candidate)
        if not response_text:
            finish_reason = candidate.get("finishReason")
            reason_suffix = f" finishReason={finish_reason}" if finish_reason else ""
            raise EmptyResponseException(message=f"Gemini returned an empty response.{reason_suffix}")

        grounding_metadata = candidate.get("groundingMetadata")
        if not isinstance(grounding_metadata, dict):
            grounding_metadata = {}
        grounding_chunks = grounding_metadata.get("groundingChunks")
        if not isinstance(grounding_chunks, list):
            grounding_chunks = []
        grounding_supports = grounding_metadata.get("groundingSupports")
        if not isinstance(grounding_supports, list):
            grounding_supports = []

        retrieval_results = self._normalize_retrieval_results(grounding_chunks=grounding_chunks)
        response_annotations = self._normalize_grounding_supports(
            grounding_supports=grounding_supports,
            retrieval_results=retrieval_results,
        )

        text_piece = MessagePiece(
            role="assistant",
            original_value=response_text,
            conversation_id=request_piece.conversation_id,
            labels=request_piece.labels,
            prompt_target_identifier=request_piece.prompt_target_identifier,
            attack_identifier=request_piece.attack_identifier,
            original_value_data_type="text",
        )

        raw_tool_payload = {
            "type": "file_search_call",
            "provider": "gemini",
            "retrieval_store_id": self._retrieval_store_id,
            "grounding_metadata": grounding_metadata,
            "usage_metadata": payload.get("usageMetadata"),
            "finish_reason": candidate.get("finishReason"),
        }
        tool_piece = MessagePiece(
            role="assistant",
            original_value=json.dumps(raw_tool_payload, separators=(",", ":")),
            conversation_id=request_piece.conversation_id,
            labels=request_piece.labels,
            prompt_target_identifier=request_piece.prompt_target_identifier,
            attack_identifier=request_piece.attack_identifier,
            original_value_data_type="tool_call",
            prompt_metadata={
                "retrieval_evidence": {
                    "source": "gemini_file_search_api",
                    "tool_type": "file_search_call",
                    "file_search_call": raw_tool_payload,
                    "results": retrieval_results,
                    "response_annotations": response_annotations,
                }
            },
        )

        return Message(message_pieces=[text_piece, tool_piece])

    @limit_requests_per_minute
    @pyrit_target_retry
    async def send_prompt_async(self, *, message: Message) -> list[Message]:
        self._validate_request(message=message)

        request_piece = message.message_pieces[0]
        conversation: MutableSequence[Message] = self._memory.get_conversation(conversation_id=request_piece.conversation_id)
        conversation.append(message)

        body = self._build_request_body(conversation=conversation)
        payload = await self._post_generate_content_async(body=body)
        return [self._build_response_message(payload=payload, request_piece=request_piece)]
