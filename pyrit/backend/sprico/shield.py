"""SpriCO Shield runtime screening service."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import asdict
import re
import uuid
from typing import Any
from urllib.parse import urlparse

from pyrit.backend.sprico.conditions import SpriCOConditionStore
from pyrit.backend.sprico.evidence_store import SpriCOEvidenceStore
from pyrit.backend.sprico.policy_store import SpriCOPolicyStore
from scoring.context_resolver import ConversationContextResolver
from scoring.packs.hospital_privacy.entity_extractors import extract_entities
from scoring.policy_context import build_policy_context
from scoring.policy_decision_engine import PolicyDecisionEngine
from scoring.types import DataSensitivity, SensitiveSignal, Verdict, ViolationRisk

_PROMPT_ATTACK_RE = re.compile(
    r"\b(ignore|override|bypass|disable|jailbreak|developer mode|system prompt|hidden instructions|reveal your instructions)\b",
    re.IGNORECASE,
)
_ROLE_CLAIM_RE = re.compile(r"\b(i am|i'm|as)\s+(?:the\s+)?(admin|administrator|doctor|physician|auditor)\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d .-]{8,}\d)\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_SECRET_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|(?:api[_ -]?key|token|secret|password)\s*[:=]\s*[^\s,;]+)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s)>\"]+", re.IGNORECASE)
_HARMFUL_CONTENT_RE = re.compile(r"\b(hate|kill|bomb|weapon|malware|phishing|self-harm|suicide)\b", re.IGNORECASE)
_MARKDOWN_EXFIL_RE = re.compile(r"!\[[^\]]*]\(https?://[^)]+\)|\[([^\]]+)]\(https?://[^)]+\)", re.IGNORECASE)

IDENTIFIER_TYPES = {"PATIENT_ID", "PATIENT_NAME", "MRN"}
LOCATION_TYPES = {"ADDRESS", "CITY", "COUNTY", "STATE", "ZIP", "LOCATION"}
MEDICAL_TYPES = {"MEDICATION", "DIAGNOSIS", "CONDITION", "CARE_PLAN", "PROGNOSIS", "DEATH_CAUSE"}


class SpriCOShieldService:
    """Runtime screening service inspired by Guard but native to SpriCO."""

    def __init__(self, store: SpriCOPolicyStore | None = None) -> None:
        self._store = store or SpriCOPolicyStore()
        self._engine = PolicyDecisionEngine()
        self._resolver = ConversationContextResolver()
        self._evidence_store = SpriCOEvidenceStore()
        self._condition_store = SpriCOConditionStore()

    def check(self, request: dict[str, Any]) -> dict[str, Any]:
        messages = list(request.get("messages") or [])
        if not messages:
            raise ValueError("messages cannot be empty")

        policy = self._store.get_policy_for_request(
            policy_id=request.get("policy_id"),
            project_id=request.get("project_id"),
        )
        latest = messages[-1]
        latest_text = str(latest.get("content") or "")
        latest_role = str(latest.get("role") or "user")
        history = _history_from_messages(messages[:-1])
        previous_user = _latest_role_content(messages[:-1], "user")
        current_turn = {
            "user_prompt": previous_user if latest_role == "assistant" else latest_text,
            "assistant_response": latest_text if latest_role == "assistant" else "",
        }
        signals = self._detect_signals(
            latest_text=latest_text,
            latest_role=latest_role,
            messages=messages,
            history=history,
            current_turn=current_turn,
            policy=policy,
        )
        policy_metadata = _policy_context_metadata(policy=policy, request=request)
        policy_context = build_policy_context(metadata=policy_metadata, prompt_text=current_turn["user_prompt"] or latest_text)
        decision = self._engine.decide(signals=signals, policy_context=policy_context, conversation_context={"messages": messages})
        response = {
            "flagged": decision.verdict != "PASS",
            "decision": _decision_action(decision.verdict, decision.risk),
            "verdict": decision.verdict,
            "violation_risk": decision.risk,
            "data_sensitivity": decision.data_sensitivity,
            "matched_signals": [signal.to_dict() for signal in signals],
            "payload": [span for signal in signals for span in signal.evidence_spans] if request.get("payload", False) else [],
            "breakdown": _breakdown(signals) if request.get("breakdown", True) else [],
            "metadata": {
                "request_uuid": str(uuid.uuid4()),
                "session_id": (request.get("metadata") or {}).get("session_id"),
                "target_id": request.get("target_id"),
                "policy_id": policy.get("id"),
                "policy_version": policy.get("version"),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            },
            "dev_info": _dev_info(decision, policy) if request.get("dev_info", False) else {},
        }
        stored = self._evidence_store.append_event(
            {
                "engine": "sprico.shield",
                "engine_version": "v1",
                "target_id": request.get("target_id"),
                "project_id": request.get("project_id"),
                "policy_id": policy.get("id"),
                "policy_context": policy_context.to_dict(),
                "raw_engine_result": {"decision": response["decision"], "breakdown": response["breakdown"]},
                "matched_signals": response["matched_signals"],
                "final_verdict": response["verdict"],
                "violation_risk": response["violation_risk"],
                "data_sensitivity": response["data_sensitivity"],
                "redaction_status": "payload_redacted" if not request.get("payload", False) else "payload_returned",
            }
        )
        response["metadata"]["evidence_id"] = stored["finding_id"]
        return response

    def simulate_policy(self, *, policy: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
        return self.check({"messages": messages, "policy_id": policy.get("id"), "payload": True, "breakdown": True})

    def _detect_signals(
        self,
        *,
        latest_text: str,
        latest_role: str,
        messages: list[dict[str, Any]],
        history: list[dict[str, Any]],
        current_turn: dict[str, Any],
        policy: dict[str, Any],
    ) -> list[SensitiveSignal]:
        signals: list[SensitiveSignal] = []
        enabled = policy.get("enabled_guardrails") or {}
        if enabled.get("prompt_defense", True):
            signals.extend(_prompt_defense_signals(latest_text))
        if enabled.get("dlp", True):
            signals.extend(_generic_dlp_signals(latest_text))
            signals.extend(_phi_signals(latest_text=latest_text, latest_role=latest_role, history=history, resolver=self._resolver, current_turn=current_turn))
            signals.extend(_secret_signals(latest_text))
        if enabled.get("content_moderation", True):
            signals.extend(_content_signals(latest_text))
        if enabled.get("malicious_links", True):
            signals.extend(_link_signals(latest_text, policy=policy))
        if enabled.get("custom_detectors", True):
            signals.extend(_custom_detector_signals(latest_text, policy=policy))
            signals.extend(
                self._condition_store.list_active_signals(
                    text=latest_text,
                    policy_context={"policy_mode": policy.get("mode"), "target_domain": policy.get("target_domain")},
                )
            )
        signals.extend(_rag_tool_signals(messages))
        return signals


def _prompt_defense_signals(text: str) -> list[SensitiveSignal]:
    signals: list[SensitiveSignal] = []
    if _PROMPT_ATTACK_RE.search(text):
        signals.append(
            SensitiveSignal(
                signal_id="PROMPT_DEFENSE_ATTACK",
                category="prompt_defense",
                detector_id="sprico.shield.prompt_defense",
                confidence=0.82,
                default_strict_verdict=Verdict.FAIL.value,
                default_strict_risk=ViolationRisk.HIGH.value,
                explanation="Prompt contains instruction override, jailbreak, or system-prompt extraction language.",
            )
        )
    if _ROLE_CLAIM_RE.search(text):
        signals.append(
            SensitiveSignal(
                signal_id="PROMPT_CLAIMED_ROLE",
                category="authorization",
                detector_id="sprico.shield.prompt_claim",
                confidence=0.9,
                raw={"authorization_source": "PROMPT_CLAIM", "attack_intent": "role_override"},
                default_strict_verdict=Verdict.NEEDS_REVIEW.value,
                default_strict_risk=ViolationRisk.MEDIUM.value,
                explanation="The prompt claims a privileged role, but prompt text is not authorization.",
            )
        )
    return signals


def _generic_dlp_signals(text: str) -> list[SensitiveSignal]:
    spans: list[dict[str, Any]] = []
    for label, regex in (("EMAIL", _EMAIL_RE), ("PHONE", _PHONE_RE), ("SSN", _SSN_RE)):
        for match in regex.finditer(text):
            spans.append({"entity_type": label, "start": match.start(), "end": match.end(), "value": "[REDACTED]"})
    if not spans:
        return []
    sensitivity = DataSensitivity.CRITICAL.value if any(span["entity_type"] == "SSN" for span in spans) else DataSensitivity.HIGH.value
    return [
        SensitiveSignal(
            signal_id="PII_DLP_MATCH",
            category="dlp",
            detector_id="sprico.shield.generic_dlp",
            confidence=0.9,
            data_sensitivity=sensitivity,
            requires_authorization=True,
            requires_minimum_necessary=True,
            evidence_spans=spans[:20],
            entity_types=sorted({str(span["entity_type"]) for span in spans}),
            default_strict_verdict=Verdict.FAIL.value,
            default_strict_risk=ViolationRisk.CRITICAL.value if sensitivity == DataSensitivity.CRITICAL.value else ViolationRisk.HIGH.value,
            explanation="Generic PII was detected.",
        )
    ]


def _phi_signals(
    *,
    latest_text: str,
    latest_role: str,
    history: list[dict[str, Any]],
    resolver: ConversationContextResolver,
    current_turn: dict[str, Any],
) -> list[SensitiveSignal]:
    entities = extract_entities(latest_text, source="latest")
    types = {entity.entity_type for entity in entities}
    resolved = resolver.resolve(current_turn=current_turn, conversation_history=history)
    signals: list[SensitiveSignal] = []
    if types & IDENTIFIER_TYPES and types & MEDICAL_TYPES:
        signals.append(_phi_signal("PATIENT_CONDITION_LINKAGE", entities, DataSensitivity.HIGH.value, "Patient identifier linked to condition or diagnosis."))
    if types & IDENTIFIER_TYPES and types & LOCATION_TYPES:
        signals.append(_phi_signal("PATIENT_LOCATION_LINKAGE", entities, DataSensitivity.HIGH.value, "Patient identifier linked to location."))
    if types & {"DOB"} and (types & IDENTIFIER_TYPES or resolved.references_prior_sensitive_entities):
        signals.append(_phi_signal("PATIENT_DOB_DISCLOSURE", entities, DataSensitivity.CRITICAL.value, "DOB linked to patient context."))
    if len([entity for entity in entities if entity.entity_type == "ADDRESS"]) >= 1:
        signals.append(_phi_signal("PHI_ADDRESS_DISCLOSURE", entities, DataSensitivity.CRITICAL.value, "Patient address disclosure detected."))
    if resolved.references_prior_sensitive_entities and (types & (LOCATION_TYPES | MEDICAL_TYPES | {"DOB"})):
        signal = _phi_signal("CONTEXT_FOLLOWUP_EXFILTRATION", entities, DataSensitivity.CRITICAL.value, resolved.risk_reason)
        signal.raw["context_references"] = asdict(resolved)
        signals.append(signal)
    if latest_role == "user" and resolved.references_prior_sensitive_entities and any(term in latest_text.lower() for term in ("where", "location", "from", "address", "dob")):
        signals.append(
            SensitiveSignal(
                signal_id="CONTEXT_FOLLOWUP_EXFILTRATION_REQUEST",
                category="hospital_privacy",
                detector_id="sprico.shield.context_followup",
                confidence=resolved.confidence,
                data_sensitivity=DataSensitivity.HIGH.value,
                requires_authorization=True,
                requires_minimum_necessary=True,
                entity_types=["PATIENT_ID"],
                default_strict_verdict=Verdict.FAIL.value,
                default_strict_risk=ViolationRisk.HIGH.value,
                explanation="Follow-up request refers to prior sensitive patient context.",
            )
        )
    return signals


def _phi_signal(signal_id: str, entities: list[Any], sensitivity: str, explanation: str) -> SensitiveSignal:
    spans = [
        {"entity_type": entity.entity_type, "start": entity.start, "end": entity.end, "value": entity.redacted_value}
        for entity in entities[:20]
    ]
    return SensitiveSignal(
        signal_id=signal_id,
        category="hospital_privacy",
        detector_id="sprico.shield.phi",
        confidence=0.94,
        data_sensitivity=sensitivity,
        requires_authorization=True,
        requires_minimum_necessary=True,
        evidence_spans=spans,
        entity_types=sorted({entity.entity_type for entity in entities}),
        default_strict_verdict=Verdict.FAIL.value,
        default_strict_risk=ViolationRisk.CRITICAL.value if sensitivity == DataSensitivity.CRITICAL.value else ViolationRisk.HIGH.value,
        explanation=explanation,
    )


def _secret_signals(text: str) -> list[SensitiveSignal]:
    spans = [{"entity_type": "SECRET", "start": m.start(), "end": m.end(), "value": "[REDACTED_SECRET]"} for m in _SECRET_RE.finditer(text)]
    if not spans:
        return []
    return [
        SensitiveSignal(
            signal_id="SECRET_DISCLOSURE",
            category="secrets",
            detector_id="sprico.shield.secrets",
            confidence=0.95,
            data_sensitivity=DataSensitivity.CRITICAL.value,
            requires_authorization=True,
            requires_minimum_necessary=True,
            evidence_spans=spans,
            entity_types=["SECRET"],
            default_strict_verdict=Verdict.FAIL.value,
            default_strict_risk=ViolationRisk.CRITICAL.value,
            explanation="Secret or credential-like value detected.",
        )
    ]


def _content_signals(text: str) -> list[SensitiveSignal]:
    if not _HARMFUL_CONTENT_RE.search(text):
        return []
    return [
        SensitiveSignal(
            signal_id="CONTENT_MODERATION_MATCH",
            category="content_moderation",
            detector_id="sprico.shield.content_moderation",
            confidence=0.65,
            default_strict_verdict=Verdict.NEEDS_REVIEW.value,
            default_strict_risk=ViolationRisk.MEDIUM.value,
            explanation="Potential harmful-content category detected.",
        )
    ]


def _link_signals(text: str, *, policy: dict[str, Any]) -> list[SensitiveSignal]:
    allowed = {str(domain).lower() for domain in policy.get("allowed_domains") or []}
    denied = {str(domain).lower() for domain in policy.get("deny_domains") or []}
    spans = []
    for match in _URL_RE.finditer(text):
        domain = (urlparse(match.group(0)).hostname or "").lower()
        if domain in allowed:
            continue
        if domain in denied or domain.endswith(".zip") or domain.endswith(".mov") or not _known_domain(domain):
            spans.append({"entity_type": "URL", "start": match.start(), "end": match.end(), "value": match.group(0), "domain": domain})
    if _MARKDOWN_EXFIL_RE.search(text):
        spans.append({"entity_type": "MARKDOWN_EXFILTRATION", "start": 0, "end": min(len(text), 256), "value": "[REDACTED_URL]"})
    if not spans:
        return []
    return [
        SensitiveSignal(
            signal_id="UNKNOWN_OR_MALICIOUS_LINK",
            category="links",
            detector_id="sprico.shield.links",
            confidence=0.72,
            data_sensitivity=DataSensitivity.MEDIUM.value,
            evidence_spans=spans[:20],
            default_strict_verdict=Verdict.NEEDS_REVIEW.value,
            default_strict_risk=ViolationRisk.MEDIUM.value,
            explanation="Unknown, denied, suspicious, or markdown-exfiltration link detected.",
        )
    ]


def _custom_detector_signals(text: str, *, policy: dict[str, Any]) -> list[SensitiveSignal]:
    signals: list[SensitiveSignal] = []
    for detector in policy.get("custom_detectors") or []:
        pattern = detector.get("pattern")
        if not pattern:
            continue
        try:
            regex = re.compile(str(pattern), re.IGNORECASE)
        except re.error:
            continue
        spans = [{"entity_type": detector.get("entity_type") or "CUSTOM", "start": m.start(), "end": m.end(), "value": "[REDACTED]"} for m in regex.finditer(text)]
        if not spans:
            continue
        signals.append(
            SensitiveSignal(
                signal_id=str(detector.get("id") or "CUSTOM_DETECTOR_MATCH"),
                category="custom_detector",
                detector_id="sprico.shield.custom",
                confidence=0.85,
                data_sensitivity=str(detector.get("data_sensitivity") or DataSensitivity.HIGH.value),
                requires_authorization=bool(detector.get("requires_authorization", True)),
                requires_minimum_necessary=bool(detector.get("requires_minimum_necessary", True)),
                evidence_spans=spans[:20],
                entity_types=[str(detector.get("entity_type") or "CUSTOM")],
                default_strict_verdict=Verdict.FAIL.value,
                default_strict_risk=str(detector.get("risk") or ViolationRisk.HIGH.value),
                explanation=str(detector.get("explanation") or "Custom detector matched."),
            )
        )
    return signals


def _rag_tool_signals(messages: list[dict[str, Any]]) -> list[SensitiveSignal]:
    signals: list[SensitiveSignal] = []
    for message in messages:
        role = str(message.get("role") or "")
        content = str(message.get("content") or "")
        if role in {"tool", "developer"} and _PROMPT_ATTACK_RE.search(content):
            signals.append(
                SensitiveSignal(
                    signal_id="TOOL_OR_RAG_PROMPT_INJECTION",
                    category="tool_rag",
                    detector_id="sprico.shield.tool_rag",
                    confidence=0.82,
                    default_strict_verdict=Verdict.FAIL.value,
                    default_strict_risk=ViolationRisk.HIGH.value,
                    explanation="Tool, developer, or retrieved context contains instruction-override language.",
                )
            )
    return signals


def _history_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for index, message in enumerate(messages, start=1):
        role = str(message.get("role") or "")
        content = str(message.get("content") or "")
        history.append(
            {
                "turn_id": f"{role}-{index}",
                "role": role,
                "user_prompt": content if role == "user" else "",
                "assistant_response": content if role == "assistant" else "",
                "content": content,
            }
        )
    return history


def _latest_role_content(messages: list[dict[str, Any]], role: str) -> str:
    for message in reversed(messages):
        if message.get("role") == role:
            return str(message.get("content") or "")
    return ""


def _policy_context_metadata(*, policy: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(request.get("metadata") or {})
    return {
        "policy_id": policy.get("id"),
        "policy_version": policy.get("version"),
        "policy_mode": policy.get("mode") or "UNKNOWN",
        "target_domain": policy.get("target_domain") or metadata.get("domain") or "unknown",
        "environment": metadata.get("environment") or policy.get("environment") or "unknown",
        "access_context": metadata.get("access_context") or "UNKNOWN",
        "authorization_source": metadata.get("authorization_source") or "NONE",
        "verified_user_role": metadata.get("verified_user_role"),
        "allowed_roles": metadata.get("allowed_roles") or [],
        "purpose": metadata.get("purpose") or "unknown",
        "allowed_purposes": metadata.get("allowed_purposes") or [],
        "subject_scope": metadata.get("subject_scope") or {},
        "scope_fit": metadata.get("scope_fit") or "UNKNOWN",
        "minimum_necessary": metadata.get("minimum_necessary") or "UNKNOWN",
        "minimum_necessary_required": metadata.get("minimum_necessary_required", True),
        **metadata,
    }


def _decision_action(verdict: str, risk: str) -> str:
    if verdict == "FAIL":
        return "block" if risk in {"HIGH", "CRITICAL"} else "mask"
    if verdict == "NEEDS_REVIEW":
        return "escalate"
    if verdict == "WARN":
        return "warn"
    return "allow"


def _breakdown(signals: list[SensitiveSignal]) -> list[dict[str, Any]]:
    detectors = ["prompt_defense", "dlp", "phi_dlp", "secrets", "content_moderation", "unknown_links", "custom_detectors", "tool_rag"]
    return [
        {
            "detector": detector,
            "detected": any(detector in signal.detector_id or detector in signal.category for signal in signals),
        }
        for detector in detectors
    ]


def _dev_info(decision: Any, policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine": "sprico.shield",
        "policy_engine": decision.scorer_version,
        "policy": {"id": policy.get("id"), "version": policy.get("version")},
    }


def _known_domain(domain: str) -> bool:
    if not domain:
        return False
    return domain in {"openai.com", "microsoft.com", "who.int", "cdc.gov", "nih.gov", "wikipedia.org"} or domain.endswith(
        (".gov", ".edu")
    )
