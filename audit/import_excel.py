# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""Import structured audit scenarios from the workbook into the SQLite audit store."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from audit.database import AuditDatabase

DEFAULT_EXCEL_PATH = Path(r"C:\Users\rahul\Downloads\Prompts for CoPyrit.xlsx")

# Explicit workbook-to-DB mapping used during import.
WORKBOOK_IMPORT_MAPPING = {
    "sheet_name": "audit_categories.source_sheet_name",
    "sheet_name_trimmed": "audit_categories.name",
    "Import-level industry_type override": "audit_tests.industry_type",
    "Industry Type / Industry": "audit_tests.industry_type (legacy workbook support)",
    "Category": "audit_tests.category_label",
    "Query": "audit_tests.canonical_question / audit_tests.test_objective",
    "Guard Rails": "audit_tests.safe_base_prompt_sequence",
    "Without Guard Rails": "audit_tests.unsafe_base_prompt_sequence",
    "Adversarial (With Guard Rails)": "audit_tests.safe_adversarial_prompt_sequence",
    "Adversarial (Without Guard Rails)": "audit_tests.unsafe_adversarial_prompt_sequence",
    "Expected Answer": "audit_tests.expected_answer",
    "Attack Type / ttack Type": "audit_tests.attack_type",
    "Test Objective": "audit_tests.test_objective",
    "Prompt Sequence / Base Prompt": "audit_tests.prompt_sequence",
    "Adversarial Prompt": "audit_tests.adversarial_prompt_sequence",
    "Expected Safe Behaviour / Expected Safe Behavior": "audit_tests.expected_behavior",
    "Result": "audit_tests.original_result_guidance",
    "Document / Document(s)": "audit_tests.supporting_documents.compiled_text",
    "RAG Scenario": "audit_tests.supporting_documents.rag_scenario",
    "Excel row number (2-based including header)": "audit_tests.workbook_row_id",
    "Workbook domain column": "audit_tests.domain (nullable; only populated if a real workbook domain column exists)",
}

COLUMN_ALIASES = {
    "industry_type": ("Industry Type", "Industry", "industry_type"),
    "category_label": ("Category", "category", "Category Name"),
    "canonical_question": ("Query", "Question", "Canonical Question"),
    "safe_base_prompt": ("Guard Rails",),
    "unsafe_base_prompt": ("Without Guard Rails",),
    "safe_adversarial_prompt": ("Adversarial (With Guard Rails)",),
    "unsafe_adversarial_prompt": ("Adversarial (Without Guard Rails)",),
    "expected_answer": ("Expected Answer",),
    "attack_type": ("Attack Type", "ttack Type"),
    "test_objective": ("Test Objective",),
    "base_prompt_sequence": ("Base Prompt", "Base Prompt Sequence", "Prompt Sequence"),
    "adversarial_prompt_sequence": ("Adversarial Prompt", "Adversarial Prompt Sequence", "Adversarial Sequence"),
    "expected_behavior": ("Expected Safe Behaviour", "Expected Safe Behavior"),
    "result": ("Result",),
    "document": ("Document", "Document(s)"),
    "rag_scenario": ("RAG Scenario",),
    "domain": ("Domain", "domain"),
}


def import_workbook(
    excel_path: Path,
    repository: Optional[AuditDatabase] = None,
    *,
    industry_type_override: Optional[str] = None,
) -> dict[str, Any]:
    """Import every workbook sheet into the audit SQLite database without inventing workbook fields."""
    db = repository or AuditDatabase()
    db.initialize()

    workbook = pd.ExcelFile(excel_path)
    db.sync_categories_from_workbook(workbook.sheet_names)

    imported_rows = 0
    per_sheet_counts: dict[str, int] = {}
    domain_column_detected = False

    for sheet_name in workbook.sheet_names:
        db.deactivate_tests_for_sheet(sheet_name)
        category_id = db.get_category_id(sheet_name)
        frame = pd.read_excel(excel_path, sheet_name=sheet_name)

        imported_for_sheet = 0
        for index, row in frame.iterrows():
            if row.dropna().empty:
                continue

            category_label = _read_column(row, "category_label") or sheet_name.strip()
            imported_industry_type = (industry_type_override or _read_column(row, "industry_type") or "Generic").strip() or "Generic"
            matrix_row = _build_matrix_prompt_record(row)
            legacy_prompt_sequence_raw = _read_column(row, "base_prompt_sequence")
            attack_type = _read_column(row, "attack_type")

            if not matrix_row and (not attack_type or not legacy_prompt_sequence_raw):
                continue

            test_objective = _read_column(row, "test_objective")
            expected_behavior = _read_column(row, "expected_behavior")
            original_result_guidance = _read_column(row, "result")
            document_text = _read_column(row, "document")
            rag_scenario = _read_column(row, "rag_scenario")
            workbook_domain = _read_column(row, "domain") or None
            if workbook_domain:
                domain_column_detected = True

            if matrix_row:
                canonical_question = matrix_row["canonical_question"]
                safe_base_prompt_text = matrix_row["safe_base_prompt_sequence"]
                unsafe_base_prompt_text = matrix_row["unsafe_base_prompt_sequence"]
                safe_adversarial_prompt_text = matrix_row["safe_adversarial_prompt_sequence"]
                unsafe_adversarial_prompt_text = matrix_row["unsafe_adversarial_prompt_sequence"]
                expected_answer = matrix_row["expected_answer"]

                prompt_sequence_text, inline_document = _extract_inline_document(safe_base_prompt_text)
                prompt_steps = _parse_prompt_steps(prompt_sequence_text)
                adversarial_prompt_text, adversarial_inline_document = (
                    _extract_inline_document(safe_adversarial_prompt_text) if safe_adversarial_prompt_text else ("", None)
                )
                adversarial_prompt_steps = _parse_prompt_steps(adversarial_prompt_text) if adversarial_prompt_text else []

                attack_type = canonical_question or category_label
                test_objective = canonical_question or test_objective or category_label
                expected_behavior = expected_answer or expected_behavior
            else:
                canonical_question = _read_column(row, "canonical_question") or test_objective or attack_type
                expected_answer = _read_column(row, "expected_answer") or expected_behavior
                safe_base_prompt_text = None
                unsafe_base_prompt_text = None
                safe_adversarial_prompt_text = None
                unsafe_adversarial_prompt_text = None

                prompt_sequence_text, inline_document = _extract_inline_document(legacy_prompt_sequence_raw)
                prompt_steps = _parse_prompt_steps(prompt_sequence_text)
                adversarial_prompt_raw = _read_column(row, "adversarial_prompt_sequence")
                adversarial_prompt_text, adversarial_inline_document = _extract_inline_document(adversarial_prompt_raw) if adversarial_prompt_raw else ("", None)
                adversarial_prompt_steps = _parse_prompt_steps(adversarial_prompt_text) if adversarial_prompt_text else []

            compiled_document = "\n\n".join(part for part in (document_text, inline_document) if part).strip() or None
            if adversarial_inline_document:
                compiled_document = "\n\n".join(part for part in (compiled_document, adversarial_inline_document) if part).strip() or None

            supporting_documents: dict[str, Any] = {}
            if compiled_document:
                supporting_documents["compiled_text"] = compiled_document
            if rag_scenario:
                supporting_documents["rag_scenario"] = rag_scenario

            record = {
                "category_id": category_id,
                "workbook_row_id": index + 2,
                "industry_type": imported_industry_type,
                "category_label": category_label,
                "attack_type": attack_type,
                "test_objective": test_objective,
                "canonical_question": canonical_question,
                "prompt_sequence": _normalize_prompt_sequence(prompt_steps, prompt_sequence_text),
                "prompt_steps": prompt_steps,
                "adversarial_prompt_sequence": _normalize_prompt_sequence(adversarial_prompt_steps, adversarial_prompt_text) if adversarial_prompt_text else None,
                "adversarial_prompt_steps": adversarial_prompt_steps,
                "safe_base_prompt_sequence": safe_base_prompt_text,
                "unsafe_base_prompt_sequence": unsafe_base_prompt_text,
                "safe_adversarial_prompt_sequence": safe_adversarial_prompt_text,
                "unsafe_adversarial_prompt_sequence": unsafe_adversarial_prompt_text,
                "supporting_documents": supporting_documents,
                "expected_behavior": expected_behavior,
                "expected_answer": expected_answer,
                "original_result_guidance": original_result_guidance,
                "domain": workbook_domain,
                "severity": _derive_severity(
                    attack_type=attack_type,
                    test_objective=test_objective,
                    prompt_sequence=prompt_sequence_text,
                    expected_behavior=expected_behavior,
                ),
                "source_origin": "workbook",
            }
            db.upsert_test(record)
            imported_rows += 1
            imported_for_sheet += 1

        per_sheet_counts[sheet_name] = imported_for_sheet

    return {
        "excel_path": str(excel_path),
        "database_path": str(db.db_path),
        "imported_rows": imported_rows,
        "per_sheet_counts": per_sheet_counts,
        "import_mapping": WORKBOOK_IMPORT_MAPPING,
        "industry_type_override": (industry_type_override or "").strip() or None,
        "has_real_domain_column": domain_column_detected,
    }


def _read_column(row: pd.Series, logical_name: str) -> str:
    for alias in COLUMN_ALIASES[logical_name]:
        value = row.get(alias)
        if pd.notna(value):
            return str(value).strip()
    return ""


def _extract_inline_document(prompt_sequence: str) -> tuple[str, Optional[str]]:
    match = re.search(r"document\s*\(if using rag\)\s*:\s*(.*)$", prompt_sequence, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return prompt_sequence.strip(), None
    prompt_only = prompt_sequence[: match.start()].strip()
    return prompt_only, match.group(1).strip()


def _build_matrix_prompt_record(row: pd.Series) -> Optional[dict[str, Optional[str]]]:
    canonical_question = _read_column(row, "canonical_question")
    safe_guard_rails = _read_column(row, "safe_base_prompt")
    unsafe_base_prompt = _read_column(row, "unsafe_base_prompt")
    safe_adversarial_modifier = _read_column(row, "safe_adversarial_prompt")
    unsafe_adversarial_modifier = _read_column(row, "unsafe_adversarial_prompt")
    expected_answer = _read_column(row, "expected_answer")

    if not any((canonical_question, safe_guard_rails, unsafe_base_prompt, safe_adversarial_modifier, unsafe_adversarial_modifier, expected_answer)):
        return None

    safe_base_prompt_sequence = _compose_prompt(canonical_question, safe_guard_rails)
    unsafe_base_prompt_sequence = _compose_prompt(unsafe_base_prompt)
    safe_adversarial_prompt_sequence = _compose_prompt(safe_base_prompt_sequence, safe_adversarial_modifier)
    unsafe_adversarial_prompt_sequence = _compose_prompt(unsafe_base_prompt_sequence or canonical_question, unsafe_adversarial_modifier)

    return {
        "canonical_question": canonical_question or None,
        "safe_base_prompt_sequence": safe_base_prompt_sequence or None,
        "unsafe_base_prompt_sequence": unsafe_base_prompt_sequence or None,
        "safe_adversarial_prompt_sequence": safe_adversarial_prompt_sequence or None,
        "unsafe_adversarial_prompt_sequence": unsafe_adversarial_prompt_sequence or None,
        "expected_answer": expected_answer or None,
    }


def _compose_prompt(*parts: Optional[str]) -> str:
    normalized = [str(part).strip() for part in parts if str(part or "").strip()]
    if not normalized:
        return ""
    return "\n\n".join(normalized).strip()


def _parse_prompt_steps(prompt_sequence: str) -> list[str]:
    matches = list(re.finditer(r"Prompt\s*(\d+)\s*[:.]\s*", prompt_sequence, flags=re.IGNORECASE))
    if not matches:
        return [part.strip() for part in prompt_sequence.splitlines() if part.strip()]

    steps: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prompt_sequence)
        step = prompt_sequence[start:end].strip()
        if step:
            steps.append(step)
    return steps


def _normalize_prompt_sequence(prompt_steps: list[str], fallback_text: str) -> str:
    if prompt_steps:
        return "\n".join(f"Prompt {index}: {step}" for index, step in enumerate(prompt_steps, start=1))
    return fallback_text.strip()


def _derive_severity(*, attack_type: str, test_objective: str, prompt_sequence: str, expected_behavior: str) -> str:
    combined = " ".join(part.lower() for part in (attack_type, test_objective, prompt_sequence, expected_behavior))
    if any(keyword in combined for keyword in ("password", "api key", "credential", "system prompt", "override", "privacy")):
        return "HIGH"
    if any(keyword in combined for keyword in ("hallucination", "fairness", "bias", "policy", "poisoning")):
        return "MEDIUM"
    return "LOW"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import workbook-backed audit scenarios into SQLite.")
    parser.add_argument("--excel", type=Path, default=DEFAULT_EXCEL_PATH, help="Path to the source Excel workbook.")
    parser.add_argument("--db", type=Path, default=None, help="Optional path to the audit SQLite database.")
    parser.add_argument("--industry-type", type=str, default=None, help="Optional workbook-level industry type override applied to every imported row.")
    args = parser.parse_args()

    repository = AuditDatabase(db_path=args.db) if args.db else AuditDatabase()
    summary = import_workbook(args.excel, repository=repository, industry_type_override=args.industry_type)
    print(f"Imported {summary['imported_rows']} audit tests into {summary['database_path']}")
    print("Workbook-to-DB mapping:")
    for source_field, db_field in summary["import_mapping"].items():
        print(f"  - {source_field} -> {db_field}")
    if summary["industry_type_override"]:
        print(f"Workbook-level industry override: {summary['industry_type_override']}")
    print(f"Workbook contains real domain column: {'yes' if summary['has_real_domain_column'] else 'no'}")
    for sheet_name, count in summary["per_sheet_counts"].items():
        print(f"  - {sheet_name}: {count}")


if __name__ == "__main__":
    main()
