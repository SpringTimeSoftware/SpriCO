"""Central redaction helpers for sensitive audit evidence."""

from __future__ import annotations

import re


def redact_patient_id(value: str) -> str:
    text = (value or "").strip()
    if len(text) <= 12:
        return "[REDACTED_PATIENT_ID]"
    return f"{text[:8]}-...-{text[-4:]}"


def redact_address(value: str) -> str:
    return "[REDACTED_ADDRESS]" if (value or "").strip() else ""


def redact_dob(value: str) -> str:
    text = (value or "").strip()
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(1)}-**-**"
    return "[REDACTED_DOB]" if text else ""


def redact_name(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return "[REDACTED_NAME]"


def redact_secret(value: str) -> str:
    text = (value or "").strip()
    if len(text) <= 4:
        return "****"
    prefix = "sk-" if text.startswith("sk-") else ""
    suffix = text[-4:]
    masked = "*" * max(4, len(text) - len(prefix) - 4)
    return f"{prefix}{masked}{suffix}"


def redact_entity(entity_type: str, value: str) -> str:
    kind = (entity_type or "").upper()
    if kind in {"PATIENT_ID", "MRN", "INSURANCE_ID", "HOSPITAL_RECORD_REFERENCE"}:
        return redact_patient_id(value)
    if kind in {"ADDRESS"}:
        return redact_address(value)
    if kind in {"DOB"}:
        return redact_dob(value)
    if kind in {"PATIENT_NAME", "PROVIDER_NAME"}:
        return redact_name(value)
    if kind in {"SSN", "PHONE", "EMAIL"}:
        return "[REDACTED]"
    return value[:48] + ("..." if len(value) > 48 else "")
