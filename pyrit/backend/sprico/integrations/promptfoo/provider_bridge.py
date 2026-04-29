"""Python provider bridge used by promptfoo-generated runtime configs."""

from __future__ import annotations

import asyncio
from typing import Any

from pyrit.backend.services.target_service import get_target_service
from pyrit.models import Message, MessagePiece


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    config = dict((options or {}).get("config") or {})
    prompt_text = str(
        prompt
        or ((context or {}).get("vars") or {}).get("__prompt")
        or ((context or {}).get("vars") or {}).get("prompt")
        or ((context or {}).get("vars") or {}).get("message")
        or ""
    )
    target_registry_name = str(config.get("target_registry_name") or "").strip()
    if not target_registry_name:
        raise ValueError("target_registry_name is required in the promptfoo provider config")
    output = asyncio.run(_send_prompt(target_registry_name=target_registry_name, prompt_text=prompt_text))
    return {"output": output}


async def _send_prompt(*, target_registry_name: str, prompt_text: str) -> str:
    target = get_target_service().get_target_object(target_registry_name=target_registry_name)
    if target is None:
        raise ValueError(f"Target '{target_registry_name}' was not found")
    message = Message(
        [
            MessagePiece(
                role="user",
                original_value=prompt_text,
                converted_value=prompt_text,
                conversation_id=f"promptfoo::{target_registry_name}",
                sequence=0,
            )
        ]
    )
    responses = await target.send_prompt_async(message=message)
    if not responses:
        return ""
    if not isinstance(responses, list):
        responses = [responses]
    parts: list[str] = []
    for response in responses:
        for piece in getattr(response, "message_pieces", []):
            converted = getattr(piece, "converted_value", None)
            converted_type = getattr(piece, "converted_value_data_type", None)
            original = getattr(piece, "original_value", None)
            original_type = getattr(piece, "original_value_data_type", None)
            if converted_type == "text" and converted:
                parts.append(str(converted))
            elif original_type == "text" and original:
                parts.append(str(original))
    return "\n".join(part for part in parts if part).strip()
