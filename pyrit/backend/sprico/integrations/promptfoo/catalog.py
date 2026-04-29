"""Curated promptfoo plugin and strategy catalog for the SpriCO UI."""

from __future__ import annotations

import hashlib
import json
from typing import Any

PLUGIN_GROUPS: list[dict[str, Any]] = [
    {
        "id": "security_access",
        "label": "Security / Access Control",
        "description": "Access control, prompt injection, and privilege-boundary checks.",
        "default_plugins": [
            "bola",
            "bfla",
            "rbac",
            "ssrf",
            "sql-injection",
            "shell-injection",
            "debug-access",
            "excessive-agency",
        ],
    },
    {
        "id": "trust_safety",
        "label": "Trust / Safety",
        "description": "Jailbreak, harmful output, bias, and safety-behavior checks.",
        "default_plugins": [
            "jailbreak",
            "harmful:hate",
            "harmful:violence",
            "harmful:self-harm",
            "toxicity",
            "bias",
        ],
    },
    {
        "id": "medical_healthcare",
        "label": "Medical / Healthcare",
        "description": "Healthcare safety, privacy, and sensitive-data behavior checks.",
        "default_plugins": [
            "pii",
            "harmful:medical",
            "medical",
            "privacy",
        ],
    },
    {
        "id": "compliance_legal",
        "label": "Compliance / Legal",
        "description": "Legal, regulated-domain, and policy-boundary checks.",
        "default_plugins": [
            "contracts",
            "policy",
            "legal",
            "compliance",
        ],
    },
    {
        "id": "dataset_rag",
        "label": "Dataset / RAG",
        "description": "RAG poisoning, exfiltration, and retrieval boundary checks.",
        "default_plugins": [
            "rag-document-exfiltration",
            "rag-poisoning",
            "prompt-extraction",
            "cross-session-leak",
        ],
    },
    {
        "id": "brand_custom",
        "label": "Brand / Custom",
        "description": "Brand, custom plugin, and organization-specific checks.",
        "default_plugins": [
            "custom",
            "competitors",
            "hallucination",
            "misinformation",
        ],
    },
]

STRATEGIES: list[dict[str, Any]] = [
    {
        "id": "jailbreak",
        "label": "Jailbreak",
        "description": "Iterative single-turn jailbreak refinement.",
        "cost": "high",
        "recommended": True,
        "default_selected": True,
    },
    {
        "id": "jailbreak:meta",
        "label": "Meta-Agent Jailbreaks",
        "description": "Strategic meta-agent jailbreak planning.",
        "cost": "high",
        "recommended": True,
        "default_selected": True,
    },
    {
        "id": "jailbreak:composite",
        "label": "Composite Jailbreaks",
        "description": "Combined jailbreak techniques for higher attack success.",
        "cost": "medium",
        "recommended": True,
        "default_selected": True,
    },
    {
        "id": "base64",
        "label": "Base64",
        "description": "Base64 encoding bypass attempts.",
        "cost": "low",
        "recommended": False,
        "default_selected": False,
    },
    {
        "id": "rot13",
        "label": "ROT13",
        "description": "ROT13 encoding bypass attempts.",
        "cost": "low",
        "recommended": False,
        "default_selected": False,
    },
    {
        "id": "jailbreak-templates",
        "label": "Jailbreak Templates",
        "description": "Known static jailbreak templates.",
        "cost": "low",
        "recommended": False,
        "default_selected": False,
    },
    {
        "id": "crescendo",
        "label": "Crescendo",
        "description": "Multi-turn escalation strategy.",
        "cost": "high",
        "recommended": False,
        "default_selected": False,
    },
    {
        "id": "goat",
        "label": "GOAT",
        "description": "Generative Offensive Agent Tester multi-turn strategy.",
        "cost": "high",
        "recommended": False,
        "default_selected": False,
    },
    {
        "id": "jailbreak:hydra",
        "label": "Hydra Multi-turn",
        "description": "Adaptive multi-turn branching jailbreak strategy.",
        "cost": "high",
        "recommended": False,
        "default_selected": False,
    },
    {
        "id": "mischievous-user",
        "label": "Mischievous User",
        "description": "Persistent mischievous-user multi-turn strategy.",
        "cost": "high",
        "recommended": False,
        "default_selected": False,
    },
    {
        "id": "retry",
        "label": "Retry",
        "description": "Regression strategy that retries previously failing cases.",
        "cost": "low",
        "recommended": False,
        "default_selected": False,
    },
]

PLUGIN_LABELS: dict[str, str] = {
    "bola": "BOLA",
    "bfla": "BFLA",
    "rbac": "RBAC",
    "ssrf": "SSRF",
    "sql-injection": "SQL Injection",
    "shell-injection": "Shell Injection",
    "debug-access": "Debug Access",
    "excessive-agency": "Excessive Agency",
    "jailbreak": "Jailbreak",
    "harmful:hate": "Harmful - Hate",
    "harmful:violence": "Harmful - Violence",
    "harmful:self-harm": "Harmful - Self Harm",
    "toxicity": "Toxicity",
    "bias": "Bias",
    "pii": "PII / PHI",
    "harmful:medical": "Harmful - Medical",
    "medical": "Medical",
    "privacy": "Privacy",
    "contracts": "Contracts",
    "policy": "Policy",
    "intent": "Custom Intent",
    "legal": "Legal",
    "compliance": "Compliance",
    "rag-document-exfiltration": "RAG Document Exfiltration",
    "rag-poisoning": "RAG Poisoning",
    "prompt-extraction": "Prompt Extraction",
    "cross-session-leak": "Cross-session Leak",
    "custom": "Custom",
    "competitors": "Competitors",
    "hallucination": "Hallucination",
    "misinformation": "Misinformation",
}

SUPPORTED_MODES = [
    "single_target",
    "multi_target_comparison",
    "suite_assertion_overlay",
    "policy_comparison",
]


def build_promptfoo_catalog(
    *,
    discovered_plugins: list[str] | None = None,
    promptfoo_version: str | None = None,
    discovered_at: str | None = None,
) -> dict[str, Any]:
    plugin_ids = _normalize_plugins(discovered_plugins)
    plugin_groups = [_build_group(group, plugin_ids=plugin_ids) for group in PLUGIN_GROUPS]
    unmatched = [plugin_id for plugin_id in plugin_ids if not any(_plugin_in_group(plugin_id, group["id"]) for group in PLUGIN_GROUPS)]
    if unmatched:
        plugin_groups[-1]["plugins"].extend(
            _plugin_payload(
                plugin_id,
                default_selected=False,
                group_id=str(plugin_groups[-1]["id"]),
                group_label=str(plugin_groups[-1]["label"]),
            )
            for plugin_id in sorted(unmatched)
        )
    plugins = _flatten_plugins(plugin_groups)
    catalog = {
        "promptfoo_version": promptfoo_version,
        "discovered_at": discovered_at,
        "plugin_groups": plugin_groups,
        "plugins": plugins,
        "strategies": STRATEGIES,
        "supported_modes": SUPPORTED_MODES,
        "final_verdict_capable": False,
        "promptfoo_is_optional": True,
    }
    catalog["catalog_hash"] = _catalog_hash(catalog)
    return catalog


def _build_group(group: dict[str, Any], *, plugin_ids: list[str]) -> dict[str, Any]:
    if plugin_ids:
        available = [plugin_id for plugin_id in plugin_ids if _plugin_in_group(plugin_id, str(group["id"]))]
        default_plugins = [plugin_id for plugin_id in group["default_plugins"] if plugin_id in available]
        discovered_extras = sorted(plugin_id for plugin_id in available if plugin_id not in default_plugins)
        plugins = [*default_plugins, *discovered_extras]
        if not plugins:
            plugins = list(group["default_plugins"])
    else:
        plugins = list(group["default_plugins"])
    payloads = []
    for index, plugin_id in enumerate(plugins):
        payloads.append(
            _plugin_payload(
                plugin_id,
                default_selected=index < min(2, len(plugins)),
                group_id=str(group["id"]),
                group_label=str(group["label"]),
            )
        )
    return {
        "id": group["id"],
        "label": group["label"],
        "description": group["description"],
        "plugins": payloads,
    }


def _plugin_in_group(plugin_id: str, group_id: str) -> bool:
    lowered = plugin_id.lower()
    if group_id == "security_access":
        return any(token in lowered for token in ("bola", "bfla", "rbac", "auth", "access", "ssrf", "sql", "shell", "debug", "agency"))
    if group_id == "trust_safety":
        return any(token in lowered for token in ("harmful", "hate", "violence", "self-harm", "tox", "bias", "jailbreak"))
    if group_id == "medical_healthcare":
        return any(token in lowered for token in ("medical", "health", "phi", "pii", "privacy"))
    if group_id == "compliance_legal":
        return any(token in lowered for token in ("legal", "contract", "compliance", "policy"))
    if group_id == "dataset_rag":
        return any(token in lowered for token in ("rag", "retriev", "dataset", "poison", "exfil", "prompt-extraction", "session"))
    if group_id == "brand_custom":
        return True
    return False


def _plugin_payload(plugin_id: str, *, default_selected: bool, group_id: str, group_label: str) -> dict[str, Any]:
    return {
        "id": plugin_id,
        "label": PLUGIN_LABELS.get(plugin_id, plugin_id.replace("-", " ").replace(":", " / ").title()),
        "default_selected": default_selected,
        "group_id": group_id,
        "group_label": group_label,
        "available": True,
    }


def _normalize_plugins(discovered_plugins: list[str] | None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for item in discovered_plugins or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _flatten_plugins(plugin_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in plugin_groups:
        for plugin in group.get("plugins", []):
            plugin_id = str(plugin.get("id") or "").strip()
            if not plugin_id or plugin_id in seen:
                continue
            seen.add(plugin_id)
            items.append(dict(plugin))
    items.sort(key=lambda item: (str(item.get("group_label") or ""), str(item.get("label") or ""), str(item.get("id") or "")))
    return items


def _catalog_hash(catalog: dict[str, Any]) -> str:
    payload = {
        "promptfoo_version": catalog.get("promptfoo_version"),
        "plugin_groups": catalog.get("plugin_groups"),
        "plugins": catalog.get("plugins"),
        "strategies": catalog.get("strategies"),
        "supported_modes": catalog.get("supported_modes"),
        "final_verdict_capable": False,
        "promptfoo_is_optional": True,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
