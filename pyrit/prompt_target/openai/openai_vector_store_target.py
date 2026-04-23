# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
from typing import Any, Optional

from pyrit.identifiers import ComponentIdentifier
from pyrit.models import Message
from pyrit.prompt_target.openai.openai_response_target import OpenAIResponseTarget

logger = logging.getLogger(__name__)


class OpenAIVectorStoreTarget(OpenAIResponseTarget):
    """
    Responses API target that augments prompts with OpenAI file_search over a configured vector store.

    This is intended for retrieval-backed audits where the target system behavior should still flow
    through the existing SpriCo Interactive Audit and evaluator pipeline as a normal prompt target.
    """

    def __init__(
        self,
        *,
        retrieval_store_id: str,
        retrieval_mode: Optional[str] = None,
        system_instructions: Optional[str] = None,
        max_num_results: Optional[int] = None,
        extra_body_parameters: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        retrieval_store_id = retrieval_store_id.strip()
        if not retrieval_store_id:
            raise ValueError("retrieval_store_id is required for OpenAIVectorStoreTarget.")

        normalized_mode = (retrieval_mode or "file_search").strip() or "file_search"
        if normalized_mode != "file_search":
            raise ValueError(
                "OpenAIVectorStoreTarget currently supports only retrieval_mode='file_search'."
            )

        if max_num_results is not None and not 1 <= int(max_num_results) <= 50:
            raise ValueError("max_num_results must be between 1 and 50 when provided.")

        self._retrieval_store_id = retrieval_store_id
        self._retrieval_mode = normalized_mode
        self._system_instructions = (system_instructions or "").strip() or None
        self._max_num_results = int(max_num_results) if max_num_results is not None else None

        merged_extra_body = dict(extra_body_parameters or {})
        merged_extra_body["tools"] = self._merge_tools(
            existing_tools=list(merged_extra_body.get("tools") or []),
        )
        merged_extra_body["include"] = self._merge_include(
            existing_include=list(merged_extra_body.get("include") or []),
        )
        merged_extra_body["instructions"] = self._merge_instructions(
            existing_instructions=merged_extra_body.get("instructions")
        )

        super().__init__(extra_body_parameters=merged_extra_body, **kwargs)

    def _build_identifier(self) -> ComponentIdentifier:
        return self._create_identifier(
            params={
                "temperature": self._temperature,
                "top_p": self._top_p,
                "max_output_tokens": self._max_output_tokens,
                "reasoning_effort": self._reasoning_effort,
                "reasoning_summary": self._reasoning_summary,
                "retrieval_store_id": self._retrieval_store_id,
                "retrieval_mode": self._retrieval_mode,
                "max_num_results": self._max_num_results,
            },
        )

    async def send_prompt_async(self, *, message: Message) -> list[Message]:
        logger.debug(
            "OpenAIVectorStoreTarget sending prompt with model=%s endpoint=%s retrieval_store_id=%s api_key_present=%s special_instructions_present=%s",
            self._model_name,
            self._endpoint,
            self._retrieval_store_id,
            bool(self._api_key),
            bool(self._system_instructions),
        )
        return await super().send_prompt_async(message=message)

    def _merge_tools(self, *, existing_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tools = [tool for tool in existing_tools if tool.get("type") != "file_search"]
        tools.append(self._build_file_search_tool())
        return tools

    def _build_file_search_tool(self) -> dict[str, Any]:
        tool: dict[str, Any] = {
            "type": "file_search",
            "vector_store_ids": [self._retrieval_store_id],
        }
        if self._max_num_results is not None:
            tool["max_num_results"] = self._max_num_results
        return tool

    def _merge_include(self, *, existing_include: list[Any]) -> list[Any]:
        include = list(existing_include)
        required_include = "file_search_call.results"
        if required_include not in include:
            include.append(required_include)
        return include

    def _merge_instructions(self, *, existing_instructions: Any) -> Optional[str]:
        existing_text = str(existing_instructions).strip() if existing_instructions is not None else ""
        saved_text = self._system_instructions or ""
        if saved_text and existing_text:
            return f"{saved_text}\n\n{existing_text}"
        if saved_text:
            return saved_text
        if existing_text:
            return existing_text
        return None
