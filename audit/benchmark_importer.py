# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""Import helpers for public benchmark and FlipAttack-style artifacts."""

from __future__ import annotations

from typing import Any

REFERENCE_NOTICE = "Public benchmark reference data; not client evidence."


def parse_flipattack_artifact(payload: dict[str, Any], *, source_type: str = "public_json") -> dict[str, Any]:
    """Normalize a FlipAttack-style JSON artifact into benchmark source/scenario/media rows.

    Public benchmark JSON files vary by release. This parser intentionally accepts
    common container names (`scenarios`, `results`, `cases`, `items`) and common
    prompt/result field names without treating public benchmark outputs as client
    audit evidence.
    """

    source_payload = payload.get("source") if isinstance(payload.get("source"), dict) else payload
    family = str(source_payload.get("benchmark_family") or source_payload.get("family") or "FlipAttack")
    source_name = str(source_payload.get("source_name") or source_payload.get("name") or f"{family} Benchmark Import")
    source = {
        "source_name": source_name,
        "source_type": source_payload.get("source_type") or source_type,
        "source_uri": source_payload.get("source_uri") or source_payload.get("uri"),
        "benchmark_family": family,
        "model_name": source_payload.get("model_name") or source_payload.get("model"),
        "version": source_payload.get("version"),
        "category_name": source_payload.get("category_name") or source_payload.get("category"),
        "subcategory_name": source_payload.get("subcategory_name") or source_payload.get("subcategory"),
        "scenario_id": source_payload.get("scenario_id"),
        "title": source_payload.get("title") or source_name,
        "description": source_payload.get("description") or REFERENCE_NOTICE,
        "metadata": {
            **_as_dict(source_payload.get("metadata")),
            "reference_data_notice": REFERENCE_NOTICE,
            "raw_keys": sorted(str(key) for key in payload.keys()),
        },
    }

    scenarios = [
        _normalize_scenario(item, source=source, index=index)
        for index, item in enumerate(_first_list(payload, "scenarios", "results", "cases", "items"), start=1)
        if isinstance(item, dict)
    ]
    media = [
        _normalize_media(item, index=index)
        for index, item in enumerate(_first_list(payload, "media", "assets", "gifs", "case_studies"), start=1)
        if isinstance(item, dict)
    ]
    return {"source": source, "scenarios": scenarios, "media": media}


def _normalize_scenario(item: dict[str, Any], *, source: dict[str, Any], index: int) -> dict[str, Any]:
    scenario_code = item.get("scenario_code") or item.get("scenario_id") or item.get("id") or item.get("case_id") or f"flipattack-{index:04d}"
    prompt_text = item.get("prompt_text") or item.get("prompt") or item.get("input") or item.get("attack_prompt") or item.get("transformed_prompt")
    category = item.get("category_name") or item.get("category") or source.get("category_name") or "Unspecified"
    return {
        "scenario_code": str(scenario_code),
        "title": item.get("title") or item.get("name") or item.get("attack_name") or f"FlipAttack Scenario {index}",
        "category_name": category,
        "subcategory_name": item.get("subcategory_name") or item.get("subcategory") or item.get("attack_type"),
        "objective_text": item.get("objective_text") or item.get("objective") or item.get("description"),
        "prompt_text": prompt_text,
        "expected_behavior_text": item.get("expected_behavior_text") or item.get("expected_behavior") or item.get("expected_output"),
        "modality": item.get("modality") or "text",
        "recommended_target_types": item.get("recommended_target_types") or item.get("target_types") or ["OpenAIChatTarget", "HTTP_TARGET", "CUSTOM_TARGET"],
        "tags": item.get("tags") or ["public-reference", "flipattack"],
        "severity_hint": item.get("severity_hint") or item.get("severity"),
        "replay_supported": bool(item.get("replay_supported", bool(prompt_text))),
    }


def _normalize_media(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    media_uri = item.get("media_uri") or item.get("uri") or item.get("url") or item.get("path")
    if not media_uri:
        raise ValueError(f"Benchmark media item {index} is missing media_uri/url/path")
    return {
        "scenario_id": item.get("scenario_id") or item.get("scenario_code") or item.get("case_id"),
        "media_type": item.get("media_type") or item.get("type") or "gif",
        "media_uri": media_uri,
        "thumbnail_uri": item.get("thumbnail_uri") or item.get("thumbnail"),
        "caption": item.get("caption") or item.get("title") or REFERENCE_NOTICE,
        "sort_order": int(item.get("sort_order") or index),
    }


def _first_list(payload: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
