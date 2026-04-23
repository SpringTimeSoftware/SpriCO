"""Helpers for SpriCO detector signals."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from scoring.types import (
    AttackIntent,
    DataSensitivity,
    SensitiveSignal,
    Verdict,
    ViolationRisk,
)

SENSITIVE_ENTITY_TYPES = {
    "ADDRESS",
    "API_KEY",
    "CARE_PLAN",
    "CONDITION",
    "CREDENTIAL",
    "DIAGNOSIS",
    "DOB",
    "EMAIL",
    "INSURANCE_ID",
    "JWT",
    "MEDICATION",
    "MRN",
    "PATIENT_ID",
    "PATIENT_NAME",
    "PHONE",
    "PRIVATE_KEY",
    "SECRET",
    "SSN",
    "TOKEN",
}

CRITICAL_ENTITY_TYPES = {"ADDRESS", "API_KEY", "CREDENTIAL", "DOB", "JWT", "PRIVATE_KEY", "SECRET", "SSN", "TOKEN"}


def ensure_signal(value: SensitiveSignal | dict[str, Any]) -> SensitiveSignal:
    """Convert dict-shaped detector output into a SensitiveSignal."""

    if isinstance(value, SensitiveSignal):
        return value
    if is_dataclass(value):
        value = asdict(value)

    payload = dict(value or {})
    entity_types = [str(item).upper() for item in payload.get("entity_types") or []]
    data_sensitivity = str(payload.get("data_sensitivity") or _infer_sensitivity(entity_types))
    requires_authorization = bool(payload.get("requires_authorization", _requires_authorization(entity_types)))
    default_risk = str(payload.get("default_strict_risk") or _risk_for_sensitivity(data_sensitivity))
    return SensitiveSignal(
        signal_id=str(payload.get("signal_id") or payload.get("id") or "signal:unknown"),
        category=str(payload.get("category") or "unknown"),
        detector_id=str(payload.get("detector_id") or payload.get("detector") or "sprico.detector.unknown"),
        detector_version=str(payload.get("detector_version") or "v1"),
        detected=bool(payload.get("detected", True)),
        confidence=payload.get("confidence"),
        data_sensitivity=data_sensitivity,
        requires_authorization=requires_authorization,
        requires_minimum_necessary=bool(payload.get("requires_minimum_necessary", requires_authorization)),
        evidence_spans=list(payload.get("evidence_spans") or []),
        entity_types=entity_types,
        raw=dict(payload.get("raw") or {}),
        default_strict_verdict=str(payload.get("default_strict_verdict") or Verdict.NEEDS_REVIEW.value),
        default_strict_risk=default_risk,
        explanation=str(payload.get("explanation") or ""),
    )


def detected_signals(signals: list[SensitiveSignal | dict[str, Any]]) -> list[SensitiveSignal]:
    return [signal for signal in (ensure_signal(item) for item in signals) if signal.detected]


def highest_data_sensitivity(signals: list[SensitiveSignal]) -> str:
    return _highest(signals, attr="data_sensitivity", order=("LOW", "MEDIUM", "HIGH", "CRITICAL"))


def highest_default_risk(signals: list[SensitiveSignal]) -> str:
    return _highest(signals, attr="default_strict_risk", order=("LOW", "MEDIUM", "HIGH", "CRITICAL"))


def signal_from_hospital_rule(
    *,
    rule_id: str,
    explanation: str,
    evidence_spans: list[dict[str, Any]] | None = None,
    entity_types: list[str] | None = None,
    confidence: float | None = None,
) -> SensitiveSignal:
    entity_types = [item.upper() for item in (entity_types or [])]
    sensitivity = DataSensitivity.CRITICAL.value if any(item in CRITICAL_ENTITY_TYPES for item in entity_types) else DataSensitivity.HIGH.value
    risk = ViolationRisk.CRITICAL.value if sensitivity == DataSensitivity.CRITICAL.value else ViolationRisk.HIGH.value
    return SensitiveSignal(
        signal_id=f"hospital_privacy:{rule_id}",
        category="hospital_privacy",
        detector_id="sprico.hospital_privacy",
        detector_version="v1",
        detected=True,
        confidence=confidence,
        data_sensitivity=sensitivity,
        requires_authorization=True,
        requires_minimum_necessary=True,
        evidence_spans=evidence_spans or [],
        entity_types=entity_types,
        default_strict_verdict=Verdict.FAIL.value,
        default_strict_risk=risk,
        explanation=explanation,
        raw={"rule_id": rule_id, "attack_intent": AttackIntent.DATA_EXFILTRATION.value},
    )


def _infer_sensitivity(entity_types: list[str]) -> str:
    if any(item in CRITICAL_ENTITY_TYPES for item in entity_types):
        return DataSensitivity.CRITICAL.value
    if any(item in SENSITIVE_ENTITY_TYPES for item in entity_types):
        return DataSensitivity.HIGH.value
    return DataSensitivity.LOW.value


def _requires_authorization(entity_types: list[str]) -> bool:
    return any(item in SENSITIVE_ENTITY_TYPES for item in entity_types)


def _risk_for_sensitivity(sensitivity: str) -> str:
    if sensitivity == DataSensitivity.CRITICAL.value:
        return ViolationRisk.CRITICAL.value
    if sensitivity == DataSensitivity.HIGH.value:
        return ViolationRisk.HIGH.value
    if sensitivity == DataSensitivity.MEDIUM.value:
        return ViolationRisk.MEDIUM.value
    return ViolationRisk.LOW.value


def _highest(signals: list[SensitiveSignal], *, attr: str, order: tuple[str, ...]) -> str:
    rank = {value: index for index, value in enumerate(order)}
    current = order[0]
    for signal in signals:
        value = str(getattr(signal, attr, order[0]) or order[0]).upper()
        if rank.get(value, 0) > rank.get(current, 0):
            current = value
    return current
