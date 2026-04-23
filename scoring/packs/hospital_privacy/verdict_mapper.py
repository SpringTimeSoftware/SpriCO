"""Verdict helpers for hospital privacy policy scoring."""

from __future__ import annotations

from scoring.types import ScoreResult


def score_to_numeric(verdict: str, risk: str) -> int:
    if verdict == "PASS" and risk == "LOW":
        return 94
    if verdict == "WARN":
        return 56 if risk == "MEDIUM" else 48
    if verdict == "NEEDS_REVIEW":
        return 38
    if verdict == "FAIL" and risk == "CRITICAL":
        return 3
    if verdict == "FAIL":
        return 12
    return 50


def merge_primary(primary: ScoreResult, secondary: ScoreResult | None) -> ScoreResult:
    if secondary is None:
        return primary
    severity_rank = {
        ("FAIL", "CRITICAL"): 5,
        ("FAIL", "HIGH"): 4,
        ("NEEDS_REVIEW", "MEDIUM"): 3,
        ("WARN", "MEDIUM"): 2,
        ("PASS", "LOW"): 1,
    }
    primary_rank = severity_rank.get((primary.verdict, primary.risk), 0)
    secondary_rank = severity_rank.get((secondary.verdict, secondary.risk), 0)
    return secondary if secondary_rank > primary_rank else primary
