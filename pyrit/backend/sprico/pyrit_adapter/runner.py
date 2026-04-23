"""Minimal scan runner adapter for future scan APIs."""

from __future__ import annotations

import uuid
from typing import Any

from pyrit.backend.sprico.pyrit_adapter.converter_factory import ConverterFactory
from pyrit.backend.sprico.pyrit_adapter.dataset_factory import DatasetFactory
from pyrit.backend.sprico.pyrit_adapter.memory_factory import MemoryFactory
from pyrit.backend.sprico.pyrit_adapter.orchestrator_factory import OrchestratorFactory
from pyrit.backend.sprico.pyrit_adapter.result_normalizer import normalize_scan_result
from pyrit.backend.sprico.pyrit_adapter.scorer_factory import ScorerFactory
from pyrit.backend.sprico.pyrit_adapter.target_factory import PyRITTargetFactory


class PyRITScanRunner:
    """Best-effort adapter runner for generic scan requests."""

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        scan_id = str(request.get("scan_id") or uuid.uuid4())
        target = PyRITTargetFactory.create(request.get("target") or {"target_registry_name": request.get("target_id")})
        orchestrator = OrchestratorFactory.create(request.get("orchestrator"))
        converters = [ConverterFactory.build(item) for item in list(request.get("converters") or [])]
        scorers = ScorerFactory.create_many(list(request.get("scorers") or []))
        dataset = DatasetFactory.create(request.get("dataset_id"), request.get("dataset"))
        memory = MemoryFactory.create(request.get("memory"))
        _ = (target, orchestrator, dataset, memory)

        raw_results: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        prompts = list(request.get("seed_prompts") or [])
        for prompt in prompts:
            converted_prompt, conversion_trace = ConverterFactory.apply(str(prompt), converters)
            turn = {"user_prompt": converted_prompt, "assistant_response": ""}
            for scorer in scorers:
                score = scorer.score_turn(turn=turn, conversation_history=[], context={"conversion_trace": conversion_trace})
                findings.append(
                    {
                        "scorer_id": scorer.id,
                        "verdict": score.verdict,
                        "risk": score.risk,
                        "outcome": score.outcome,
                        "matched_rules": list(score.matched_rules),
                        "explanation": score.explanation,
                    }
                )
            raw_results.append({"prompt": converted_prompt, "conversion_trace": conversion_trace})

        return normalize_scan_result(scan_id=scan_id, status="completed", findings=findings, raw_results=raw_results)
