"""Optional judge-model configuration metadata.

Judge models are evidence sources only. They never produce SpriCO final verdicts.
"""

from __future__ import annotations

import os
from typing import Any


OPENAI_PROVIDER_ID = "openai"
FINAL_VERDICT_AUTHORITY = "sprico_policy_decision_engine"
DEFAULT_BLOCKED_DOMAINS = ["healthcare", "hospital"]


def get_judge_status() -> dict[str, Any]:
    """Return safe judge-model configuration metadata without exposing secrets."""

    api_key_configured = bool(os.getenv("OPENAI_API_KEY"))
    model = os.getenv("SPRICO_OPENAI_JUDGE_MODEL", "").strip()
    configured = api_key_configured and bool(model)
    enabled = configured and _env_truthy("SPRICO_OPENAI_JUDGE_ENABLED", default=False)
    allow_raw = enabled and _env_truthy("SPRICO_OPENAI_JUDGE_ALLOW_RAW", default=False)
    allowed_modes = ["disabled", "redacted"]
    if allow_raw:
        allowed_modes.append("raw")

    return {
        "enabled": enabled,
        "configured": configured,
        "providers": [
            {
                "id": OPENAI_PROVIDER_ID,
                "label": "OpenAI Judge",
                "configured": configured,
                "enabled": enabled,
                "enabled_by_default": False,
                "final_verdict_capable": False,
                "supports_redaction": True,
                "allowed_modes": allowed_modes,
                "blocked_for_domains_by_default": DEFAULT_BLOCKED_DOMAINS,
                "configure_hint": (
                    "Set SPRICO_OPENAI_JUDGE_ENABLED=true, SPRICO_OPENAI_JUDGE_MODEL, and OPENAI_API_KEY "
                    "in the backend environment. API keys must not be entered in the frontend."
                ),
            }
        ],
        "final_verdict_authority": FINAL_VERDICT_AUTHORITY,
    }


def _env_truthy(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
