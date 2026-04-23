"""Normalize scan runner output into SpriCO-friendly JSON."""

from __future__ import annotations

from typing import Any


def normalize_scan_result(*, scan_id: str, status: str, findings: list[dict[str, Any]], raw_results: list[dict[str, Any]]) -> dict[str, Any]:
    critical_fail_count = sum(1 for item in findings if item.get("verdict") == "FAIL" and item.get("risk") == "CRITICAL")
    high_fail_count = sum(1 for item in findings if item.get("verdict") == "FAIL" and item.get("risk") == "HIGH")
    needs_review_count = sum(1 for item in findings if item.get("verdict") == "NEEDS_REVIEW")
    pass_count = sum(1 for item in findings if item.get("verdict") == "PASS")
    worst_risk = "CRITICAL" if critical_fail_count else "HIGH" if high_fail_count else "MEDIUM" if needs_review_count else "LOW"
    final_verdict = "FAIL" if critical_fail_count or high_fail_count else "NEEDS_REVIEW" if needs_review_count else "PASS"
    return {
        "scan_id": scan_id,
        "status": status,
        "findings": findings,
        "raw_results": raw_results,
        "aggregate": {
            "critical_fail_count": critical_fail_count,
            "high_fail_count": high_fail_count,
            "needs_review_count": needs_review_count,
            "pass_count": pass_count,
            "worst_risk": worst_risk,
            "final_verdict": final_verdict,
        },
    }
