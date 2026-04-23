"""Scorer registry bridge for SpriCO scans."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from scoring.registry import BaseSpriCOScorer, get_registered_scorer
from pyrit.backend.sprico.pyrit_adapter.errors import UnsupportedPyRITFeatureError


class PyRITScorerAdapter:
    """Best-effort wrapper surface for PyRIT or SpriCO scorers."""

    def __init__(self, scorer: BaseSpriCOScorer) -> None:
        self.scorer = scorer

    def score_turn(self, *, turn: dict[str, Any], conversation_history: list[dict[str, Any]], context: dict[str, Any] | None = None) -> dict[str, Any]:
        return asdict(self.scorer.score_turn(turn=turn, conversation_history=conversation_history, context=context))


class ScorerFactory:
    """Instantiate registered deterministic scorers by id."""

    @staticmethod
    def create(scorer_id: str) -> BaseSpriCOScorer:
        scorer = get_registered_scorer(scorer_id)
        if scorer is None:
            raise UnsupportedPyRITFeatureError(f"Unsupported scorer '{scorer_id}'.")
        return scorer

    @staticmethod
    def create_many(scorers: list[dict[str, Any]]) -> list[BaseSpriCOScorer]:
        if not scorers:
            return [ScorerFactory.create("hospital_privacy_composite")]
        return [ScorerFactory.create(str(item.get("name") or "")) for item in scorers]
