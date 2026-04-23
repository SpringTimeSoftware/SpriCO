"""Registry for reusable SpriCO scorers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from scoring.aggregation import aggregate_results
from scoring.types import AggregateScoreResult, ScoreResult


class BaseSpriCOScorer(ABC):
    id: str = "sprico.base"
    name: str = "Base SpriCO Scorer"
    version: str = "v1"
    domains: list[str] = []

    @abstractmethod
    def score_turn(
        self,
        turn: dict[str, Any],
        conversation_history: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> ScoreResult:
        raise NotImplementedError

    def score_conversation(self, conversation: list[dict[str, Any]]) -> AggregateScoreResult:
        findings = [self.score_turn(turn=turn, conversation_history=conversation[:index], context=None) for index, turn in enumerate(conversation)]
        return aggregate_results(findings)


_SCORER_REGISTRY: dict[str, BaseSpriCOScorer] = {}


def register_scorer(scorer: BaseSpriCOScorer) -> BaseSpriCOScorer:
    _SCORER_REGISTRY[scorer.id] = scorer
    return scorer


def get_registered_scorer(scorer_id: str) -> BaseSpriCOScorer | None:
    return _SCORER_REGISTRY.get(scorer_id)


def list_registered_scorers() -> list[BaseSpriCOScorer]:
    return list(_SCORER_REGISTRY.values())
