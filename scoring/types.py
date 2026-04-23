"""Shared types for deterministic SpriCO scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class _StrEnum(str, Enum):
    """Small compatibility shim for Python 3.10 string enums."""

    def __str__(self) -> str:
        return self.value


class Verdict(_StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ViolationRisk(_StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DataSensitivity(_StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Safety(_StrEnum):
    SAFE = "SAFE"
    WARN = "WARN"
    VIOLATION = "VIOLATION"


class AttackIntent(_StrEnum):
    NONE_DETECTED = "none_detected"
    PROMPT_INJECTION = "prompt_injection"
    INDIRECT_PROMPT_INJECTION = "indirect_prompt_injection"
    JAILBREAK = "jailbreak"
    ROLE_OVERRIDE = "role_override"
    DATA_EXFILTRATION = "data_exfiltration"
    TOOL_MISUSE = "tool_misuse"
    UNSAFE_SPECIALIZED_ADVICE = "unsafe_specialized_advice"
    UNKNOWN = "unknown"


class Outcome(_StrEnum):
    NOT_TRIGGERED = "NOT_TRIGGERED"
    RESISTED = "RESISTED"
    PARTIAL = "PARTIAL"
    SUCCESS = "SUCCESS"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Grounding(_StrEnum):
    GROUNDED = "GROUNDED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    CONTAMINATED = "CONTAMINATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AccessContext(_StrEnum):
    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"
    CLAIMED_ONLY = "CLAIMED_ONLY"
    UNKNOWN = "UNKNOWN"


class AuthorizationSource(_StrEnum):
    SESSION = "SESSION"
    RBAC = "RBAC"
    JWT = "JWT"
    SSO = "SSO"
    TARGET_METADATA = "TARGET_METADATA"
    POLICY_CONFIG = "POLICY_CONFIG"
    PROMPT_CLAIM = "PROMPT_CLAIM"
    NONE = "NONE"


class PolicyMode(_StrEnum):
    PUBLIC = "PUBLIC"
    RESEARCH_DEIDENTIFIED = "RESEARCH_DEIDENTIFIED"
    REDTEAM_STRICT = "REDTEAM_STRICT"
    CLINICAL_AUTHORIZED = "CLINICAL_AUTHORIZED"
    AUDITOR_AUTHORIZED = "AUDITOR_AUTHORIZED"
    INTERNAL_QA = "INTERNAL_QA"
    UNKNOWN = "UNKNOWN"


class Purpose(_StrEnum):
    TREATMENT = "treatment"
    PAYMENT = "payment"
    HEALTHCARE_OPERATIONS = "healthcare_operations"
    AUDIT = "audit"
    COMPLIANCE = "compliance"
    RESEARCH = "research"
    PUBLIC_INFORMATION = "public_information"
    DEBUGGING = "debugging"
    UNKNOWN = "unknown"


class PurposeFit(_StrEnum):
    ALLOWED = "ALLOWED"
    NOT_ALLOWED = "NOT_ALLOWED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ScopeFit(_StrEnum):
    IN_SCOPE = "IN_SCOPE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNKNOWN = "UNKNOWN"


class MinimumNecessary(_StrEnum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class DisclosureType(_StrEnum):
    ALLOWED_DISCLOSURE = "ALLOWED_DISCLOSURE"
    PRIVACY_LEAK = "PRIVACY_LEAK"
    OVER_DISCLOSURE = "OVER_DISCLOSURE"
    UNSAFE_REFUSAL_WITH_LEAK = "UNSAFE_REFUSAL_WITH_LEAK"
    DEIDENTIFIED = "DEIDENTIFIED"
    AGGREGATED = "AGGREGATED"
    PUBLIC_INFORMATION = "PUBLIC_INFORMATION"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(slots=True)
class SensitiveEntity:
    entity_type: str
    value: str
    redacted_value: str
    start: int
    end: int
    source: str = "response"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SensitiveSignal:
    signal_id: str
    category: str
    detector_id: str
    detector_version: str = "v1"
    detected: bool = True
    confidence: float | None = None
    data_sensitivity: str = DataSensitivity.LOW.value
    requires_authorization: bool = False
    requires_minimum_necessary: bool = False
    evidence_spans: list[dict[str, Any]] = field(default_factory=list)
    entity_types: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    default_strict_verdict: str = Verdict.NEEDS_REVIEW.value
    default_strict_risk: str = ViolationRisk.MEDIUM.value
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "category": self.category,
            "detector_id": self.detector_id,
            "detector_version": self.detector_version,
            "detected": self.detected,
            "confidence": self.confidence,
            "data_sensitivity": self.data_sensitivity,
            "requires_authorization": self.requires_authorization,
            "requires_minimum_necessary": self.requires_minimum_necessary,
            "evidence_spans": list(self.evidence_spans),
            "entity_types": list(self.entity_types),
            "raw": dict(self.raw),
            "default_strict_verdict": self.default_strict_verdict,
            "default_strict_risk": self.default_strict_risk,
            "explanation": self.explanation,
        }


@dataclass(slots=True)
class PolicyContext:
    policy_id: str = "default"
    policy_version: str = "1.0.0"
    policy_mode: str = PolicyMode.UNKNOWN.value
    access_context: str = AccessContext.UNKNOWN.value
    authorization_source: str = AuthorizationSource.NONE.value
    verified_user_role: str | None = None
    allowed_roles: list[str] = field(default_factory=list)
    purpose: str = Purpose.UNKNOWN.value
    allowed_purposes: list[str] = field(default_factory=list)
    subject_scope: dict[str, Any] = field(default_factory=dict)
    minimum_necessary_required: bool = True
    target_domain: str = "unknown"
    environment: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    purpose_fit: str = PurposeFit.NEEDS_REVIEW.value
    scope_fit: str = ScopeFit.UNKNOWN.value
    minimum_necessary: str = MinimumNecessary.UNKNOWN.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_mode": self.policy_mode,
            "access_context": self.access_context,
            "authorization_source": self.authorization_source,
            "verified_user_role": self.verified_user_role,
            "allowed_roles": list(self.allowed_roles),
            "purpose": self.purpose,
            "allowed_purposes": list(self.allowed_purposes),
            "subject_scope": dict(self.subject_scope),
            "minimum_necessary_required": self.minimum_necessary_required,
            "target_domain": self.target_domain,
            "environment": self.environment,
            "metadata": dict(self.metadata),
            "purpose_fit": self.purpose_fit,
            "scope_fit": self.scope_fit,
            "minimum_necessary": self.minimum_necessary,
        }


@dataclass(slots=True)
class ResolvedContext:
    references_prior_sensitive_entities: bool
    referenced_entity_ids: list[str] = field(default_factory=list)
    referenced_patient_ids: list[str] = field(default_factory=list)
    referenced_names: list[str] = field(default_factory=list)
    referenced_conditions: list[str] = field(default_factory=list)
    referenced_locations: list[str] = field(default_factory=list)
    reference_terms: list[str] = field(default_factory=list)
    previous_turn_ids: list[str] = field(default_factory=list)
    risk_reason: str = ""
    confidence: float = 0.0
    cascading_exfiltration: bool = False


@dataclass(slots=True)
class ScoreResult:
    verdict: str
    risk: str
    safety: str
    refusal: str
    outcome: str
    grounding: str
    attack_intent: str
    outcome_safety: str
    explanation: str
    confidence: float
    score: int
    matched_rules: list[str] = field(default_factory=list)
    detected_entities: list[dict[str, Any]] = field(default_factory=list)
    evidence_spans: list[dict[str, Any]] = field(default_factory=list)
    context_references: dict[str, Any] = field(default_factory=dict)
    policy_pack: str = ""
    scorer_id: str = ""
    scorer_version: str = ""
    refusal_quality: str = "NOT_APPLICABLE"
    raw_output: dict[str, Any] = field(default_factory=dict)
    violation_risk: str | None = None
    data_sensitivity: str = DataSensitivity.LOW.value
    access_context: str = AccessContext.UNKNOWN.value
    authorization_source: str = AuthorizationSource.NONE.value
    policy_mode: str = PolicyMode.UNKNOWN.value
    purpose: str = Purpose.UNKNOWN.value
    purpose_fit: str = PurposeFit.NEEDS_REVIEW.value
    scope_fit: str = ScopeFit.UNKNOWN.value
    minimum_necessary: str = MinimumNecessary.UNKNOWN.value
    disclosure_type: str = DisclosureType.NEEDS_REVIEW.value
    matched_signals: list[dict[str, Any]] = field(default_factory=list)
    raw_engine_result: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.violation_risk is None:
            self.violation_risk = self.risk


@dataclass(slots=True)
class AggregateScoreResult:
    verdict: str
    risk: str
    explanation: str
    matched_rules: list[str] = field(default_factory=list)
    findings: list[ScoreResult] = field(default_factory=list)
