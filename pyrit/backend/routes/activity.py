"""Unified SpriCO activity history API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from audit.database import AuditDatabase
from pyrit.backend.sprico.integrations.garak.reports import build_garak_scan_reports
from pyrit.backend.sprico.storage import get_storage_backend
from pyrit.memory import CentralMemory

router = APIRouter(tags=["activity"])


@router.get("/activity/history")
async def get_activity_history(limit: int = Query(5, ge=1, le=25)) -> dict[str, Any]:
    backend = get_storage_backend()
    audit_db = AuditDatabase()

    pyrit_attacks = _pyrit_attack_items(limit=limit)
    audit_runs = audit_db.get_recent_runs(limit=limit)
    interactive_runs = audit_db.get_recent_interactive_runs(limit=limit)
    scanner_reports = build_garak_scan_reports(backend.list_records("garak_runs"))[:limit]
    red_scans = backend.list_records("red_scans")[:limit]
    shield_events = backend.list_records("shield_events")[:limit]
    evidence_items = backend.list_records("evidence_items")[:limit]
    findings = backend.list_records("findings")[:limit]

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
                description="Saved Interactive Audit replays and structured audit runs from audit.db.",
                count=_safe_len(interactive_runs) + _count_audit_runs(audit_db),
                navigation_view="audit",
                items=[
                    *[_audit_item(run, "Saved Interactive Audit") for run in interactive_runs[:limit]],
                    *[_audit_item(run, "Structured Audit Run") for run in audit_runs[: max(0, limit - len(interactive_runs))]],
                ][:limit],
            ),
            _category(
                key="scanner_runs",
                title="Scanner Runs",
                description="LLM Vulnerability Scanner jobs, including completed no-finding and not-evaluated runs.",
                count=len(backend.list_records("garak_runs")),
                navigation_view="scanner-reports",
                items=[_scanner_item(report) for report in scanner_reports],
            ),
            _category(
                key="red_team_campaigns",
                title="Red Team Campaigns",
                description="SpriCO-native campaign runs. DeepTeam/promptfoo runtime is not enabled in this phase.",
                count=len(backend.list_records("red_scans")),
                navigation_view="red",
                items=[_red_item(scan) for scan in red_scans],
            ),
            _category(
                key="shield_events",
                title="Shield Events",
                description="SpriCO Shield checks stored as policy/evidence events.",
                count=len(backend.list_records("shield_events")),
                navigation_view="shield",
                items=[_evidence_item(event, "Shield Event") for event in shield_events],
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


def _count_audit_runs(audit_db: AuditDatabase) -> int:
    try:
        return len(audit_db.get_recent_runs(limit=500))
    except Exception:
        return 0


def _audit_item(run: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "id": _text(run.get("job_id") or run.get("id")),
        "title": _text(run.get("target_registry_name") or run.get("target_id") or kind),
        "subtitle": kind,
        "status": _text(run.get("status"), "recorded"),
        "created_at": _text(run.get("completed_at") or run.get("updated_at") or run.get("created_at")),
    }


def _scanner_item(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _text(report.get("scan_id") or report.get("id")),
        "title": _text(report.get("target_name") or report.get("target_id") or "Scanner run"),
        "subtitle": _text(report.get("scan_profile"), "profile not recorded"),
        "status": _scanner_status(report),
        "created_at": _text(report.get("finished_at") or report.get("started_at")),
    }


def _scanner_status(report: dict[str, Any]) -> str:
    status = _text(report.get("status"), "unknown")
    if status == "completed_no_findings":
        return "Completed - no findings"
    if _text(report.get("final_sprico_verdict")) == "NOT_EVALUATED":
        return "Not evaluated"
    return status


def _red_item(scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _text(scan.get("id")),
        "title": _text(scan.get("target_id"), "Red Team Campaign"),
        "subtitle": _text(scan.get("engine"), "sprico-native"),
        "status": _text(scan.get("status"), "recorded"),
        "created_at": _text(scan.get("updated_at") or scan.get("created_at")),
    }


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


def _safe_len(value: list[Any]) -> int:
    return len(value) if isinstance(value, list) else 0


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value)
    return text if text else fallback
