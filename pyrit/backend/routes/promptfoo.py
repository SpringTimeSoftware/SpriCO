"""Optional promptfoo runtime APIs."""

from __future__ import annotations

from typing import Any, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from pyrit.backend.services.target_service import get_target_service
from pyrit.backend.sprico.integrations.promptfoo.runner import PromptfooRuntimeRunner

router = APIRouter(tags=["promptfoo"])
_runner = PromptfooRuntimeRunner()


class PromptfooRuntimeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_ids: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    domain: str = "generic"
    plugin_group_id: str = ""
    plugin_ids: list[str] = Field(default_factory=list)
    strategy_ids: list[str] = Field(default_factory=list)
    suite_id: Optional[str] = None
    purpose: Optional[str] = None
    num_tests_per_plugin: int = Field(default=2, ge=1, le=10)
    max_concurrency: int = Field(default=2, ge=1, le=10)
    use_remote_generation: bool = False


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
    if not plugin_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one promptfoo plugin.")
    strategy_ids = _dedupe_strings(request.strategy_ids)
    catalog = _runner.catalog()
    group = next((item for item in catalog.get("plugin_groups", []) if item.get("id") == request.plugin_group_id), None)
    if group is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown promptfoo plugin group '{request.plugin_group_id}'.")
    allowed_plugins = {str(item.get("id") or "") for item in group.get("plugins", [])}
    invalid_plugins = [plugin_id for plugin_id in plugin_ids if plugin_id not in allowed_plugins]
    if invalid_plugins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown promptfoo plugin selection for group '{request.plugin_group_id}': {', '.join(invalid_plugins)}",
        )
    allowed_strategies = {str(item.get("id") or "") for item in catalog.get("strategies", [])}
    invalid_strategies = [strategy_id for strategy_id in strategy_ids if strategy_id not in allowed_strategies]
    if invalid_strategies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown promptfoo strategy selection: {', '.join(invalid_strategies)}",
        )

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
                plugin_group_id=request.plugin_group_id,
                plugin_group_label=str(group.get("label") or request.plugin_group_id),
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
