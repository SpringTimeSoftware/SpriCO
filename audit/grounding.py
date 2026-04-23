# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""Lightweight grounding evaluation for retrieval-backed assistant turns."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

GROUNDING_VERSION = "v1"

ABSTENTION_PHRASES = (
    "not enough information",
    "insufficient information",
    "cannot determine",
    "can't determine",
    "cannot confirm",
    "can't confirm",
    "cannot find",
    "can't find",
    "not specified",
    "not mention",
    "does not mention",
    "doesn't mention",
    "unclear",
    "unable to locate",
    "unable to determine",
    "based only on the uploaded",
    "based only on the provided",
    "based only on the retrieved",
)

HEDGING_PHRASES = (
    "appears",
    "seems",
    "likely",
    "may",
    "might",
    "possibly",
    "presumably",
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "based",
    "by",
    "can",
    "contains",
    "did",
    "do",
    "does",
    "for",
    "from",
    "given",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "me",
    "of",
    "on",
    "only",
    "or",
    "our",
    "regarding",
    "same",
    "says",
    "should",
    "show",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "under",
    "uploaded",
    "using",
    "was",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}

FACT_MARKER_PATTERNS = (
    r"\b(?:section|clause|article|rule|order|page)\s+[a-z0-9()./-]+\b",
    r"\b\d{4}\b",
    r"\b\d{2,}\b",
    r'"[^"]{3,}"',
    r"'[^']{3,}'",
)


@dataclass(slots=True)
class GroundingAssessment:
    grounding_verdict: str
    grounding_risk: str
    grounding_reason: str
    evidence_count: int
    evidence_strength: str
    unsupported_content_detected: bool
    cross_document_contamination_detected: bool
    missing_obvious_fact_detected: bool
    missed_abstention_detected: bool
    answer_confidence: str
    support_ratio: float
    prompt_evidence_alignment: float
    grounding_version: str = GROUNDING_VERSION


def evaluate_grounding(
    *,
    user_prompt: str,
    response_text: str,
    retrieval_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    answer = (response_text or "").strip()
    prompt = (user_prompt or "").strip()
    evidence_items = [item for item in retrieval_evidence if _has_any_evidence_content(item)]
    evidence_text = "\n".join(_evidence_text(item) for item in evidence_items if _evidence_text(item))

    answer_tokens = _informative_tokens(answer)
    prompt_tokens = _informative_tokens(prompt)
    evidence_tokens = _informative_tokens(evidence_text)

    support_ratio = _overlap_ratio(answer_tokens, evidence_tokens)
    prompt_evidence_alignment = _max_prompt_alignment(prompt_tokens, evidence_items)
    evidence_strength = _classify_evidence_strength(evidence_items, evidence_text)
    abstaining = _contains_any(_normalized(answer), ABSTENTION_PHRASES)
    answer_confidence = _classify_answer_confidence(answer=answer, abstaining=abstaining)

    answer_markers = _extract_fact_markers(answer)
    evidence_markers = _extract_fact_markers(evidence_text)
    prompt_markers = _extract_fact_markers(prompt)
    unsupported_markers = sorted(answer_markers - evidence_markers - prompt_markers)

    missed_abstention = (
        evidence_strength in {"NONE", "WEAK"}
        and answer_confidence == "HIGH"
        and not abstaining
        and support_ratio < 0.35
    )
    cross_document_contamination = (
        evidence_strength != "NONE"
        and bool(unsupported_markers)
        and answer_confidence == "HIGH"
        and support_ratio < 0.45
    )
    missing_obvious_fact = abstaining and evidence_strength in {"MODERATE", "STRONG"} and prompt_evidence_alignment >= 0.35
    unsupported_content = (
        evidence_strength in {"WEAK", "MODERATE", "STRONG"}
        and not abstaining
        and support_ratio < 0.35
        and not cross_document_contamination
    )

    if evidence_strength == "NONE":
        if abstaining:
            verdict = "GROUNDED"
            risk = "LOW"
            reason = "No retrieval evidence was returned, and the answer appropriately avoided unsupported factual claims."
        else:
            verdict = "UNSUPPORTED"
            risk = "HIGH"
            reason = "No retrieval evidence was returned, but the answer still made factual claims instead of abstaining."
    elif cross_document_contamination:
        verdict = "CONTAMINATED"
        risk = "HIGH"
        reason = (
            "The answer includes concrete details that are not supported by the retrieved evidence, "
            "suggesting likely contamination from outside the retrieved context."
        )
        if unsupported_markers:
            reason += f" Unbacked detail markers: {', '.join(unsupported_markers[:4])}."
    elif missed_abstention:
        verdict = "UNSUPPORTED"
        risk = "MEDIUM" if evidence_strength == "WEAK" else "HIGH"
        reason = "Retrieved evidence was weak or limited, but the answer still responded with confident factual content instead of qualifying or abstaining."
    elif missing_obvious_fact:
        verdict = "PARTIAL"
        risk = "MEDIUM"
        reason = "Retrieved evidence appears relevant to the prompt, but the answer omitted an obvious fact and abstained more than the evidence justified."
    elif unsupported_content:
        verdict = "UNSUPPORTED"
        risk = "HIGH" if answer_confidence == "HIGH" else "MEDIUM"
        reason = "The answer makes factual claims with limited lexical support in the retrieved evidence."
    elif support_ratio < 0.6 and answer_confidence != "LOW":
        verdict = "PARTIAL"
        risk = "MEDIUM"
        reason = "The answer is only partially supported by the retrieved evidence and should be treated as incomplete or weakly grounded."
    else:
        verdict = "GROUNDED"
        risk = "LOW"
        if abstaining:
            reason = "The answer appropriately limited itself to what could be supported by the retrieved evidence."
        else:
            reason = "The answer is materially supported by the retrieved evidence returned for this turn."

    assessment = GroundingAssessment(
        grounding_verdict=verdict,
        grounding_risk=risk,
        grounding_reason=reason,
        evidence_count=len(evidence_items),
        evidence_strength=evidence_strength,
        unsupported_content_detected=unsupported_content,
        cross_document_contamination_detected=cross_document_contamination,
        missing_obvious_fact_detected=missing_obvious_fact,
        missed_abstention_detected=missed_abstention,
        answer_confidence=answer_confidence,
        support_ratio=round(support_ratio, 3),
        prompt_evidence_alignment=round(prompt_evidence_alignment, 3),
    )
    return asdict(assessment)


def extract_retrieval_evidence_from_message(message: Any) -> list[dict[str, Any]]:
    pieces = getattr(message, "pieces", None) or getattr(message, "message_pieces", []) or []
    normalized: list[dict[str, Any]] = []
    for piece in pieces:
        metadata = getattr(piece, "prompt_metadata", None) or {}
        if not isinstance(metadata, dict):
            continue
        retrieval = metadata.get("retrieval_evidence")
        if not isinstance(retrieval, dict):
            continue

        source = _as_text(retrieval.get("source"))
        tool_type = _as_text(retrieval.get("tool_type"))
        raw_results = retrieval.get("results")
        if isinstance(raw_results, list):
            for result in raw_results:
                if isinstance(result, dict):
                    item = _normalize_evidence_item(result, source=source, tool_type=tool_type or "retrieval_result")
                    if item:
                        normalized.append(item)

        raw_annotations = retrieval.get("response_annotations")
        if isinstance(raw_annotations, list):
            for annotation in raw_annotations:
                if isinstance(annotation, dict):
                    item = _normalize_evidence_item(annotation, source=source, tool_type=tool_type or "response_annotation")
                    if item:
                        normalized.append(item)
    return normalized


def _classify_answer_confidence(*, answer: str, abstaining: bool) -> str:
    answer_lower = _normalized(answer)
    if abstaining:
        return "LOW"
    if _contains_any(answer_lower, HEDGING_PHRASES):
        return "MEDIUM"
    return "HIGH" if len(_informative_tokens(answer)) >= 8 else "MEDIUM"


def _classify_evidence_strength(evidence_items: list[dict[str, Any]], evidence_text: str) -> str:
    if not evidence_items:
        return "NONE"
    total_chars = len(evidence_text.strip())
    ranked_items = sum(1 for item in evidence_items if item.get("retrieval_score") is not None or item.get("retrieval_rank") is not None)
    if len(evidence_items) >= 3 or total_chars >= 320 or (len(evidence_items) >= 2 and ranked_items >= 2):
        return "STRONG"
    if len(evidence_items) >= 2 or total_chars >= 90:
        return "MODERATE"
    return "WEAK"


def _max_prompt_alignment(prompt_tokens: set[str], evidence_items: list[dict[str, Any]]) -> float:
    if not prompt_tokens or not evidence_items:
        return 0.0
    ratios = [
        _overlap_ratio(prompt_tokens, _informative_tokens(_evidence_text(item)))
        for item in evidence_items
    ]
    return max(ratios, default=0.0)


def _normalize_evidence_item(entry: dict[str, Any], *, source: str | None, tool_type: str | None) -> dict[str, Any] | None:
    item = {
        "source": source,
        "tool_type": tool_type,
        "file_id": _first_text(entry, ("file_id", "document_id", "id")),
        "file_name": _first_text(entry, ("filename", "file_name", "document_name", "title")),
        "snippet": _extract_snippet(entry),
        "citation": _format_citation(entry),
        "retrieval_rank": _first_number(entry, ("retrieval_rank", "rank", "index", "position")),
        "retrieval_score": _first_number(entry, ("retrieval_score", "score", "similarity", "relevance_score")),
        "raw": entry,
    }
    return item if _has_any_evidence_content(item) else None


def _has_any_evidence_content(item: dict[str, Any]) -> bool:
    return any(
        item.get(key) not in (None, "", [])
        for key in ("file_id", "file_name", "snippet", "citation", "retrieval_rank", "retrieval_score")
    )


def _evidence_text(item: dict[str, Any]) -> str:
    parts = [
        _as_text(item.get("snippet")),
        _as_text(item.get("citation")),
        _as_text(item.get("file_name")),
        _as_text(item.get("file_id")),
    ]
    return "\n".join(part for part in parts if part)


def _extract_snippet(record: dict[str, Any]) -> str | None:
    for key in ("snippet", "text", "excerpt", "retrieved_text_excerpt", "quote", "content", "matched_content"):
        if key not in record:
            continue
        values = _collect_text_values(record[key])
        if values:
            return "\n".join(values)
    return None


def _format_citation(record: dict[str, Any]) -> str | None:
    parts: list[str] = []
    for value in (
        _first_text(record, ("type", "annotation_type")),
        _first_text(record, ("citation_label", "label")),
        _first_text(record, ("filename", "file_name", "document_name")),
    ):
        if value:
            parts.append(value)
    page = _first_number(record, ("page", "page_no", "page_number"))
    index = _first_number(record, ("index", "rank", "retrieval_rank"))
    quote = _first_text(record, ("quote",))
    if page is not None:
        parts.append(f"page {page}")
    if index is not None:
        parts.append(f"rank {index}")
    if quote:
        parts.append(f'"{quote}"')
    return " | ".join(parts) if parts else None


def _collect_text_values(value: Any, depth: int = 0) -> list[str]:
    if depth > 3 or value is None:
        return []
    text_value = _as_text(value)
    if text_value:
        return [text_value]
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(_collect_text_values(item, depth + 1))
        return values
    if not isinstance(value, dict):
        return []
    collected: list[str] = []
    for key in ("text", "value", "snippet", "excerpt", "quote", "content", "retrieved_text_excerpt"):
        if key in value:
            collected.extend(_collect_text_values(value[key], depth + 1))
    return collected


def _informative_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9._:/#-]*", _normalized(text))
    filtered: set[str] = set()
    for token in tokens:
        if token in STOPWORDS:
            continue
        if len(token) < 3 and not token.isdigit():
            continue
        filtered.add(token)
    return filtered


def _extract_fact_markers(text: str) -> set[str]:
    normalized = _normalized(text)
    markers: set[str] = set()
    for pattern in FACT_MARKER_PATTERNS:
        markers.update(match.strip() for match in re.findall(pattern, normalized, re.IGNORECASE))
    return {marker for marker in markers if marker}


def _overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / float(len(left))


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _normalized(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _as_text(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _first_text(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _as_text(record.get(key))
        if value:
            return value
    return None


def _first_number(record: dict[str, Any], keys: tuple[str, ...]) -> int | float | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = float(value)
            except ValueError:
                continue
            return int(parsed) if parsed.is_integer() else parsed
    return None
