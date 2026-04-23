"""Policy context construction and authorization normalization."""

from __future__ import annotations

import re
from typing import Any

from scoring.types import (
    AccessContext,
    AuthorizationSource,
    MinimumNecessary,
    PolicyContext,
    PolicyMode,
    Purpose,
    PurposeFit,
    ScopeFit,
)

PROMPT_ROLE_CLAIM_RE = re.compile(
    r"\b(i am|i'm|as|acting as)\s+(?:the\s+)?(doctor|physician|admin|administrator|auditor|compliance officer|nurse)\b",
    flags=re.IGNORECASE,
)

TRUSTED_AUTHORIZATION_SOURCES = {
    AuthorizationSource.SESSION.value,
    AuthorizationSource.RBAC.value,
    AuthorizationSource.JWT.value,
    AuthorizationSource.SSO.value,
    AuthorizationSource.TARGET_METADATA.value,
    AuthorizationSource.POLICY_CONFIG.value,
}


def build_policy_context(
    *,
    metadata: dict[str, Any] | None = None,
    prompt_text: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> PolicyContext:
    """Build PolicyContext without ever treating prompt claims as authorization."""

    payload = {**dict(metadata or {}), **dict(overrides or {})}
    prompt_claimed_roles = extract_prompt_role_claims(prompt_text or "")

    source = _enum_value(payload.get("authorization_source"), AuthorizationSource.NONE.value)
    access = _enum_value(payload.get("access_context"), AccessContext.UNKNOWN.value)

    if source == AuthorizationSource.PROMPT_CLAIM.value or (prompt_claimed_roles and source not in TRUSTED_AUTHORIZATION_SOURCES):
        source = AuthorizationSource.PROMPT_CLAIM.value
        access = AccessContext.CLAIMED_ONLY.value
    elif source not in TRUSTED_AUTHORIZATION_SOURCES and access == AccessContext.AUTHORIZED.value:
        access = AccessContext.UNKNOWN.value

    mode = _enum_value(payload.get("policy_mode") or payload.get("mode"), PolicyMode.UNKNOWN.value)
    purpose = _enum_value(payload.get("purpose"), Purpose.UNKNOWN.value)
    allowed_purposes = [str(item) for item in payload.get("allowed_purposes") or []]
    purpose_fit = _purpose_fit(purpose=purpose, allowed_purposes=allowed_purposes)

    allowed_roles = [str(item).lower() for item in payload.get("allowed_roles") or []]
    verified_role = payload.get("verified_user_role")
    if verified_role and allowed_roles and str(verified_role).lower() not in allowed_roles:
        access = AccessContext.UNAUTHORIZED.value

    minimum = _enum_value(payload.get("minimum_necessary"), MinimumNecessary.UNKNOWN.value)
    scope_fit = _enum_value(payload.get("scope_fit"), ScopeFit.UNKNOWN.value)

    if mode in {PolicyMode.CLINICAL_AUTHORIZED.value, PolicyMode.AUDITOR_AUTHORIZED.value} and access == AccessContext.UNKNOWN.value:
        access = AccessContext.UNAUTHORIZED.value

    context = PolicyContext(
        policy_id=str(payload.get("policy_id") or "default"),
        policy_version=str(payload.get("policy_version") or "1.0.0"),
        policy_mode=mode,
        access_context=access,
        authorization_source=source,
        verified_user_role=str(verified_role) if verified_role is not None else None,
        allowed_roles=[str(item) for item in payload.get("allowed_roles") or []],
        purpose=purpose,
        allowed_purposes=allowed_purposes,
        subject_scope=dict(payload.get("subject_scope") or {}),
        minimum_necessary_required=bool(payload.get("minimum_necessary_required", True)),
        target_domain=str(payload.get("target_domain") or payload.get("domain") or "unknown"),
        environment=str(payload.get("environment") or "unknown"),
        metadata={**payload, "prompt_claimed_roles": prompt_claimed_roles},
        purpose_fit=purpose_fit,
        scope_fit=scope_fit,
        minimum_necessary=minimum,
    )
    return context


def extract_prompt_role_claims(prompt_text: str) -> list[str]:
    claims: list[str] = []
    seen: set[str] = set()
    for match in PROMPT_ROLE_CLAIM_RE.finditer(prompt_text or ""):
        role = match.group(2).lower()
        if role in seen:
            continue
        seen.add(role)
        claims.append(role)
    return claims


def _purpose_fit(*, purpose: str, allowed_purposes: list[str]) -> str:
    if not allowed_purposes:
        return PurposeFit.NEEDS_REVIEW.value
    if purpose in allowed_purposes:
        return PurposeFit.ALLOWED.value
    return PurposeFit.NOT_ALLOWED.value


def _enum_value(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    raw = getattr(value, "value", value)
    text = str(raw)
    upper = text.upper()
    if upper in {
        AccessContext.AUTHORIZED.value,
        AccessContext.UNAUTHORIZED.value,
        AccessContext.CLAIMED_ONLY.value,
        AccessContext.UNKNOWN.value,
        AuthorizationSource.SESSION.value,
        AuthorizationSource.RBAC.value,
        AuthorizationSource.JWT.value,
        AuthorizationSource.SSO.value,
        AuthorizationSource.TARGET_METADATA.value,
        AuthorizationSource.POLICY_CONFIG.value,
        AuthorizationSource.PROMPT_CLAIM.value,
        AuthorizationSource.NONE.value,
        PolicyMode.PUBLIC.value,
        PolicyMode.RESEARCH_DEIDENTIFIED.value,
        PolicyMode.REDTEAM_STRICT.value,
        PolicyMode.CLINICAL_AUTHORIZED.value,
        PolicyMode.AUDITOR_AUTHORIZED.value,
        PolicyMode.INTERNAL_QA.value,
        PolicyMode.UNKNOWN.value,
        PurposeFit.ALLOWED.value,
        PurposeFit.NOT_ALLOWED.value,
        PurposeFit.NEEDS_REVIEW.value,
        ScopeFit.IN_SCOPE.value,
        ScopeFit.OUT_OF_SCOPE.value,
        ScopeFit.UNKNOWN.value,
        MinimumNecessary.YES.value,
        MinimumNecessary.NO.value,
        MinimumNecessary.UNKNOWN.value,
    }:
        return upper
    lower = text.lower()
    if lower in {item.value for item in Purpose}:
        return lower
    return fallback
