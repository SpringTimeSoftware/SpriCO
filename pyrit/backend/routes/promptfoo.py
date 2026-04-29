"""Optional promptfoo runtime APIs."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from pyrit.backend.services.target_service import get_target_service
from pyrit.backend.sprico.integrations.promptfoo.runner import PromptfooRuntimeRunner

router = APIRouter(tags=["promptfoo"])
_runner = PromptfooRuntimeRunner()
ALLOWED_PROMPTFOO_SEVERITIES = {"low", "medium", "high", "critical"}
SECRET_PATTERN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|(?:api[_ -]?key|token|secret|password)\s*[:=]\s*[^\s,;]+)", re.IGNORECASE)
HOSPITAL_PHI_WARNING_PATTERN = re.compile(
    r"\b(?:mrn|medical record|patient|diagnosis|dob|date of birth|insurance id|discharge notes)\b|"
    r"\b\d{4}-\d{2}-\d{2}\b|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


class PromptfooRuntimeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_ids: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    domain: str = "generic"
    plugin_group_id: str = ""
    plugin_ids: list[str] = Field(default_factory=list)
    strategy_ids: list[str] = Field(default_factory=list)
    custom_policies: list["PromptfooCustomPolicyRequest"] = Field(default_factory=list)
    custom_intents: list["PromptfooCustomIntentRequest"] = Field(default_factory=list)
    suite_id: Optional[str] = None
    purpose: Optional[str] = None
    num_tests_per_plugin: int = Field(default=2, ge=1, le=10)
    max_concurrency: int = Field(default=2, ge=1, le=10)
    use_remote_generation: bool = False


class PromptfooCustomPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: Optional[str] = None
    policy_name: str
    policy_text: str
    severity: str = "medium"
    num_tests: int = Field(default=2, ge=1, le=10)
    domain: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class PromptfooCustomIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_id: Optional[str] = None
    intent_name: str
    prompt_text: Optional[str] = None
    prompt_sequence: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    severity: str = "medium"
    num_tests: int = Field(default=1, ge=1, le=10)
    tags: list[str] = Field(default_factory=list)


class PromptfooRuntimeLaunchRun(BaseModel):
    scan_id: str
    run_id: str
    target_id: str
    target_name: str
    policy_id: str
    policy_name: Optional[str] = None
    suite_id: Optional[str] = None
    suite_name: Optional[str] = None
    comparison_group_id: str
    comparison_mode: str
    comparison_label: str
    status: str


class PromptfooRuntimeLaunchResponse(BaseModel):
    comparison_group_id: str
    comparison_mode: str
    runs: list[PromptfooRuntimeLaunchRun]


PromptfooRuntimeRequest.model_rebuild()


@router.get("/promptfoo/status")
async def promptfoo_status() -> dict[str, Any]:
    return _runner.status()


@router.get("/promptfoo/catalog")
async def promptfoo_catalog() -> dict[str, Any]:
    return _runner.catalog()


@router.get("/promptfoo/runs")
async def list_promptfoo_runs(limit: int = Query(100, ge=1, le=1000)) -> list[dict[str, Any]]:
    runs = _runner.list_runs()
    runs.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return runs[:limit]


@router.get("/promptfoo/runs/{scan_id}")
async def get_promptfoo_run(scan_id: str) -> dict[str, Any]:
    run = _runner.get_run(scan_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"promptfoo run '{scan_id}' not found")
    return run


@router.post("/promptfoo/runs", response_model=PromptfooRuntimeLaunchResponse, status_code=status.HTTP_201_CREATED)
async def create_promptfoo_runs(request: PromptfooRuntimeRequest, background_tasks: BackgroundTasks) -> PromptfooRuntimeLaunchResponse:
    target_ids = _dedupe_strings(request.target_ids)
    if not target_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one target for promptfoo runtime.")
    policy_ids = _dedupe_strings(request.policy_ids) or ["policy_public_default"]
    plugin_ids = _dedupe_strings(request.plugin_ids)
    custom_policies, validation_warnings = _normalize_custom_policies(request.custom_policies, domain=request.domain)
    custom_intents, intent_warnings = _normalize_custom_intents(request.custom_intents, domain=request.domain)
    validation_warnings.extend(intent_warnings)
    if not plugin_ids and not custom_policies and not custom_intents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one promptfoo plugin.")
    strategy_ids = _dedupe_strings(request.strategy_ids)
    if not strategy_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one promptfoo strategy.")
    runtime_status = _runner.status()
    catalog = _runner.catalog()
    group = next((item for item in catalog.get("plugin_groups", []) if item.get("id") == request.plugin_group_id), None) if request.plugin_group_id else None
    if plugin_ids and group is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown promptfoo plugin group '{request.plugin_group_id}'.")
    allowed_plugins = {str(item.get("id") or "") for item in (group.get("plugins", []) if isinstance(group, dict) else [])}
    invalid_plugins = [plugin_id for plugin_id in plugin_ids if plugin_id not in allowed_plugins] if plugin_ids else []
    if invalid_plugins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected promptfoo plugin is not available in the current catalog. Missing: {', '.join(invalid_plugins)}",
        )
    allowed_strategies = {str(item.get("id") or "") for item in catalog.get("strategies", [])}
    invalid_strategies = [strategy_id for strategy_id in strategy_ids if strategy_id not in allowed_strategies]
    if invalid_strategies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected promptfoo strategy is not available in the current catalog. Missing: {', '.join(invalid_strategies)}",
        )
    selected_catalog_snapshot = {
        "plugin_group": {
            "id": group.get("id") if isinstance(group, dict) else "custom_business_logic",
            "label": group.get("label") if isinstance(group, dict) else "Custom Business Logic",
            "description": group.get("description") if isinstance(group, dict) else "Custom promptfoo policies and intents defined inside SpriCO.",
        },
        "plugins": [
            *[item for item in (group.get("plugins", []) if isinstance(group, dict) else []) if str(item.get("id") or "") in plugin_ids],
            *[_custom_policy_catalog_item(item) for item in custom_policies],
            *[_custom_intent_catalog_item(item) for item in custom_intents],
        ],
        "strategies": [item for item in catalog.get("strategies", []) if str(item.get("id") or "") in strategy_ids],
        "custom_policies": custom_policies,
        "custom_intents": custom_intents,
    }

    suite = None
    if request.suite_id:
        suite = _runner.get_suite(request.suite_id)
        if suite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AuditSpec suite '{request.suite_id}' not found")

    comparison_group_id = f"promptfoo_compare:{uuid.uuid4().hex[:12]}"
    comparison_mode = _comparison_mode(target_count=len(target_ids), policy_count=len(policy_ids))
    launches: list[PromptfooRuntimeLaunchRun] = []
    target_service = get_target_service()
    for target_id in target_ids:
        target = await target_service.get_target_async(target_registry_name=target_id)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target '{target_id}' not found")
        for policy_id in policy_ids:
            policy_record = _runner.get_policy(policy_id) or {}
            policy_name = str(policy_record.get("name") or policy_id)
            purpose = _purpose_for_run(request=request, suite=suite, target_name=target.display_name or target.target_registry_name, policy_name=policy_name)
            comparison_label = _comparison_label(
                target_label=target.display_name or target.target_registry_name,
                policy_id=policy_id,
                target_count=len(target_ids),
                policy_count=len(policy_ids),
            )
            run = _runner.create_pending_run(
                target_id=target.target_registry_name,
                target_name=target.display_name or target.target_registry_name,
                target_type=target.target_type,
                policy_id=policy_id,
                policy_name=policy_name,
                domain=request.domain,
                plugin_group_id=request.plugin_group_id or "custom_business_logic",
                plugin_group_label=str(group.get("label") if isinstance(group, dict) else "Custom Business Logic"),
                plugin_ids=plugin_ids,
                strategy_ids=strategy_ids,
                suite_id=suite.get("suite_id") if isinstance(suite, dict) else None,
                suite_name=suite.get("name") if isinstance(suite, dict) else None,
                purpose=purpose,
                comparison_group_id=comparison_group_id,
                comparison_mode=comparison_mode,
                comparison_label=comparison_label,
                num_tests_per_plugin=request.num_tests_per_plugin,
                max_concurrency=request.max_concurrency,
                use_remote_generation=request.use_remote_generation,
                custom_policies=custom_policies,
                custom_intents=custom_intents,
                validation_warnings=validation_warnings,
                promptfoo_status=runtime_status,
                catalog=catalog,
                selected_catalog_snapshot=selected_catalog_snapshot,
            )
            background_tasks.add_task(_execute_promptfoo_run_background, run["scan_id"])
            launches.append(
                PromptfooRuntimeLaunchRun(
                    scan_id=run["scan_id"],
                    run_id=f"promptfoo_runtime:{run['scan_id']}",
                    target_id=target.target_registry_name,
                    target_name=target.display_name or target.target_registry_name,
                    policy_id=policy_id,
                    policy_name=policy_name,
                    suite_id=run.get("suite_id"),
                    suite_name=run.get("suite_name"),
                    comparison_group_id=comparison_group_id,
                    comparison_mode=comparison_mode,
                    comparison_label=comparison_label,
                    status=run["status"],
                )
            )

    return PromptfooRuntimeLaunchResponse(
        comparison_group_id=comparison_group_id,
        comparison_mode=comparison_mode,
        runs=launches,
    )


def _execute_promptfoo_run_background(scan_id: str) -> None:
    _runner.execute_run(scan_id)


def _comparison_mode(*, target_count: int, policy_count: int) -> str:
    if target_count > 1 and policy_count > 1:
        return "cross_product_comparison"
    if target_count > 1:
        return "multi_target_comparison"
    if policy_count > 1:
        return "policy_comparison"
    return "single_target"


def _comparison_label(*, target_label: str, policy_id: str, target_count: int, policy_count: int) -> str:
    if target_count > 1 and policy_count > 1:
        return f"{target_label} | {policy_id}"
    if target_count > 1:
        return target_label
    if policy_count > 1:
        return policy_id
    return target_label


def _purpose_for_run(
    *,
    request: PromptfooRuntimeRequest,
    suite: dict[str, Any] | None,
    target_name: str,
    policy_name: str,
) -> str:
    explicit = str(request.purpose or "").strip()
    if explicit:
        return explicit
    suite_description = str((suite or {}).get("description") or "").strip()
    if suite_description:
        return suite_description
    domain = str(request.domain or "generic").strip()
    return f"Audit the {domain} target '{target_name}' under policy '{policy_name}' for unsafe or policy-bypassing behavior."


def _dedupe_strings(values: list[str] | None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _normalize_custom_policies(values: list[PromptfooCustomPolicyRequest], *, domain: str) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values, start=1):
        policy_name = str(value.policy_name or "").strip()
        policy_text = str(value.policy_text or "").strip()
        if not policy_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Custom policy {index} requires a policy name.")
        if not policy_text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Custom policy '{policy_name}' requires policy text.")
        if _contains_secret_like_content(policy_name) or _contains_secret_like_content(policy_text):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Custom policy '{policy_name}' must not contain secrets or API keys.")
        normalized_domain = str(value.domain or domain or "generic").strip().lower() or "generic"
        if normalized_domain == "hospital" and _looks_like_hospital_phi(policy_text):
            warnings.append(f"Custom policy '{policy_name}' contains hospital/PHI-like text. Use synthetic examples only.")
        policy_id = _safe_identifier(
            preferred=value.policy_id,
            fallback_text=policy_name,
            prefix="policy",
            seen=seen,
        )
        severity = _normalize_promptfoo_severity(value.severity, label=f"Custom policy '{policy_name}'")
        items.append(
            {
                "policy_id": policy_id,
                "policy_name": policy_name,
                "policy_text": policy_text,
                "policy_text_hash": _text_hash(policy_text),
                "severity": severity,
                "num_tests": int(value.num_tests),
                "domain": normalized_domain,
                "tags": _dedupe_strings(value.tags),
                "policy_text_redacted": True,
            }
        )
    return items, warnings


def _normalize_custom_intents(values: list[PromptfooCustomIntentRequest], *, domain: str) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values, start=1):
        intent_name = str(value.intent_name or "").strip()
        if not intent_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Custom intent {index} requires an intent name.")
        prompt_text = str(value.prompt_text or "").strip()
        prompt_sequence = [str(step or "").strip() for step in value.prompt_sequence if str(step or "").strip()]
        if prompt_sequence and any(not step for step in prompt_sequence):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Custom intent '{intent_name}' contains blank multi-step entries.")
        if not prompt_sequence and not prompt_text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Custom intent '{intent_name}' requires prompt text or a multi-step prompt sequence.")
        joined_text = "\n".join(prompt_sequence or [prompt_text])
        if _contains_secret_like_content(intent_name) or _contains_secret_like_content(joined_text):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Custom intent '{intent_name}' must not contain secrets or API keys.")
        normalized_domain = str(domain or "generic").strip().lower() or "generic"
        if normalized_domain == "hospital" and _looks_like_hospital_phi(joined_text):
            warnings.append(f"Custom intent '{intent_name}' contains hospital/PHI-like text. Use synthetic examples only.")
        intent_id = _safe_identifier(
            preferred=value.intent_id,
            fallback_text=intent_name,
            prefix="intent",
            seen=seen,
        )
        severity = _normalize_promptfoo_severity(value.severity, label=f"Custom intent '{intent_name}'")
        items.append(
            {
                "intent_id": intent_id,
                "intent_name": intent_name,
                "prompt_text": prompt_text or None,
                "prompt_sequence": prompt_sequence,
                "category": str(value.category or "").strip() or None,
                "severity": severity,
                "num_tests": int(value.num_tests),
                "tags": _dedupe_strings(value.tags),
                "intent_payload": prompt_sequence if prompt_sequence else prompt_text,
                "prompt_text_hash": _text_hash(joined_text),
                "multi_step": bool(prompt_sequence),
            }
        )
    return items, warnings


def _normalize_promptfoo_severity(value: str, *, label: str) -> str:
    severity = str(value or "medium").strip().lower() or "medium"
    if severity not in ALLOWED_PROMPTFOO_SEVERITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} must use one of: {', '.join(sorted(ALLOWED_PROMPTFOO_SEVERITIES))}.",
        )
    return severity


def _contains_secret_like_content(value: str) -> bool:
    return bool(value and SECRET_PATTERN.search(value))


def _looks_like_hospital_phi(value: str) -> bool:
    return bool(value and HOSPITAL_PHI_WARNING_PATTERN.search(value))


def _safe_identifier(*, preferred: str | None, fallback_text: str, prefix: str, seen: set[str]) -> str:
    candidate = re.sub(r"[^a-z0-9_]+", "_", str(preferred or "").strip().lower()).strip("_")
    if not candidate:
        candidate = re.sub(r"[^a-z0-9]+", "_", fallback_text.lower()).strip("_")
    candidate = candidate or uuid.uuid4().hex[:8]
    normalized = candidate if candidate.startswith(f"{prefix}_") else f"{prefix}_{candidate}"
    while normalized in seen:
        normalized = f"{prefix}_{candidate}_{uuid.uuid4().hex[:4]}"
    seen.add(normalized)
    return normalized


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _custom_policy_catalog_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"policy:{item.get('policy_id')}",
        "runtime_plugin_id": "policy",
        "label": f"Custom Policy: {item.get('policy_name')}",
        "group_id": "custom_business_logic",
        "group_label": "Custom Business Logic",
        "available": True,
        "default_selected": True,
        "policy_id": item.get("policy_id"),
        "policy_name": item.get("policy_name"),
        "policy_text_hash": item.get("policy_text_hash"),
        "severity": item.get("severity"),
        "tags": list(item.get("tags") or []),
    }


def _custom_intent_catalog_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"intent:{item.get('intent_id')}",
        "runtime_plugin_id": "intent",
        "label": f"Custom Intent: {item.get('intent_name')}",
        "group_id": "custom_business_logic",
        "group_label": "Custom Business Logic",
        "available": True,
        "default_selected": True,
        "intent_id": item.get("intent_id"),
        "intent_name": item.get("intent_name"),
        "prompt_text_hash": item.get("prompt_text_hash"),
        "category": item.get("category"),
        "severity": item.get("severity"),
        "multi_step": bool(item.get("multi_step")),
        "tags": list(item.get("tags") or []),
    }
