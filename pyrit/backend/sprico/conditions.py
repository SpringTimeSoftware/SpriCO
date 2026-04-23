"""Safe declarative custom condition lifecycle and simulation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
import uuid
from typing import Any

from pyrit.backend.sprico.storage import StorageBackend, get_storage_backend
from scoring.packs.hospital_privacy.entity_extractors import extract_entities
from scoring.types import DataSensitivity, SensitiveSignal, Verdict, ViolationRisk

ALLOWED_CONDITION_TYPES = {
    "keyword_match",
    "regex_match",
    "entity_linkage",
    "sensitive_signal_match",
    "policy_context_match",
    "threshold_condition",
    "composite_condition",
    "llm_judge_condition",
}

REGEX_PATTERN_LIMIT = 256
REGEX_TEXT_LIMIT = 10_000
COMPOSITE_DEPTH_LIMIT = 3


class ConditionLifecycleError(ValueError):
    """Raised when a condition lifecycle transition is invalid."""


class SpriCOConditionStore:
    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend = backend or get_storage_backend()

    def list_conditions(self) -> list[dict[str, Any]]:
        return self._backend.list_records("custom_conditions")

    def get_condition(self, condition_id: str) -> dict[str, Any] | None:
        return self._backend.get_record("custom_conditions", condition_id)

    def create_condition(self, payload: dict[str, Any]) -> dict[str, Any]:
        condition_type = str(payload.get("condition_type") or payload.get("type") or "")
        if condition_type not in ALLOWED_CONDITION_TYPES:
            raise ConditionLifecycleError(f"Unsupported condition_type '{condition_type}'")
        now = _now()
        condition_id = str(payload.get("condition_id") or f"cond_{uuid.uuid4().hex[:12]}")
        version = str(payload.get("version") or "1.0.0")
        condition = {
            "condition_id": condition_id,
            "id": condition_id,
            "name": str(payload.get("name") or condition_id),
            "description": payload.get("description"),
            "version": version,
            "status": "draft",
            "activation_state": "inactive",
            "condition_type": condition_type,
            "parameters": dict(payload.get("parameters") or {}),
            "author": str(payload.get("author") or "system"),
            "approver": None,
            "domain": str(payload.get("domain") or "generic"),
            "policy_modes": list(payload.get("policy_modes") or ["REDTEAM_STRICT"]),
            "data_sensitivity": str(payload.get("data_sensitivity") or DataSensitivity.HIGH.value),
            "violation_risk": str(payload.get("violation_risk") or ViolationRisk.HIGH.value),
            "requires_authorization": bool(payload.get("requires_authorization", True)),
            "requires_minimum_necessary": bool(payload.get("requires_minimum_necessary", True)),
            "test_cases": list(payload.get("test_cases") or []),
            "simulation_result": None,
            "activation_timestamp": None,
            "rollback_target": payload.get("rollback_target"),
            "version_frozen": False,
            "audit_history": [],
            "created_at": now,
            "updated_at": now,
        }
        self._append_audit(condition, "draft", condition["author"], {"created": True})
        self._persist(condition, action="draft")
        return deepcopy(condition)

    def simulate_condition(self, condition_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        condition = self._require_condition(condition_id)
        text = str(payload.get("text") or payload.get("input_text") or "")
        policy_context = dict(payload.get("policy_context") or {})
        existing_signals = list(payload.get("signals") or [])
        result = evaluate_condition(
            condition,
            text=text,
            policy_context=policy_context,
            existing_signals=existing_signals,
        )
        now = _now()
        condition["status"] = "simulate"
        condition["simulation_result"] = result
        condition["updated_at"] = now
        self._append_audit(condition, "simulate", str(payload.get("actor") or condition.get("author") or "system"), result)
        self._backend.upsert_record(
            "condition_simulations",
            f"{condition_id}:{now}",
            {"id": f"{condition_id}:{now}", "condition_id": condition_id, "version": condition["version"], "result": result, "created_at": now},
        )
        self._persist(condition, action="simulate")
        return result

    def add_test_case(self, condition_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        condition = self._require_condition(condition_id)
        if condition.get("version_frozen"):
            raise ConditionLifecycleError("Frozen condition versions cannot be edited; create a new version instead")
        test_case = {
            "id": str(payload.get("id") or f"test_{uuid.uuid4().hex[:10]}"),
            "name": str(payload.get("name") or "Condition test"),
            "input_text": str(payload.get("input_text") or ""),
            "expected_match": bool(payload.get("expected_match")),
            "policy_context": dict(payload.get("policy_context") or {}),
        }
        result = evaluate_condition(condition, text=test_case["input_text"], policy_context=test_case["policy_context"])
        test_case["last_result"] = result
        test_case["passed"] = bool(result["matched"]) == test_case["expected_match"]
        condition.setdefault("test_cases", []).append(test_case)
        condition["status"] = "test"
        condition["updated_at"] = _now()
        self._append_audit(condition, "test", str(payload.get("actor") or condition.get("author") or "system"), {"test_case": test_case})
        self._backend.upsert_record("condition_tests", f"{condition_id}:{test_case['id']}", {"condition_id": condition_id, **test_case})
        self._persist(condition, action="test")
        return deepcopy(condition)

    def approve_condition(self, condition_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        condition = self._require_condition(condition_id)
        if not _has_positive_and_negative_tests(condition):
            raise ConditionLifecycleError("Condition approval requires at least one positive and one negative test case")
        if not condition.get("simulation_result"):
            raise ConditionLifecycleError("Condition approval requires a completed simulation")
        approver = str(payload.get("approver") or "")
        if not approver:
            raise ConditionLifecycleError("approver is required")
        condition["status"] = "approve"
        condition["approver"] = approver
        condition["version_frozen"] = True
        condition["updated_at"] = _now()
        approval = {
            "id": f"{condition_id}:{condition['version']}:approval",
            "condition_id": condition_id,
            "version": condition["version"],
            "approver": approver,
            "created_at": condition["updated_at"],
            "notes": payload.get("notes"),
        }
        self._append_audit(condition, "approve", approver, approval)
        self._backend.upsert_record("condition_approvals", approval["id"], approval)
        self._persist(condition, action="approve")
        return deepcopy(condition)

    def activate_condition(self, condition_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        condition = self._require_condition(condition_id)
        payload = payload or {}
        failures = _activation_failures(condition)
        if failures:
            raise ConditionLifecycleError("Condition cannot activate: " + "; ".join(failures))
        actor = str(payload.get("actor") or condition.get("approver") or "system")
        now = _now()
        condition["activation_timestamp"] = now
        condition["activation_state"] = "active"
        condition["status"] = "monitor"
        condition["updated_at"] = now
        self._append_audit(condition, "activate", actor, {"activation_timestamp": now})
        self._append_audit(condition, "monitor", actor, {"activation_state": "active"})
        self._persist(condition, action="activate")
        return deepcopy(condition)

    def retire_condition(self, condition_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        condition = self._require_condition(condition_id)
        payload = payload or {}
        actor = str(payload.get("actor") or "system")
        condition["status"] = "retire"
        condition["activation_state"] = "retired"
        condition["retired_at"] = _now()
        condition["updated_at"] = condition["retired_at"]
        self._append_audit(condition, "retire", actor, {"reason": payload.get("reason")})
        self._persist(condition, action="retire")
        return deepcopy(condition)

    def rollback_condition(self, condition_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        condition = self._require_condition(condition_id)
        rollback_target = str(payload.get("rollback_target") or condition.get("rollback_target") or "")
        if not rollback_target:
            raise ConditionLifecycleError("rollback_target is required")
        actor = str(payload.get("actor") or "system")
        condition["status"] = "rollback"
        condition["activation_state"] = "rolled_back"
        condition["rollback_target"] = rollback_target
        condition["rolled_back_at"] = _now()
        condition["updated_at"] = condition["rolled_back_at"]
        self._append_audit(condition, "rollback", actor, {"rollback_target": rollback_target})
        self._persist(condition, action="rollback")
        return deepcopy(condition)

    def list_active_signals(self, *, text: str, policy_context: dict[str, Any] | None = None) -> list[SensitiveSignal]:
        signals: list[SensitiveSignal] = []
        context = dict(policy_context or {})
        for condition in self.list_conditions():
            if condition.get("activation_state") != "active" or condition.get("status") not in {"monitor", "activate"}:
                continue
            allowed_modes = set(str(mode) for mode in condition.get("policy_modes") or [])
            policy_mode = str(context.get("policy_mode") or context.get("mode") or "")
            if allowed_modes and policy_mode and policy_mode not in allowed_modes:
                continue
            result = evaluate_condition(condition, text=text, policy_context=context)
            for signal_payload in result.get("signals") or []:
                signals.append(SensitiveSignal(**signal_payload))
        return signals

    def versions(self, condition_id: str) -> list[dict[str, Any]]:
        return [
            item
            for item in self._backend.list_records("condition_versions")
            if item.get("condition_id") == condition_id
        ]

    def audit_history(self, condition_id: str) -> list[dict[str, Any]]:
        condition = self._require_condition(condition_id)
        stored = [
            item
            for item in self._backend.list_records("condition_audit_history")
            if item.get("condition_id") == condition_id
        ]
        return stored or list(condition.get("audit_history") or [])

    def _require_condition(self, condition_id: str) -> dict[str, Any]:
        condition = self.get_condition(condition_id)
        if condition is None:
            raise KeyError(condition_id)
        return condition

    def _persist(self, condition: dict[str, Any], *, action: str) -> None:
        self._backend.upsert_record("custom_conditions", condition["condition_id"], condition)
        version_id = f"{condition['condition_id']}:{condition['version']}"
        self._backend.upsert_record(
            "condition_versions",
            version_id,
            {
                "id": version_id,
                "condition_id": condition["condition_id"],
                "version": condition["version"],
                "status": condition["status"],
                "condition": deepcopy(condition),
                "created_at": condition["updated_at"],
                "action": action,
            },
        )
        for item in condition.get("audit_history") or []:
            self._backend.upsert_record(
                "condition_audit_history",
                item["id"],
                item,
            )

    def _append_audit(self, condition: dict[str, Any], action: str, actor: str, changes: dict[str, Any]) -> None:
        now = _now()
        condition.setdefault("audit_history", []).append(
            {
                "id": f"{condition['condition_id']}:{condition.get('version', '1.0.0')}:{now}:{action}",
                "condition_id": condition["condition_id"],
                "version": condition.get("version", "1.0.0"),
                "timestamp": now,
                "action": action,
                "actor": actor,
                "changes": deepcopy(changes),
            }
        )


def evaluate_condition(
    condition: dict[str, Any],
    *,
    text: str,
    policy_context: dict[str, Any] | None = None,
    existing_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    matched, details = _evaluate(
        condition_type=str(condition.get("condition_type") or ""),
        parameters=dict(condition.get("parameters") or {}),
        text=text,
        policy_context=dict(policy_context or {}),
        existing_signals=list(existing_signals or []),
        depth=0,
    )
    signals = [_signal_from_condition(condition, evidence=details).to_dict()] if matched else []
    return {
        "matched": matched,
        "signals": signals,
        "details": details,
        "final_verdict_authority": "sprico_policy_decision_engine",
        "note": "Custom conditions emit SensitiveSignals only; PolicyDecisionEngine computes final verdict.",
    }


def _evaluate(
    *,
    condition_type: str,
    parameters: dict[str, Any],
    text: str,
    policy_context: dict[str, Any],
    existing_signals: list[dict[str, Any]],
    depth: int,
) -> tuple[bool, dict[str, Any]]:
    if condition_type == "keyword_match":
        keywords = [str(item) for item in parameters.get("keywords") or []]
        haystack = text if parameters.get("case_sensitive") else text.lower()
        needles = keywords if parameters.get("case_sensitive") else [item.lower() for item in keywords]
        matched = [keyword for keyword, needle in zip(keywords, needles) if needle and needle in haystack]
        return bool(matched), {"condition_type": condition_type, "matched_keywords": matched}
    if condition_type == "regex_match":
        pattern = str(parameters.get("pattern") or "")
        return _safe_regex_search(pattern, text)
    if condition_type == "entity_linkage":
        required = {str(item) for item in parameters.get("required_entity_types") or []}
        entities = extract_entities(text[:REGEX_TEXT_LIMIT], source="custom_condition")
        found = {entity.entity_type for entity in entities}
        matched = required.issubset(found) if required else False
        return matched, {"condition_type": condition_type, "required_entity_types": sorted(required), "found_entity_types": sorted(found)}
    if condition_type == "sensitive_signal_match":
        categories = {str(item) for item in parameters.get("categories") or []}
        signal_ids = {str(item) for item in parameters.get("signal_ids") or []}
        matches = [
            signal
            for signal in existing_signals
            if (not categories or signal.get("category") in categories) and (not signal_ids or signal.get("signal_id") in signal_ids)
        ]
        return bool(matches), {"condition_type": condition_type, "match_count": len(matches)}
    if condition_type == "policy_context_match":
        expected = dict(parameters.get("expected") or {})
        mismatches = {
            key: {"expected": value, "actual": policy_context.get(key)}
            for key, value in expected.items()
            if policy_context.get(key) != value
        }
        return not mismatches and bool(expected), {"condition_type": condition_type, "mismatches": mismatches}
    if condition_type == "threshold_condition":
        metric = str(parameters.get("metric") or "")
        threshold = float(parameters.get("threshold") or 0)
        value = float(parameters.get("value", policy_context.get(metric, 0)) or 0)
        operator = str(parameters.get("operator") or "gte")
        matched = value >= threshold if operator == "gte" else value > threshold if operator == "gt" else value <= threshold
        return matched, {"condition_type": condition_type, "metric": metric, "value": value, "threshold": threshold, "operator": operator}
    if condition_type == "composite_condition":
        if depth >= COMPOSITE_DEPTH_LIMIT:
            return False, {"condition_type": condition_type, "error": "composite depth limit exceeded"}
        operator = str(parameters.get("operator") or "any").lower()
        children = [item for item in parameters.get("conditions") or [] if isinstance(item, dict)]
        results = [
            _evaluate(
                condition_type=str(child.get("condition_type") or child.get("type") or ""),
                parameters=dict(child.get("parameters") or {}),
                text=text,
                policy_context=policy_context,
                existing_signals=existing_signals,
                depth=depth + 1,
            )
            for child in children[:10]
        ]
        matched_values = [item[0] for item in results]
        matched = all(matched_values) if operator == "all" else any(matched_values)
        return matched, {"condition_type": condition_type, "operator": operator, "children": [item[1] for item in results]}
    if condition_type == "llm_judge_condition":
        return False, {"condition_type": condition_type, "disabled": True, "reason": "LLM judge conditions are optional and disabled by default"}
    return False, {"condition_type": condition_type, "error": "unsupported condition type"}


def _safe_regex_search(pattern: str, text: str) -> tuple[bool, dict[str, Any]]:
    if len(pattern) > REGEX_PATTERN_LIMIT:
        return False, {"condition_type": "regex_match", "error": "pattern length limit exceeded"}
    if len(text) > REGEX_TEXT_LIMIT:
        text = text[:REGEX_TEXT_LIMIT]
    if re.search(r"(\([^)]*[+*][^)]*\))[+*{]", pattern) or re.search(r"\\[1-9]", pattern):
        return False, {"condition_type": "regex_match", "error": "unsafe regex pattern rejected"}
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return False, {"condition_type": "regex_match", "error": str(exc)}
    match = regex.search(text)
    return bool(match), {
        "condition_type": "regex_match",
        "matched_span": [match.start(), match.end()] if match else None,
        "text_length_limit": REGEX_TEXT_LIMIT,
        "pattern_length_limit": REGEX_PATTERN_LIMIT,
    }


def _signal_from_condition(condition: dict[str, Any], *, evidence: dict[str, Any]) -> SensitiveSignal:
    risk = str(condition.get("violation_risk") or ViolationRisk.HIGH.value)
    return SensitiveSignal(
        signal_id=f"custom_condition:{condition['condition_id']}:{condition.get('version')}",
        category="custom_condition",
        detector_id=f"sprico.condition.{condition.get('condition_type')}",
        detector_version=str(condition.get("version") or "1.0.0"),
        detected=True,
        confidence=0.86,
        data_sensitivity=str(condition.get("data_sensitivity") or DataSensitivity.HIGH.value),
        requires_authorization=bool(condition.get("requires_authorization", True)),
        requires_minimum_necessary=bool(condition.get("requires_minimum_necessary", True)),
        evidence_spans=[],
        entity_types=[],
        raw={"condition_id": condition["condition_id"], "condition_version": condition.get("version"), "evidence": evidence},
        default_strict_verdict=Verdict.FAIL.value if risk in {ViolationRisk.HIGH.value, ViolationRisk.CRITICAL.value} else Verdict.NEEDS_REVIEW.value,
        default_strict_risk=risk,
        explanation=f"Custom condition '{condition.get('name') or condition['condition_id']}' matched and emitted a SensitiveSignal.",
    )


def _has_positive_and_negative_tests(condition: dict[str, Any]) -> bool:
    tests = condition.get("test_cases") or []
    return any(item.get("expected_match") is True for item in tests) and any(item.get("expected_match") is False for item in tests)


def _activation_failures(condition: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not _has_positive_and_negative_tests(condition):
        failures.append("positive and negative test cases are required")
    if not condition.get("simulation_result"):
        failures.append("simulation was not run")
    if not condition.get("approver"):
        failures.append("approval was not recorded")
    if not condition.get("version_frozen"):
        failures.append("version was not frozen")
    if not condition.get("audit_history"):
        failures.append("audit history was not written")
    if condition.get("status") != "approve":
        failures.append("condition must be approved before activation")
    return failures


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
