"""Report projections for persisted garak scanner runs."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


def build_garak_scan_report(run: dict[str, Any], *, policy_names: dict[str, str] | None = None) -> dict[str, Any]:
    """Build a user-facing scanner run report from an existing run/result record."""

    policy_names = policy_names or {}
    config = _dict(run.get("config"))
    policy_context = _dict(config.get("policy_context"))
    profile_resolution = _dict(run.get("profile_resolution") or config.get("profile_resolution"))
    artifacts = _list(run.get("artifacts"))
    findings = _list(run.get("findings"))
    scanner_evidence = _list(run.get("scanner_evidence"))
    signals = _list(run.get("signals"))
    aggregate = _dict(run.get("aggregate"))
    sprico_final_verdict = _dict(run.get("sprico_final_verdict"))
    scan_id = str(run.get("scan_id") or run.get("id") or "")
    policy_id = _text(run.get("policy_id") or config.get("policy_id") or policy_context.get("policy_id"))
    resolved_probes = _string_list(profile_resolution.get("probes"))
    skipped_probe_details = _skipped_details(profile_resolution, "probes")
    detectors = _string_list(profile_resolution.get("detectors"))
    buffs = _string_list(profile_resolution.get("buffs"))
    started_at = _text(run.get("started_at"))
    finished_at = _text(run.get("finished_at"))
    evidence_count = _int(run.get("evidence_count"), fallback=len(scanner_evidence))
    findings_count = _int(run.get("findings_count"), fallback=len(findings))
    artifact_count = len(artifacts)
    status = _text(run.get("status"), "not_evaluated")
    risk = _text(run.get("risk") or sprico_final_verdict.get("violation_risk") or aggregate.get("worst_risk"))
    verdict = _text(run.get("final_verdict") or sprico_final_verdict.get("verdict") or aggregate.get("final_verdict"))

    report = {
        "scan_id": scan_id,
        "id": scan_id,
        "target_id": _text(run.get("target_id") or config.get("target_id") or policy_context.get("target_id")),
        "target_name": _text(run.get("target_name") or config.get("target_name") or policy_context.get("target_name")),
        "target_type": _text(run.get("target_type") or config.get("target_type") or policy_context.get("target_type")),
        "policy_id": policy_id,
        "policy_name": policy_names.get(policy_id) or _text(policy_context.get("policy_name")),
        "scan_profile": _text(run.get("scan_profile") or config.get("scan_profile") or profile_resolution.get("scan_profile")),
        "vulnerability_categories": _categories(run, config, policy_context, profile_resolution),
        "profile_resolution": profile_resolution,
        "resolved_probes_count": len(resolved_probes),
        "resolved_probes": resolved_probes,
        "skipped_probes_count": len(skipped_probe_details),
        "skipped_probes": [item["name"] for item in skipped_probe_details],
        "skipped_probe_details": skipped_probe_details,
        "detectors_count": len(detectors),
        "detectors": detectors,
        "buffs_count": len(buffs),
        "buffs": buffs,
        "default_generations": _int(
            profile_resolution.get("default_generations"),
            fallback=_int(config.get("max_attempts"), fallback=_int(config.get("generations"), fallback=None)),
        ),
        "timeout_seconds": _int(
            profile_resolution.get("timeout_seconds"),
            fallback=_int(profile_resolution.get("default_timeout_seconds"), fallback=_int(config.get("timeout_seconds"), fallback=None)),
        ),
        "status": status,
        "evaluation_status": _text(run.get("evaluation_status")),
        "failure_reason": run.get("failure_reason"),
        "evidence_count": evidence_count,
        "findings_count": findings_count,
        "artifact_count": artifact_count,
        "final_sprico_verdict": verdict,
        "final_verdict": verdict,
        "violation_risk": risk,
        "risk": risk,
        "data_sensitivity": _text(sprico_final_verdict.get("data_sensitivity") or aggregate.get("data_sensitivity")),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": _duration_seconds(started_at, finished_at),
        "finding_ids": [_text(item.get("finding_id") or item.get("id")) for item in findings if isinstance(item, dict)],
        "findings": findings,
        "scanner_evidence": scanner_evidence,
        "signals": signals,
        "sprico_final_verdict": sprico_final_verdict,
        "aggregate": aggregate,
        "artifacts": artifacts,
        "garak": _dict(run.get("garak")),
        "raw_findings": _list(run.get("raw_findings")),
        "config": config,
    }
    return report


def build_garak_scan_reports(runs: list[dict[str, Any]], *, policy_names: dict[str, str] | None = None) -> list[dict[str, Any]]:
    reports = [build_garak_scan_report(run, policy_names=policy_names) for run in runs]
    return sorted(reports, key=lambda item: _text(item.get("finished_at") or item.get("started_at")), reverse=True)


def summarize_garak_scan_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = Counter(_text(report.get("status"), "unknown") for report in reports)
    by_target = Counter(_text(report.get("target_name") or report.get("target_id"), "unknown") for report in reports)
    by_profile = Counter(_text(report.get("scan_profile"), "unknown") for report in reports)
    with_findings = sum(1 for report in reports if _int(report.get("findings_count")) > 0)
    no_findings = sum(1 for report in reports if _text(report.get("status")).lower() == "completed_no_findings")
    high_critical = sum(
        1
        for report in reports
        if _text(report.get("violation_risk") or report.get("risk")).upper() in {"HIGH", "CRITICAL"}
        or any(_text(item.get("severity")).upper() in {"HIGH", "CRITICAL"} for item in _list(report.get("findings")) if isinstance(item, dict))
    )
    return {
        "scanner_runs_total": len(reports),
        "scanner_runs_by_status": _counter_rows(by_status, "status"),
        "scanner_runs_by_target": _counter_rows(by_target, "target"),
        "scanner_runs_by_profile": _counter_rows(by_profile, "profile"),
        "scanner_runs_with_findings": with_findings,
        "scanner_runs_with_no_findings": no_findings,
        "high_critical_scanner_findings": high_critical,
        "scanner_evidence_count": sum(_int(report.get("evidence_count")) for report in reports),
        "artifacts_stored": sum(_int(report.get("artifact_count")) for report in reports),
    }


def _counter_rows(counter: Counter[str], key: str) -> list[dict[str, Any]]:
    return [{key: name, "count": count} for name, count in sorted(counter.items())]


def _categories(
    run: dict[str, Any],
    config: dict[str, Any],
    policy_context: dict[str, Any],
    profile_resolution: dict[str, Any],
) -> list[str]:
    for value in (
        run.get("vulnerability_categories"),
        config.get("vulnerability_categories"),
        profile_resolution.get("categories"),
        policy_context.get("vulnerability_categories"),
    ):
        categories = _string_list(value)
        if categories:
            return categories
    return []


def _skipped_details(profile_resolution: dict[str, Any], key: str) -> list[dict[str, str]]:
    skipped = profile_resolution.get("skipped")
    if not isinstance(skipped, dict):
        return []
    value = skipped.get(key)
    items: list[dict[str, str]] = []
    if isinstance(value, list):
        items.extend({"name": _text(item), "reason": "Reason not recorded."} for item in value)
    elif isinstance(value, dict):
        for name, reason in value.items():
            items.append({"name": _text(name), "reason": _text(reason, "Reason not recorded.")})
    else:
        for maybe_items in skipped.values():
            if isinstance(maybe_items, list):
                items.extend({"name": _text(item), "reason": "Reason not recorded."} for item in maybe_items)
    return [item for item in items if item["name"]]


def _duration_seconds(started_at: str, finished_at: str) -> int | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    seconds = int((finished - started).total_seconds())
    return seconds if seconds >= 0 else None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [_text(item) for item in value] if isinstance(value, list) else []


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value)
    return text if text else fallback


def _int(value: Any, fallback: int | None = 0) -> int | None:
    if value is None or value == "":
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
