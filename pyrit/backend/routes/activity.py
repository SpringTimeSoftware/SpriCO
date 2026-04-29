"""Unified SpriCO activity history API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from audit.database import AuditDatabase
from pyrit.backend.sprico.runs import SpriCORunRegistry
from pyrit.backend.sprico.storage import get_storage_backend
from pyrit.memory import CentralMemory

router = APIRouter(tags=["activity"])
_run_registry = SpriCORunRegistry()


@router.get("/activity/history")
async def get_activity_history(limit: int = Query(5, ge=1, le=25)) -> dict[str, Any]:
    backend = get_storage_backend()
    runs = _run_registry.list_runs(limit=5_000)

    pyrit_attacks = _pyrit_attack_items(limit=limit)
    evidence_items = backend.list_records("evidence_items")[:limit]
    findings = backend.list_records("findings")[:limit]
    audit_runs = [run for run in runs if run.get("run_type") in {"interactive_audit", "audit_workstation", "benchmark_replay", "sprico_auditspec"}]
    scanner_runs = [run for run in runs if run.get("run_type") == "garak_scan"]
    promptfoo_runs = [run for run in runs if run.get("run_type") == "promptfoo_runtime"]
    red_scans = [run for run in runs if run.get("run_type") == "red_campaign"]
    shield_runs = [run for run in runs if run.get("run_type") == "shield_check"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_note": (
            "Activity History is a cross-workflow index. Attack History remains scoped to PyRIT CentralMemory "
            "attack sessions and saved Interactive Audit runs."
        ),
        "categories": [
            _category(
                key="pyrit_attack_sessions",
                title="PyRIT Attack Sessions",
                description="Manual/interactive PyRIT CentralMemory attack sessions.",
                count=_count_pyrit_attacks(),
                navigation_view="history",
                items=pyrit_attacks,
            ),
            _category(
                key="interactive_audit_runs",
                title="Interactive/Audit Runs",
                description="Saved Interactive Audit replays, Audit Workstation runs, benchmark replays, and SpriCO AuditSpec runs from audit.db.",
                count=len(audit_runs),
                navigation_view="audit",
                items=[_run_item(run) for run in audit_runs[:limit]],
            ),
            _category(
                key="scanner_runs",
                title="Scanner Runs",
                description="LLM Vulnerability Scanner jobs, including completed no-finding and not-evaluated runs.",
                count=len(scanner_runs),
                navigation_view="scanner-reports",
                items=[_run_item(run) for run in scanner_runs[:limit]],
            ),
            _category(
                key="promptfoo_runs",
                title="promptfoo Runtime",
                description="Optional promptfoo runtime runs from Benchmark Library. Evidence is imported into SpriCO; final verdict authority remains SpriCO.",
                count=len(promptfoo_runs),
                navigation_view="benchmark-library",
                items=[_run_item(run) for run in promptfoo_runs[:limit]],
            ),
            _category(
                key="red_team_campaigns",
                title="Red Team Campaigns",
                description="SpriCO-native campaign runs. DeepTeam runtime is not enabled here; promptfoo runtime lives under Benchmark Library, not Red Team Campaigns.",
                count=len(red_scans),
                navigation_view="red",
                items=[_run_item(run) for run in red_scans[:limit]],
            ),
            _category(
                key="shield_events",
                title="Shield Events",
                description="SpriCO Shield checks stored as policy/evidence events.",
                count=len(shield_runs),
                navigation_view="shield",
                items=[_run_item(run) for run in shield_runs[:limit]],
            ),
            _category(
                key="evidence",
                title="Evidence",
                description="Normalized proof records from audits, scanners, campaigns, and Shield checks.",
                count=len(backend.list_records("evidence_items")),
                navigation_view="evidence",
                items=[_evidence_item(item, "Evidence") for item in evidence_items],
            ),
            _category(
                key="findings",
                title="Findings",
                description="Actionable SpriCO outcomes only.",
                count=len(backend.list_records("findings")),
                navigation_view="findings",
                items=[_finding_item(item) for item in findings],
            ),
        ],
    }


def _category(*, key: str, title: str, description: str, count: int, navigation_view: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "description": description,
        "count": count,
        "navigation_view": navigation_view,
        "items": items,
    }


def _pyrit_attack_items(*, limit: int) -> list[dict[str, Any]]:
    try:
        attacks = CentralMemory.get_memory_instance().get_attack_results()
    except Exception:
        return []
    items = []
    for attack in attacks[:limit]:
        attack_id = str(getattr(attack, "attack_result_id", None) or getattr(attack, "id", "") or "")
        items.append(
            {
                "id": attack_id,
                "title": attack_id or "PyRIT attack session",
                "subtitle": str(getattr(attack, "attack_type", "") or getattr(attack, "objective", "") or ""),
                "status": str(getattr(attack, "outcome", "") or "recorded"),
                "created_at": _text(getattr(attack, "created_at", None)),
            }
        )
    return items


def _count_pyrit_attacks() -> int:
    try:
        return len(CentralMemory.get_memory_instance().get_attack_results())
    except Exception:
        return 0


def _run_item(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _text(run.get("run_id") or run.get("id")),
        "title": _text(run.get("target_name") or run.get("target_id") or run.get("run_type") or "Run"),
        "subtitle": _text(run.get("run_type") or run.get("source_page"), "recorded"),
        "status": _run_status(run),
        "created_at": _text(run.get("finished_at") or run.get("started_at") or run.get("updated_at")),
    }


def _run_status(report: dict[str, Any]) -> str:
    status = _text(report.get("status"), "unknown")
    if status == "completed_no_findings":
        return "Completed - no findings"
    if _text(report.get("final_verdict")) == "NOT_EVALUATED":
        return "Not evaluated"
    return status


def _evidence_item(item: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "id": _text(item.get("finding_id") or item.get("id")),
        "title": _text(item.get("engine_name") or item.get("engine") or kind),
        "subtitle": _text(item.get("scan_id") or item.get("conversation_id") or item.get("target_id")),
        "status": _text(item.get("final_verdict") or (item.get("sprico_final_verdict") or {}).get("verdict"), "recorded"),
        "created_at": _text(item.get("created_at") or item.get("timestamp")),
    }


def _finding_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _text(item.get("id") or item.get("finding_id")),
        "title": _text(item.get("objective_id") or item.get("scan_id") or "Finding"),
        "subtitle": _text(item.get("policy_id")),
        "status": _text(item.get("verdict") or item.get("final_verdict"), "actionable"),
        "created_at": _text(item.get("created_at") or item.get("updated_at")),
    }


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value)
    return text if text else fallback
