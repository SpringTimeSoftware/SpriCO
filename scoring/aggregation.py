"""Worst-risk aggregation helpers for SpriCO decisions."""

from __future__ import annotations

from scoring.types import AggregateScoreResult, ScoreResult, Verdict, ViolationRisk

_SEVERITY_RANK = {
    (Verdict.FAIL.value, ViolationRisk.CRITICAL.value): 6,
    (Verdict.FAIL.value, ViolationRisk.HIGH.value): 5,
    (Verdict.NEEDS_REVIEW.value, ViolationRisk.HIGH.value): 4,
    (Verdict.NEEDS_REVIEW.value, ViolationRisk.MEDIUM.value): 3,
    (Verdict.WARN.value, ViolationRisk.MEDIUM.value): 2,
    (Verdict.PASS.value, ViolationRisk.LOW.value): 1,
}


def worst_result(results: list[ScoreResult]) -> ScoreResult | None:
    """Return the worst result so PASS counts cannot hide severe failures."""

    if not results:
        return None
    return max(results, key=lambda result: _rank(result))


def aggregate_results(results: list[ScoreResult]) -> AggregateScoreResult:
    worst = worst_result(results)
    return AggregateScoreResult(
        verdict=worst.verdict if worst else Verdict.PASS.value,
        risk=worst.risk if worst else ViolationRisk.LOW.value,
        explanation=worst.explanation if worst else "No findings were generated.",
        matched_rules=list(worst.matched_rules) if worst else [],
        findings=list(results),
    )


def _rank(result: ScoreResult) -> int:
    return _SEVERITY_RANK.get((result.verdict, result.risk), 0)
