# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""SQLite storage for workbook-faithful audit scenarios, variants, and run evidence."""

from __future__ import annotations

import json
import hashlib
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from audit.scorer import evaluate_response
from audit.stability import aggregate_runs, infer_refusal_strength, infer_safety_label
from pyrit.common.path import DB_DATA_PATH

DEFAULT_AUDIT_CATEGORIES = (
    "Jailbreak",
    "Prompt Injection",
    "Data Poisoning",
    "Hallucination",
    "Fairness",
    "Privacy",
)

SEVERITY_BUCKETS = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

DEFAULT_EXECUTION_PROFILE = {
    "mode_code": "COMPLIANCE",
    "temperature": 0.0,
    "top_p": 1.0,
    "top_k": None,
    "fixed_seed": True,
    "base_seed": None,
    "seed_strategy": "FIXED",
    "max_tokens": None,
    "run_count_requested": 1,
    "variability_mode": False,
    "created_by": None,
}

SCORING_RESULT_COLUMNS = {
    "attack_detected": "INTEGER",
    "attack_family": "TEXT",
    "attack_subtype": "TEXT",
    "attack_severity_potential": "TEXT",
    "policy_domain": "TEXT",
    "expected_behavior_profile": "TEXT",
    "response_behavior_class": "TEXT",
    "response_safety_label": "TEXT",
    "response_safety_risk": "TEXT",
    "attack_outcome": "TEXT",
    "refusal_strength": "TEXT",
    "refusal_style": "TEXT",
    "boundary_clarity": "TEXT",
    "safe_alternative_quality": "TEXT",
    "scoring_version": "TEXT",
    "prompt_attack_assessment": "TEXT",
    "response_behavior_assessment": "TEXT",
    "refusal_strength_assessment": "TEXT",
    "scenario_verdict_assessment": "TEXT",
    "attack_intent": "TEXT",
    "outcome_safety": "TEXT",
    "refusal_quality": "TEXT",
    "matched_rules": "TEXT",
    "detected_entities": "TEXT",
    "evidence_spans": "TEXT",
    "context_references": "TEXT",
    "policy_pack": "TEXT",
    "confidence": "REAL",
    "review_status": "TEXT",
    "reviewer_id": "TEXT",
    "reviewer_comment": "TEXT",
    "reviewed_at": "TEXT",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    source_sheet_name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    workbook_row_id INTEGER NOT NULL,
    industry_type TEXT NOT NULL DEFAULT 'Generic',
    category_label TEXT,
    attack_type TEXT NOT NULL,
    test_objective TEXT NOT NULL,
    canonical_question TEXT,
    prompt_sequence TEXT NOT NULL,
    prompt_steps_json TEXT NOT NULL,
    adversarial_prompt_sequence TEXT,
    adversarial_prompt_steps_json TEXT,
    safe_base_prompt_sequence TEXT,
    unsafe_base_prompt_sequence TEXT,
    safe_adversarial_prompt_sequence TEXT,
    unsafe_adversarial_prompt_sequence TEXT,
    supporting_documents TEXT,
    expected_behavior TEXT NOT NULL,
    expected_answer TEXT,
    original_result_guidance TEXT,
    domain TEXT,
    severity TEXT NOT NULL,
    source_origin TEXT NOT NULL DEFAULT 'workbook',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES audit_categories(id),
    UNIQUE (category_id, workbook_row_id, source_origin)
);

CREATE TABLE IF NOT EXISTS audit_test_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_test_id INTEGER NOT NULL,
    variant_name TEXT NOT NULL,
    edited_prompt_sequence TEXT NOT NULL,
    edited_prompt_steps_json TEXT NOT NULL,
    edited_expected_behavior TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (parent_test_id) REFERENCES audit_tests(id)
);

CREATE TABLE IF NOT EXISTS audit_runs (
    id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    target_registry_name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    model_name TEXT,
    endpoint TEXT,
    supports_multi_turn INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    selected_industries TEXT NOT NULL DEFAULT '[]',
    selected_categories TEXT NOT NULL DEFAULT '[]',
    selected_test_ids TEXT NOT NULL DEFAULT '[]',
    selected_variant_ids TEXT NOT NULL DEFAULT '[]',
    total_tests INTEGER NOT NULL DEFAULT 0,
    completed_tests INTEGER NOT NULL DEFAULT 0,
    pass_count INTEGER NOT NULL DEFAULT 0,
    warn_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS audit_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    test_id INTEGER NOT NULL,
    variant_id INTEGER,
    display_order INTEGER NOT NULL,
    result_label TEXT NOT NULL,
    variant_name TEXT,
    prompt_source_type TEXT,
    prompt_source_label TEXT,
    prompt_variant TEXT,
    transient_prompt_used INTEGER NOT NULL DEFAULT 0,
    execution_scope_label TEXT,
    variant_group_key TEXT,
    editor_snapshot TEXT,
    industry_type TEXT NOT NULL DEFAULT 'Generic',
    category_name TEXT NOT NULL,
    domain TEXT,
    severity TEXT NOT NULL,
    test_identifier TEXT NOT NULL,
    workbook_row_id INTEGER NOT NULL,
    attack_type TEXT NOT NULL,
    test_objective TEXT NOT NULL,
    original_workbook_prompt TEXT NOT NULL,
    actual_prompt_sequence TEXT NOT NULL,
    actual_prompt_steps_json TEXT NOT NULL,
    supporting_documents_snapshot TEXT,
    prompt_sent TEXT,
    response_received TEXT,
    expected_behavior_snapshot TEXT NOT NULL,
    original_result_guidance_snapshot TEXT,
    score_status TEXT,
    risk_level TEXT,
    score_value INTEGER,
    score_reason TEXT,
    audit_reasoning TEXT,
    attack_detected INTEGER,
    attack_family TEXT,
    attack_subtype TEXT,
    attack_severity_potential TEXT,
    policy_domain TEXT,
    expected_behavior_profile TEXT,
    response_behavior_class TEXT,
    response_safety_label TEXT,
    response_safety_risk TEXT,
    attack_outcome TEXT,
    refusal_strength TEXT,
    refusal_style TEXT,
    boundary_clarity TEXT,
    safe_alternative_quality TEXT,
    scoring_version TEXT,
    prompt_attack_assessment TEXT,
    response_behavior_assessment TEXT,
    refusal_strength_assessment TEXT,
    scenario_verdict_assessment TEXT,
    attack_intent TEXT,
    outcome_safety TEXT,
    refusal_quality TEXT,
    matched_rules TEXT,
    detected_entities TEXT,
    evidence_spans TEXT,
    context_references TEXT,
    policy_pack TEXT,
    confidence REAL,
    review_status TEXT,
    reviewer_id TEXT,
    reviewer_comment TEXT,
    reviewed_at TEXT,
    interaction_log TEXT,
    execution_status TEXT NOT NULL,
    attack_result_id TEXT,
    conversation_id TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (run_id) REFERENCES audit_runs(id),
    FOREIGN KEY (test_id) REFERENCES audit_tests(id),
    FOREIGN KEY (variant_id) REFERENCES audit_test_variants(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_tests_category_id ON audit_tests(category_id);
CREATE INDEX IF NOT EXISTS idx_audit_tests_domain ON audit_tests(domain);
CREATE INDEX IF NOT EXISTS idx_audit_tests_active ON audit_tests(is_active);
CREATE INDEX IF NOT EXISTS idx_audit_variants_parent_test_id ON audit_test_variants(parent_test_id);
CREATE INDEX IF NOT EXISTS idx_audit_variants_active ON audit_test_variants(is_active);
CREATE INDEX IF NOT EXISTS idx_audit_results_run_id ON audit_results(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_results_execution_status ON audit_results(execution_status);
CREATE INDEX IF NOT EXISTS idx_audit_runs_status ON audit_runs(status);
"""

MULTIRUN_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_execution_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_session_id TEXT NOT NULL,
    mode_code TEXT NOT NULL,
    model_target_type TEXT,
    model_target_name TEXT,
    provider_name TEXT,
    api_style TEXT,
    temperature REAL,
    top_p REAL,
    top_k INTEGER,
    fixed_seed INTEGER NOT NULL DEFAULT 1,
    base_seed INTEGER,
    seed_strategy TEXT,
    max_tokens INTEGER,
    run_count_requested INTEGER NOT NULL DEFAULT 1,
    variability_mode INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    created_by TEXT,
    FOREIGN KEY (audit_session_id) REFERENCES audit_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_execution_profile_session ON audit_execution_profile(audit_session_id);

CREATE TABLE IF NOT EXISTS audit_test_case_result_group (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_session_id TEXT NOT NULL,
    execution_profile_id INTEGER NOT NULL,
    prompt_source_type TEXT NOT NULL,
    prompt_source_ref TEXT,
    benchmark_scenario_id INTEGER,
    industry_type TEXT,
    category_code TEXT,
    category_name TEXT,
    subcategory_name TEXT,
    prompt_variant TEXT,
    severity_expected TEXT,
    expected_behavior_text TEXT,
    objective_text TEXT,
    run_count_actual INTEGER NOT NULL DEFAULT 1,
    aggregate_verdict TEXT,
    aggregate_risk_level TEXT,
    pass_rate REAL,
    warn_rate REAL,
    fail_rate REAL,
    safe_rate REAL,
    attack_success_rate REAL,
    resistance_rate REAL,
    variance_score REAL,
    stability_score REAL,
    worst_case_verdict TEXT,
    worst_case_risk_level TEXT,
    best_case_verdict TEXT,
    summary_reasoning TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (audit_session_id) REFERENCES audit_runs(id),
    FOREIGN KEY (execution_profile_id) REFERENCES audit_execution_profile(id),
    FOREIGN KEY (benchmark_scenario_id) REFERENCES benchmark_scenario(id)
);

CREATE INDEX IF NOT EXISTS idx_result_group_session ON audit_test_case_result_group(audit_session_id);
CREATE INDEX IF NOT EXISTS idx_result_group_category ON audit_test_case_result_group(category_name, subcategory_name);

CREATE TABLE IF NOT EXISTS audit_test_case_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_group_id INTEGER NOT NULL,
    run_no INTEGER NOT NULL,
    seed_used INTEGER,
    temperature_used REAL,
    top_p_used REAL,
    top_k_used INTEGER,
    request_payload_hash TEXT,
    context_hash TEXT,
    system_prompt_hash TEXT,
    prompt_text TEXT,
    normalized_prompt_text TEXT,
    raw_response_text TEXT,
    normalized_response_text TEXT,
    response_latency_ms INTEGER,
    token_input_count INTEGER,
    token_output_count INTEGER,
    evaluator_safety_label TEXT,
    evaluator_safety_risk TEXT,
    evaluator_compliance_label TEXT,
    attack_family TEXT,
    attack_subtype TEXT,
    attack_severity_potential TEXT,
    policy_domain TEXT,
    expected_behavior_profile TEXT,
    response_behavior_class TEXT,
    attack_outcome TEXT,
    refusal_strength TEXT,
    refusal_style TEXT,
    boundary_clarity TEXT,
    safe_alternative_quality TEXT,
    evaluator_reasoning TEXT,
    scoring_version TEXT,
    prompt_attack_assessment TEXT,
    response_behavior_assessment TEXT,
    refusal_strength_assessment TEXT,
    scenario_verdict_assessment TEXT,
    attack_intent TEXT,
    outcome_safety TEXT,
    refusal_quality TEXT,
    matched_rules TEXT,
    detected_entities TEXT,
    evidence_spans TEXT,
    context_references TEXT,
    policy_pack TEXT,
    confidence REAL,
    is_worst_case INTEGER NOT NULL DEFAULT 0,
    is_best_case INTEGER NOT NULL DEFAULT 0,
    run_status TEXT NOT NULL DEFAULT 'COMPLETED',
    created_at TEXT NOT NULL,
    FOREIGN KEY (result_group_id) REFERENCES audit_test_case_result_group(id),
    UNIQUE(result_group_id, run_no)
);

CREATE INDEX IF NOT EXISTS idx_run_group ON audit_test_case_run(result_group_id);
CREATE INDEX IF NOT EXISTS idx_run_safety ON audit_test_case_run(evaluator_safety_label, evaluator_safety_risk);
CREATE INDEX IF NOT EXISTS idx_run_compliance ON audit_test_case_run(evaluator_compliance_label);

CREATE TABLE IF NOT EXISTS audit_retrieval_trace (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    document_id TEXT,
    document_name TEXT,
    document_type TEXT,
    page_no INTEGER,
    chunk_id TEXT,
    ocr_used INTEGER NOT NULL DEFAULT 0,
    retrieved_text_excerpt TEXT,
    retrieval_rank INTEGER,
    retrieval_score REAL,
    source_uri TEXT,
    citation_label TEXT,
    FOREIGN KEY (run_id) REFERENCES audit_test_case_run(id)
);

CREATE INDEX IF NOT EXISTS idx_retrieval_run ON audit_retrieval_trace(run_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_doc ON audit_retrieval_trace(document_name, page_no);

CREATE TABLE IF NOT EXISTS audit_target_capability_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    api_style TEXT NOT NULL,
    modality TEXT NOT NULL,
    supports_deterministic_seed INTEGER NOT NULL DEFAULT 0,
    supports_temperature INTEGER NOT NULL DEFAULT 0,
    supports_multi_run INTEGER NOT NULL DEFAULT 1,
    best_for TEXT NOT NULL,
    not_suitable_for TEXT NOT NULL,
    example_scenarios TEXT NOT NULL,
    provider_examples TEXT NOT NULL,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);
"""

BENCHMARK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS benchmark_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    benchmark_family TEXT,
    model_name TEXT,
    version TEXT,
    category_name TEXT,
    subcategory_name TEXT,
    scenario_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_benchmark_source_type ON benchmark_source(source_type);
CREATE INDEX IF NOT EXISTS idx_benchmark_source_family ON benchmark_source(benchmark_family);
CREATE INDEX IF NOT EXISTS idx_benchmark_source_model ON benchmark_source(model_name);
CREATE INDEX IF NOT EXISTS idx_benchmark_source_category ON benchmark_source(category_name, subcategory_name);

CREATE TABLE IF NOT EXISTS benchmark_scenario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_source_id INTEGER NOT NULL,
    scenario_code TEXT,
    title TEXT NOT NULL,
    category_name TEXT,
    subcategory_name TEXT,
    objective_text TEXT,
    prompt_text TEXT,
    expected_behavior_text TEXT,
    modality TEXT NOT NULL DEFAULT 'text',
    recommended_target_types TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    severity_hint TEXT,
    replay_supported INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (benchmark_source_id) REFERENCES benchmark_source(id),
    UNIQUE(benchmark_source_id, scenario_code)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_scenario_source ON benchmark_scenario(benchmark_source_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_scenario_category ON benchmark_scenario(category_name, subcategory_name);
CREATE INDEX IF NOT EXISTS idx_benchmark_scenario_replay ON benchmark_scenario(replay_supported);

CREATE TABLE IF NOT EXISTS benchmark_media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_source_id INTEGER NOT NULL,
    scenario_id INTEGER,
    media_type TEXT NOT NULL,
    media_uri TEXT NOT NULL,
    thumbnail_uri TEXT,
    caption TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (benchmark_source_id) REFERENCES benchmark_source(id),
    FOREIGN KEY (scenario_id) REFERENCES benchmark_scenario(id)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_media_source ON benchmark_media(benchmark_source_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_media_scenario ON benchmark_media(scenario_id);
"""

TARGET_CAPABILITY_SEED = (
    {
        "target_code": "OPENAI_CHAT_TARGET",
        "display_name": "OpenAIChatTarget",
        "api_style": "chat",
        "modality": "text",
        "supports_deterministic_seed": 1,
        "supports_temperature": 1,
        "supports_multi_run": 1,
        "best_for": "Chat-completion compatible text targets, including OpenAI-compatible local or enterprise gateways.",
        "not_suitable_for": "Image, video, audio-only, or browser-click workflows.",
        "example_scenarios": "Audit an enterprise assistant served by Azure OpenAI, OpenAI, Ollama OpenAI-compatible API, or an internal chat gateway.",
        "provider_examples": "Azure, OpenAI, Ollama, Custom OpenAI-compatible gateway",
        "is_builtin": 1,
        "sort_order": 10,
    },
    {
        "target_code": "OPENAI_COMPLETION_TARGET",
        "display_name": "OpenAICompletionTarget",
        "api_style": "completion",
        "modality": "text",
        "supports_deterministic_seed": 0,
        "supports_temperature": 1,
        "supports_multi_run": 1,
        "best_for": "Legacy completion-style text models or gateways that expose a completion API.",
        "not_suitable_for": "Multi-turn chat behavior or tool-rich app testing.",
        "example_scenarios": "Regression-test a legacy text-generation endpoint used in an internal workflow.",
        "provider_examples": "OpenAI-protocol completion services, Custom",
        "is_builtin": 1,
        "sort_order": 20,
    },
    {
        "target_code": "OPENAI_RESPONSE_TARGET",
        "display_name": "OpenAIResponseTarget",
        "api_style": "response",
        "modality": "mixed",
        "supports_deterministic_seed": 1,
        "supports_temperature": 1,
        "supports_multi_run": 1,
        "best_for": "Response API style targets and app gateways that expose richer response objects.",
        "not_suitable_for": "Browser-only products with no API access.",
        "example_scenarios": "Audit a tool-using assistant via a response-style API gateway.",
        "provider_examples": "OpenAI, Azure gateway, Custom response-compatible gateway",
        "is_builtin": 1,
        "sort_order": 30,
    },
    {
        "target_code": "OPENAI_VECTOR_STORE_TARGET",
        "display_name": "OpenAIVectorStoreTarget",
        "api_style": "response",
        "modality": "text",
        "supports_deterministic_seed": 1,
        "supports_temperature": 1,
        "supports_multi_run": 1,
        "best_for": "Retrieval-backed audits against an OpenAI vector store where prompts should be answered with file_search over uploaded documents.",
        "not_suitable_for": "Browser-only app audits, non-retrieval chat endpoints, or providers that do not support OpenAI Responses API file_search.",
        "example_scenarios": "Audit a legal or contract assistant backed by retrieved judgment PDFs while preserving Siddhii's existing Interactive Audit and evaluator pipeline.",
        "provider_examples": "OpenAI Responses API with vector stores; future retrieval-backed provider targets can reuse the same retrieval_store_id pattern.",
        "is_builtin": 1,
        "sort_order": 35,
    },
    {
        "target_code": "GEMINI_FILE_SEARCH_TARGET",
        "display_name": "GeminiFileSearchTarget",
        "api_style": "generate_content",
        "modality": "text",
        "supports_deterministic_seed": 0,
        "supports_temperature": 0,
        "supports_multi_run": 1,
        "best_for": "Retrieval-backed audits against a Gemini File Search store where prompts should be answered from uploaded files.",
        "not_suitable_for": "OpenAI Responses API vector stores, browser-only app audits, or non-retrieval chat endpoints.",
        "example_scenarios": "Audit an HR or policy assistant backed by Gemini File Search while preserving Siddhii's existing Interactive Audit, evidence, and evaluator pipeline.",
        "provider_examples": "Gemini API with file_search over fileSearchStores resources.",
        "is_builtin": 1,
        "sort_order": 36,
    },
    {
        "target_code": "OPENAI_IMAGE_TARGET",
        "display_name": "OpenAIImageTarget",
        "api_style": "image",
        "modality": "image",
        "supports_deterministic_seed": 0,
        "supports_temperature": 0,
        "supports_multi_run": 1,
        "best_for": "Image generation safety and policy tests.",
        "not_suitable_for": "Text-only chat compliance testing.",
        "example_scenarios": "Audit whether a marketing image generator refuses unsafe visual requests.",
        "provider_examples": "OpenAI image APIs, compatible image gateways",
        "is_builtin": 1,
        "sort_order": 40,
    },
    {
        "target_code": "OPENAI_VIDEO_TARGET",
        "display_name": "OpenAIVideoTarget",
        "api_style": "video",
        "modality": "video",
        "supports_deterministic_seed": 0,
        "supports_temperature": 0,
        "supports_multi_run": 1,
        "best_for": "Video-generation policy checks where supported by an adapter.",
        "not_suitable_for": "Text-only refusal/compliance checks.",
        "example_scenarios": "Audit a video generator for prohibited scenario generation.",
        "provider_examples": "Video generation providers via compatible adapters",
        "is_builtin": 1,
        "sort_order": 50,
    },
    {
        "target_code": "OPENAI_TTS_TARGET",
        "display_name": "OpenAITTSTarget",
        "api_style": "tts",
        "modality": "audio",
        "supports_deterministic_seed": 0,
        "supports_temperature": 0,
        "supports_multi_run": 1,
        "best_for": "Text-to-speech behavior, voice generation, and audio output tests.",
        "not_suitable_for": "Chatbot reasoning or RAG retrieval evaluation.",
        "example_scenarios": "Audit whether a TTS workflow produces disallowed impersonation content.",
        "provider_examples": "OpenAI TTS, custom TTS gateways",
        "is_builtin": 1,
        "sort_order": 60,
    },
    {
        "target_code": "HTTP_TARGET",
        "display_name": "HTTP / API Target",
        "api_style": "http",
        "modality": "mixed",
        "supports_deterministic_seed": 0,
        "supports_temperature": 0,
        "supports_multi_run": 1,
        "best_for": "Auditing application-level AI systems through REST APIs.",
        "not_suitable_for": "Direct model parameter control unless the app API exposes it.",
        "example_scenarios": "Audit a contract assistant, support bot, or risk-scoring app through its enterprise API.",
        "provider_examples": "Azure apps, Claude/Gemini apps, custom RAG systems, internal APIs",
        "is_builtin": 0,
        "sort_order": 70,
    },
    {
        "target_code": "BROWSER_TARGET",
        "display_name": "Browser Target",
        "api_style": "browser",
        "modality": "browser",
        "supports_deterministic_seed": 0,
        "supports_temperature": 0,
        "supports_multi_run": 1,
        "best_for": "Auditing browser-based AI copilots and products without stable backend APIs.",
        "not_suitable_for": "Low-level model parameter reproducibility.",
        "example_scenarios": "Audit an embedded CRM copilot or browser-only enterprise assistant.",
        "provider_examples": "Copilots, SaaS AI apps, custom browser workflows",
        "is_builtin": 0,
        "sort_order": 80,
    },
    {
        "target_code": "CUSTOM_TARGET",
        "display_name": "Custom Target Adapter",
        "api_style": "custom",
        "modality": "mixed",
        "supports_deterministic_seed": 0,
        "supports_temperature": 0,
        "supports_multi_run": 1,
        "best_for": "Enterprise systems needing custom authentication, orchestration, files, tools, or telemetry capture.",
        "not_suitable_for": "Quick demos when a standard OpenAI-compatible target already works.",
        "example_scenarios": "Audit a Gemini, Claude, Azure, or internal AI product via a custom adapter.",
        "provider_examples": "Azure, OpenAI, Ollama, Claude, Gemini, Custom",
        "is_builtin": 0,
        "sort_order": 90,
    },
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads_json(value: Optional[str], default: Any) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)


def _dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _bool_from_db(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


def _interaction_log_to_conversation_history(interaction_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for index, item in enumerate(interaction_log, start=1):
        prompt = str(item.get("prompt") or "").strip()
        response = str(item.get("response") or "").strip()
        if prompt:
            history.append(
                {
                    "turn_id": f"user-{index}",
                    "role": "user",
                    "user_prompt": prompt,
                    "content": prompt,
                }
            )
        if response:
            history.append(
                {
                    "turn_id": f"assistant-{index}",
                    "role": "assistant",
                    "assistant_response": response,
                    "content": response,
                }
            )
    return history[:-1] if history and history[-1].get("role") == "assistant" else history


class AuditDatabase:
    """Repository for workbook-backed audit data."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        default_path = DB_DATA_PATH / "audit.db"
        self._db_path = Path(db_path) if db_path else default_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            self._migrate_legacy_schema(conn)
            conn.executescript(SCHEMA_SQL)
            conn.executescript(MULTIRUN_SCHEMA_SQL)
            conn.executescript(BENCHMARK_SCHEMA_SQL)
            self._ensure_workbook_model_columns(conn)
            self._ensure_multirun_columns(conn)
            conn.commit()
        self.seed_categories(DEFAULT_AUDIT_CATEGORIES)
        self.seed_target_capability_catalog()
        self.backfill_scoring_v2()

    def _ensure_workbook_model_columns(self, conn: sqlite3.Connection) -> None:
        test_columns = {row["name"] for row in conn.execute("PRAGMA table_info(audit_tests)").fetchall()}
        test_additions = {
            "industry_type": "TEXT NOT NULL DEFAULT 'Generic'",
            "category_label": "TEXT",
            "canonical_question": "TEXT",
            "adversarial_prompt_sequence": "TEXT",
            "adversarial_prompt_steps_json": "TEXT",
            "safe_base_prompt_sequence": "TEXT",
            "unsafe_base_prompt_sequence": "TEXT",
            "safe_adversarial_prompt_sequence": "TEXT",
            "unsafe_adversarial_prompt_sequence": "TEXT",
            "expected_answer": "TEXT",
        }
        for column, ddl_type in test_additions.items():
            if column not in test_columns:
                conn.execute(f"ALTER TABLE audit_tests ADD COLUMN {column} {ddl_type}")
        conn.execute(
            """
            UPDATE audit_tests
            SET industry_type = 'Generic'
            WHERE industry_type IS NULL OR TRIM(industry_type) = ''
            """
        )
        if "category_label" in {row["name"] for row in conn.execute("PRAGMA table_info(audit_tests)").fetchall()}:
            conn.execute(
                """
                UPDATE audit_tests
                SET category_label = (
                    SELECT c.source_sheet_name
                    FROM audit_categories c
                    WHERE c.id = audit_tests.category_id
                )
                WHERE category_label IS NULL OR TRIM(category_label) = ''
                """
            )
        conn.execute(
            """
            UPDATE audit_tests
            SET canonical_question = COALESCE(NULLIF(TRIM(test_objective), ''), NULLIF(TRIM(attack_type), ''))
            WHERE canonical_question IS NULL OR TRIM(canonical_question) = ''
            """
        )
        conn.execute(
            """
            UPDATE audit_tests
            SET safe_base_prompt_sequence = prompt_sequence
            WHERE safe_base_prompt_sequence IS NULL OR TRIM(safe_base_prompt_sequence) = ''
            """
        )
        conn.execute(
            """
            UPDATE audit_tests
            SET safe_adversarial_prompt_sequence = adversarial_prompt_sequence
            WHERE (safe_adversarial_prompt_sequence IS NULL OR TRIM(safe_adversarial_prompt_sequence) = '')
              AND adversarial_prompt_sequence IS NOT NULL
              AND TRIM(adversarial_prompt_sequence) <> ''
            """
        )
        conn.execute(
            """
            UPDATE audit_tests
            SET expected_answer = expected_behavior
            WHERE expected_answer IS NULL OR TRIM(expected_answer) = ''
            """
        )

        run_columns = {row["name"] for row in conn.execute("PRAGMA table_info(audit_runs)").fetchall()}
        if "selected_industries" not in run_columns:
            conn.execute("ALTER TABLE audit_runs ADD COLUMN selected_industries TEXT NOT NULL DEFAULT '[]'")

    def _ensure_multirun_columns(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(audit_results)").fetchall()}
        additions = {
            "stability_group_id": "INTEGER",
            "stability_run_id": "INTEGER",
            "stability_run_no": "INTEGER",
            "prompt_source_type": "TEXT",
            "prompt_source_label": "TEXT",
            "prompt_variant": "TEXT",
            "transient_prompt_used": "INTEGER NOT NULL DEFAULT 0",
            "execution_scope_label": "TEXT",
            "variant_group_key": "TEXT",
            "editor_snapshot": "TEXT",
            "supporting_documents_snapshot": "TEXT",
            "industry_type": "TEXT NOT NULL DEFAULT 'Generic'",
        }
        additions.update(SCORING_RESULT_COLUMNS)
        for column, ddl_type in additions.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE audit_results ADD COLUMN {column} {ddl_type}")

        group_columns = {row["name"] for row in conn.execute("PRAGMA table_info(audit_test_case_result_group)").fetchall()}
        if "benchmark_scenario_id" not in group_columns:
            conn.execute("ALTER TABLE audit_test_case_result_group ADD COLUMN benchmark_scenario_id INTEGER")
        for column, ddl_type in {"industry_type": "TEXT", "prompt_variant": "TEXT"}.items():
            if column not in group_columns:
                conn.execute(f"ALTER TABLE audit_test_case_result_group ADD COLUMN {column} {ddl_type}")
        for column, ddl_type in {"attack_success_rate": "REAL", "resistance_rate": "REAL"}.items():
            if column not in group_columns:
                conn.execute(f"ALTER TABLE audit_test_case_result_group ADD COLUMN {column} {ddl_type}")

        run_columns = {row["name"] for row in conn.execute("PRAGMA table_info(audit_test_case_run)").fetchall()}
        run_additions = {
            "attack_family": "TEXT",
            "attack_subtype": "TEXT",
            "attack_severity_potential": "TEXT",
            "policy_domain": "TEXT",
            "expected_behavior_profile": "TEXT",
            "response_behavior_class": "TEXT",
            "attack_outcome": "TEXT",
            "refusal_style": "TEXT",
            "boundary_clarity": "TEXT",
            "safe_alternative_quality": "TEXT",
            "scoring_version": "TEXT",
            "prompt_attack_assessment": "TEXT",
            "response_behavior_assessment": "TEXT",
            "refusal_strength_assessment": "TEXT",
            "scenario_verdict_assessment": "TEXT",
            "attack_intent": "TEXT",
            "outcome_safety": "TEXT",
            "refusal_quality": "TEXT",
            "matched_rules": "TEXT",
            "detected_entities": "TEXT",
            "evidence_spans": "TEXT",
            "context_references": "TEXT",
            "policy_pack": "TEXT",
            "confidence": "REAL",
        }
        for column, ddl_type in run_additions.items():
            if column not in run_columns:
                conn.execute(f"ALTER TABLE audit_test_case_run ADD COLUMN {column} {ddl_type}")

    def seed_target_capability_catalog(self) -> None:
        with closing(self._connect()) as conn, conn:
            for item in TARGET_CAPABILITY_SEED:
                conn.execute(
                    """
                    INSERT INTO audit_target_capability_catalog (
                        target_code,
                        display_name,
                        api_style,
                        modality,
                        supports_deterministic_seed,
                        supports_temperature,
                        supports_multi_run,
                        best_for,
                        not_suitable_for,
                        example_scenarios,
                        provider_examples,
                        is_builtin,
                        sort_order
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(target_code) DO UPDATE SET
                        display_name = excluded.display_name,
                        api_style = excluded.api_style,
                        modality = excluded.modality,
                        supports_deterministic_seed = excluded.supports_deterministic_seed,
                        supports_temperature = excluded.supports_temperature,
                        supports_multi_run = excluded.supports_multi_run,
                        best_for = excluded.best_for,
                        not_suitable_for = excluded.not_suitable_for,
                        example_scenarios = excluded.example_scenarios,
                        provider_examples = excluded.provider_examples,
                        is_builtin = excluded.is_builtin,
                        sort_order = excluded.sort_order
                    """,
                    (
                        item["target_code"],
                        item["display_name"],
                        item["api_style"],
                        item["modality"],
                        item["supports_deterministic_seed"],
                        item["supports_temperature"],
                        item["supports_multi_run"],
                        item["best_for"],
                        item["not_suitable_for"],
                        item["example_scenarios"],
                        item["provider_examples"],
                        item["is_builtin"],
                        item["sort_order"],
                    ),
                )

    def backfill_scoring_v2(self) -> None:
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """
                SELECT *
                FROM audit_results
                WHERE execution_status = 'completed'
                  AND COALESCE(scoring_version, '') = ''
                ORDER BY run_id, display_order, id
                """
            ).fetchall()
            touched_runs: set[str] = set()
            for row in rows:
                item = dict(row)
                interaction_log = _loads_json(item.get("interaction_log"), [])
                evaluation = evaluate_response(
                    response_text=item.get("response_received") or "",
                    expected_behavior=item.get("expected_behavior_snapshot") or "",
                    category_name=item.get("category_name") or "",
                    scoring_guidance=item.get("original_result_guidance_snapshot") or "",
                    prompt_sequence=item.get("actual_prompt_sequence") or "",
                    attack_type=item.get("attack_type") or "",
                    conversation_history=_interaction_log_to_conversation_history(interaction_log),
                )
                conn.execute(
                    """
                    UPDATE audit_results
                    SET score_status = ?,
                        risk_level = ?,
                        score_value = ?,
                        score_reason = ?,
                        audit_reasoning = ?,
                        attack_detected = ?,
                        attack_family = ?,
                        attack_subtype = ?,
                        attack_severity_potential = ?,
                        policy_domain = ?,
                        expected_behavior_profile = ?,
                        response_behavior_class = ?,
                        response_safety_label = ?,
                        response_safety_risk = ?,
                        attack_outcome = ?,
                        refusal_strength = ?,
                        refusal_style = ?,
                        boundary_clarity = ?,
                        safe_alternative_quality = ?,
                        scoring_version = ?,
                        prompt_attack_assessment = ?,
                        response_behavior_assessment = ?,
                        refusal_strength_assessment = ?,
                        scenario_verdict_assessment = ?,
                        attack_intent = ?,
                        outcome_safety = ?,
                        refusal_quality = ?,
                        matched_rules = ?,
                        detected_entities = ?,
                        evidence_spans = ?,
                        context_references = ?,
                        policy_pack = ?,
                        confidence = ?
                    WHERE id = ?
                    """,
                    (
                        evaluation["status"],
                        evaluation["risk"],
                        evaluation["score"],
                        evaluation["reason"],
                        evaluation.get("audit_reasoning") or evaluation["reason"],
                        1 if evaluation.get("attack_detected") else 0,
                        evaluation.get("attack_family"),
                        evaluation.get("attack_subtype"),
                        evaluation.get("attack_severity_potential"),
                        evaluation.get("policy_domain"),
                        evaluation.get("expected_behavior_profile"),
                        evaluation.get("response_behavior_class"),
                        evaluation.get("response_safety_label"),
                        evaluation.get("response_safety_risk"),
                        evaluation.get("attack_outcome"),
                        evaluation.get("refusal_strength"),
                        evaluation.get("refusal_style"),
                        evaluation.get("boundary_clarity"),
                        evaluation.get("safe_alternative_quality"),
                        evaluation.get("scoring_version"),
                        _dumps_json(evaluation.get("prompt_attack_assessment") or {}),
                        _dumps_json(evaluation.get("response_behavior_assessment") or {}),
                        _dumps_json(evaluation.get("refusal_strength_assessment") or {}),
                        _dumps_json(evaluation.get("scenario_verdict_assessment") or {}),
                        evaluation.get("attack_intent"),
                        evaluation.get("outcome_safety"),
                        evaluation.get("refusal_quality"),
                        _dumps_json(evaluation.get("matched_rules") or []),
                        _dumps_json(evaluation.get("detected_entities") or []),
                        _dumps_json(evaluation.get("evidence_spans") or []),
                        _dumps_json(evaluation.get("context_references") or {}),
                        evaluation.get("policy_pack"),
                        evaluation.get("confidence"),
                        item["id"],
                    ),
                )
                if item.get("stability_run_id"):
                    conn.execute(
                        """
                        UPDATE audit_test_case_run
                        SET evaluator_safety_label = ?,
                            evaluator_safety_risk = ?,
                            evaluator_compliance_label = ?,
                            attack_family = ?,
                            attack_subtype = ?,
                            attack_severity_potential = ?,
                            policy_domain = ?,
                            expected_behavior_profile = ?,
                            response_behavior_class = ?,
                            attack_outcome = ?,
                            refusal_strength = ?,
                            refusal_style = ?,
                            boundary_clarity = ?,
                            safe_alternative_quality = ?,
                            evaluator_reasoning = ?,
                            scoring_version = ?,
                            prompt_attack_assessment = ?,
                            response_behavior_assessment = ?,
                            refusal_strength_assessment = ?,
                            scenario_verdict_assessment = ?,
                            attack_intent = ?,
                            outcome_safety = ?,
                            refusal_quality = ?,
                            matched_rules = ?,
                            detected_entities = ?,
                            evidence_spans = ?,
                            context_references = ?,
                            policy_pack = ?,
                            confidence = ?
                        WHERE id = ?
                        """,
                        (
                            evaluation.get("response_safety_label"),
                            evaluation.get("response_safety_risk"),
                            evaluation.get("status"),
                            evaluation.get("attack_family"),
                            evaluation.get("attack_subtype"),
                            evaluation.get("attack_severity_potential"),
                            evaluation.get("policy_domain"),
                            evaluation.get("expected_behavior_profile"),
                            evaluation.get("response_behavior_class"),
                            evaluation.get("attack_outcome"),
                            evaluation.get("refusal_strength"),
                            evaluation.get("refusal_style"),
                            evaluation.get("boundary_clarity"),
                            evaluation.get("safe_alternative_quality"),
                            evaluation.get("audit_reasoning") or evaluation["reason"],
                            evaluation.get("scoring_version"),
                            _dumps_json(evaluation.get("prompt_attack_assessment") or {}),
                            _dumps_json(evaluation.get("response_behavior_assessment") or {}),
                            _dumps_json(evaluation.get("refusal_strength_assessment") or {}),
                            _dumps_json(evaluation.get("scenario_verdict_assessment") or {}),
                            evaluation.get("attack_intent"),
                            evaluation.get("outcome_safety"),
                            evaluation.get("refusal_quality"),
                            _dumps_json(evaluation.get("matched_rules") or []),
                            _dumps_json(evaluation.get("detected_entities") or []),
                            _dumps_json(evaluation.get("evidence_spans") or []),
                            _dumps_json(evaluation.get("context_references") or {}),
                            evaluation.get("policy_pack"),
                            evaluation.get("confidence"),
                            item["stability_run_id"],
                        ),
                    )
                touched_runs.add(str(item["run_id"]))
            for run_id in touched_runs:
                self._recalculate_run_summary(conn, run_id)
                self._recalculate_stability_groups(conn, run_id)

    def seed_categories(self, categories: tuple[str, ...] | list[str]) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            for category in categories:
                conn.execute(
                    """
                    INSERT INTO audit_categories (name, source_sheet_name, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        source_sheet_name = excluded.source_sheet_name
                    """,
                    (category.strip(), category, now),
                )

    def sync_categories_from_workbook(self, sheet_names: list[str]) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            for sheet_name in sheet_names:
                canonical_name = sheet_name.strip()
                conn.execute(
                    """
                    INSERT INTO audit_categories (name, source_sheet_name, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        source_sheet_name = excluded.source_sheet_name
                    """,
                    (canonical_name, sheet_name, now),
                )

    def deactivate_tests_for_sheet(self, sheet_name: str) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE audit_tests SET is_active = 0, updated_at = ? WHERE category_id = (SELECT id FROM audit_categories WHERE source_sheet_name = ? OR name = ?)",
                (now, sheet_name, sheet_name.strip()),
            )

    def get_category_id(self, category_name: str) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id FROM audit_categories WHERE source_sheet_name = ? OR name = ?",
                (category_name, category_name.strip()),
            ).fetchone()
        if row is None:
            raise ValueError(f"Unknown audit category '{category_name}'")
        return int(row["id"])

    def ensure_category(self, category_name: str, *, source_sheet_name: Optional[str] = None) -> int:
        now = _utc_now()
        canonical_name = category_name.strip() or "Unspecified"
        source_name = (source_sheet_name or category_name).strip() or canonical_name
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO audit_categories (name, source_sheet_name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO NOTHING
                """,
                (canonical_name, source_name, now),
            )
            row = conn.execute(
                "SELECT id FROM audit_categories WHERE name = ? OR source_sheet_name = ?",
                (canonical_name, source_name),
            ).fetchone()
        if row is None:
            raise ValueError(f"Failed to create audit category '{canonical_name}'")
        return int(row["id"])

    def upsert_test(self, record: dict[str, Any]) -> int:
        now = _utc_now()
        payload = (
            record["category_id"],
            record["workbook_row_id"],
            self._normalize_industry_type(record.get("industry_type")),
            str(record.get("category_label") or "").strip() or None,
            record["attack_type"],
            record.get("test_objective", ""),
            str(record.get("canonical_question") or "").strip() or None,
            record["prompt_sequence"],
            _dumps_json(record["prompt_steps"]),
            record.get("adversarial_prompt_sequence"),
            _dumps_json(record["adversarial_prompt_steps"]) if record.get("adversarial_prompt_steps") else None,
            record.get("safe_base_prompt_sequence"),
            record.get("unsafe_base_prompt_sequence"),
            record.get("safe_adversarial_prompt_sequence"),
            record.get("unsafe_adversarial_prompt_sequence"),
            _dumps_json(record["supporting_documents"]) if record.get("supporting_documents") else None,
            record["expected_behavior"],
            str(record.get("expected_answer") or "").strip() or None,
            record.get("original_result_guidance"),
            record.get("domain"),
            record["severity"],
            record.get("source_origin", "workbook"),
            int(record.get("is_active", 1)),
            now,
            now,
        )
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO audit_tests (
                    category_id,
                    workbook_row_id,
                    industry_type,
                    category_label,
                    attack_type,
                    test_objective,
                    canonical_question,
                    prompt_sequence,
                    prompt_steps_json,
                    adversarial_prompt_sequence,
                    adversarial_prompt_steps_json,
                    safe_base_prompt_sequence,
                    unsafe_base_prompt_sequence,
                    safe_adversarial_prompt_sequence,
                    unsafe_adversarial_prompt_sequence,
                    supporting_documents,
                    expected_behavior,
                    expected_answer,
                    original_result_guidance,
                    domain,
                    severity,
                    source_origin,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(category_id, workbook_row_id, source_origin) DO UPDATE SET
                    industry_type = excluded.industry_type,
                    category_label = excluded.category_label,
                    attack_type = excluded.attack_type,
                    test_objective = excluded.test_objective,
                    canonical_question = excluded.canonical_question,
                    prompt_sequence = excluded.prompt_sequence,
                    prompt_steps_json = excluded.prompt_steps_json,
                    adversarial_prompt_sequence = excluded.adversarial_prompt_sequence,
                    adversarial_prompt_steps_json = excluded.adversarial_prompt_steps_json,
                    safe_base_prompt_sequence = excluded.safe_base_prompt_sequence,
                    unsafe_base_prompt_sequence = excluded.unsafe_base_prompt_sequence,
                    safe_adversarial_prompt_sequence = excluded.safe_adversarial_prompt_sequence,
                    unsafe_adversarial_prompt_sequence = excluded.unsafe_adversarial_prompt_sequence,
                    supporting_documents = excluded.supporting_documents,
                    expected_behavior = excluded.expected_behavior,
                    expected_answer = excluded.expected_answer,
                    original_result_guidance = excluded.original_result_guidance,
                    domain = excluded.domain,
                    severity = excluded.severity,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
            row = conn.execute(
                """
                SELECT id
                FROM audit_tests
                WHERE category_id = ? AND workbook_row_id = ? AND source_origin = ?
                """,
                (record["category_id"], record["workbook_row_id"], record.get("source_origin", "workbook")),
            ).fetchone()
        if row is None:
            raise ValueError("Failed to upsert audit test")
        return int(row["id"])

    def get_options(self, *, industry_types: Optional[list[str]] = None) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            filtered_clause = ""
            filtered_params: list[Any] = []
            if industry_types:
                placeholders = ", ".join("?" for _ in industry_types)
                filtered_clause = f" AND COALESCE(NULLIF(TRIM(t.industry_type), ''), 'Generic') IN ({placeholders})"
                filtered_params.extend(self._normalize_industry_type(item) for item in industry_types)
            categories = conn.execute(
                f"""
                SELECT COALESCE(NULLIF(TRIM(t.category_label), ''), c.source_sheet_name) AS category_name,
                       MIN(c.source_sheet_name) AS source_sheet_name,
                       COUNT(t.id) AS test_count
                FROM audit_tests t
                INNER JOIN audit_categories c ON c.id = t.category_id
                WHERE t.is_active = 1 AND t.source_origin = 'workbook'
                {filtered_clause}
                GROUP BY COALESCE(NULLIF(TRIM(t.category_label), ''), c.source_sheet_name)
                ORDER BY category_name
                """,
                filtered_params,
            ).fetchall()
            domains = conn.execute(
                f"""
                SELECT domain, COUNT(*) AS test_count
                FROM audit_tests
                WHERE is_active = 1 AND source_origin = 'workbook' AND domain IS NOT NULL AND TRIM(domain) <> ''
                  {"AND COALESCE(NULLIF(TRIM(industry_type), ''), 'Generic') IN (" + ", ".join("?" for _ in industry_types) + ")" if industry_types else ""}
                GROUP BY domain
                ORDER BY domain
                """,
                filtered_params if industry_types else [],
            ).fetchall()
            industries = conn.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(industry_type), ''), 'Generic') AS industry_type, COUNT(*) AS test_count
                FROM audit_tests
                WHERE is_active = 1 AND source_origin = 'workbook'
                GROUP BY COALESCE(NULLIF(TRIM(industry_type), ''), 'Generic')
                ORDER BY CASE COALESCE(NULLIF(TRIM(industry_type), ''), 'Generic') WHEN 'Generic' THEN 0 ELSE 1 END,
                         COALESCE(NULLIF(TRIM(industry_type), ''), 'Generic')
                """
            ).fetchall()
            total_tests = conn.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM audit_tests t
                WHERE t.is_active = 1 AND t.source_origin = 'workbook'
                {filtered_clause}
                """,
                filtered_params,
            ).fetchone()
        category_items = [
            dict(row)
            for row in categories
            if int(row["test_count"] or 0) > 0 or str(row["category_name"]) in DEFAULT_AUDIT_CATEGORIES
        ]
        return {
            "industries": [dict(row) for row in industries],
            "categories": category_items,
            "domains": [dict(row) for row in domains],
            "has_real_domains": len(domains) > 0,
            "total_tests": int(total_tests["count"]) if total_tests else 0,
            "database_path": str(self._db_path),
        }

    def list_tests(
        self,
        *,
        industry_types: Optional[list[str]] = None,
        category_names: Optional[list[str]] = None,
        domains: Optional[list[str]] = None,
        test_ids: Optional[list[int]] = None,
        source_origins: Optional[list[str]] = None,
        include_variants: bool = True,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                t.id,
                t.workbook_row_id,
                COALESCE(NULLIF(TRIM(t.industry_type), ''), 'Generic') AS industry_type,
                COALESCE(NULLIF(TRIM(t.category_label), ''), c.source_sheet_name) AS category_name,
                c.source_sheet_name,
                t.attack_type,
                t.test_objective,
                t.canonical_question,
                t.prompt_sequence,
                t.prompt_steps_json,
                t.adversarial_prompt_sequence,
                t.adversarial_prompt_steps_json,
                t.safe_base_prompt_sequence,
                t.unsafe_base_prompt_sequence,
                t.safe_adversarial_prompt_sequence,
                t.unsafe_adversarial_prompt_sequence,
                t.supporting_documents,
                t.expected_behavior,
                t.expected_answer,
                t.original_result_guidance,
                t.domain,
                t.severity,
                t.source_origin,
                t.category_label
            FROM audit_tests t
            INNER JOIN audit_categories c ON c.id = t.category_id
            WHERE t.is_active = 1
        """
        params: list[Any] = []
        if industry_types:
            placeholders = ", ".join("?" for _ in industry_types)
            query += f" AND COALESCE(NULLIF(TRIM(t.industry_type), ''), 'Generic') IN ({placeholders})"
            params.extend(self._normalize_industry_type(item) for item in industry_types)
        if category_names:
            placeholders = ", ".join("?" for _ in category_names)
            query += (
                f" AND (COALESCE(NULLIF(TRIM(t.category_label), ''), c.source_sheet_name) IN ({placeholders}) "
                f"OR c.source_sheet_name IN ({placeholders}) OR c.name IN ({placeholders}))"
            )
            params.extend(category_names)
            params.extend(category_names)
            params.extend(category_names)
        if domains:
            placeholders = ", ".join("?" for _ in domains)
            query += f" AND t.domain IN ({placeholders})"
            params.extend(domains)
        if test_ids:
            placeholders = ", ".join("?" for _ in test_ids)
            query += f" AND t.id IN ({placeholders})"
            params.extend(test_ids)
        if source_origins is None and not test_ids:
            source_origins = ["workbook"]
        if source_origins:
            placeholders = ", ".join("?" for _ in source_origins)
            query += f" AND t.source_origin IN ({placeholders})"
            params.extend(source_origins)
        query += " ORDER BY COALESCE(NULLIF(TRIM(t.industry_type), ''), 'Generic'), c.id, t.workbook_row_id, t.id"

        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()

        tests: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["name"] = item["attack_type"]
            item["prompt_steps"] = _loads_json(item.pop("prompt_steps_json"), [])
            item["base_prompt_sequence"] = item["prompt_sequence"]
            item["base_prompt_steps"] = list(item["prompt_steps"])
            item["adversarial_prompt_steps"] = _loads_json(item.pop("adversarial_prompt_steps_json"), [])
            item["canonical_question"] = str(item.get("canonical_question") or "").strip() or None
            item["safe_base_prompt_sequence"] = str(item.get("safe_base_prompt_sequence") or item["base_prompt_sequence"] or "").strip() or item["base_prompt_sequence"]
            item["unsafe_base_prompt_sequence"] = str(item.get("unsafe_base_prompt_sequence") or "").strip() or None
            item["safe_adversarial_prompt_sequence"] = str(item.get("safe_adversarial_prompt_sequence") or item.get("adversarial_prompt_sequence") or "").strip() or None
            item["unsafe_adversarial_prompt_sequence"] = str(item.get("unsafe_adversarial_prompt_sequence") or "").strip() or None
            item["has_adversarial_prompt"] = any(
                bool(str(item.get(key) or "").strip())
                for key in ("adversarial_prompt_sequence", "safe_adversarial_prompt_sequence", "unsafe_adversarial_prompt_sequence")
            )
            item["expected_answer"] = str(item.get("expected_answer") or item.get("expected_behavior") or "").strip() or item.get("expected_behavior")
            item["supporting_documents"] = _loads_json(item.get("supporting_documents"), {})
            item["test_identifier"] = self._make_test_identifier(item["source_sheet_name"], int(item["workbook_row_id"]))
            item["test_label"] = "Base Test"
            item["variants"] = self.list_test_variants(int(item["id"])) if include_variants else []
            tests.append(item)
        return tests

    def list_test_variants(self, parent_test_id: int) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM audit_test_variants
                WHERE parent_test_id = ? AND is_active = 1
                ORDER BY created_at DESC, id DESC
                """,
                (parent_test_id,),
            ).fetchall()
        variants: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["edited_prompt_steps"] = _loads_json(item.pop("edited_prompt_steps_json"), [])
            item["test_label"] = "Variant"
            variants.append(item)
        return variants

    def create_variant(
        self,
        *,
        parent_test_id: int,
        variant_name: str,
        edited_prompt_sequence: str,
        edited_expected_behavior: Optional[str],
        created_by: Optional[str],
    ) -> dict[str, Any]:
        now = _utc_now()
        prompt_steps = self._parse_prompt_steps(edited_prompt_sequence)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO audit_test_variants (
                    parent_test_id,
                    variant_name,
                    edited_prompt_sequence,
                    edited_prompt_steps_json,
                    edited_expected_behavior,
                    created_by,
                    created_at,
                    updated_at,
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    parent_test_id,
                    variant_name.strip(),
                    edited_prompt_sequence.strip(),
                    _dumps_json(prompt_steps),
                    edited_expected_behavior.strip() if edited_expected_behavior else None,
                    created_by.strip() if created_by else None,
                    now,
                    now,
                ),
            )
            variant_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        return self.get_variant(variant_id)

    def get_variant(self, variant_id: int) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM audit_test_variants WHERE id = ?", (variant_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown audit test variant '{variant_id}'")
        item = dict(row)
        item["edited_prompt_steps"] = _loads_json(item.pop("edited_prompt_steps_json"), [])
        item["test_label"] = "Variant"
        return item

    def create_run(
        self,
        *,
        industry_types: list[str],
        category_names: list[str],
        target_info: dict[str, Any],
        execution_items: list[dict[str, Any]],
        execution_profile: Optional[dict[str, Any]] = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        now = _utc_now()
        selected_test_ids = [int(item["test_id"]) for item in execution_items if item.get("variant_id") is None]
        selected_variant_ids = [int(item["variant_id"]) for item in execution_items if item.get("variant_id") is not None]
        profile = self._normalize_execution_profile(execution_profile, target_info=target_info)
        run_count = int(profile["run_count_requested"])

        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO audit_runs (
                    id,
                    target_id,
                    target_registry_name,
                    target_type,
                    model_name,
                    endpoint,
                    supports_multi_turn,
                    status,
                    selected_industries,
                    selected_categories,
                    selected_test_ids,
                    selected_variant_ids,
                    total_tests,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    target_info["target_registry_name"],
                    target_info["target_registry_name"],
                    target_info["target_type"],
                    target_info.get("model_name"),
                    target_info.get("endpoint"),
                    1 if target_info.get("supports_multi_turn", True) else 0,
                    "pending",
                    _dumps_json([self._normalize_industry_type(item) for item in industry_types]),
                    _dumps_json(category_names),
                    _dumps_json(selected_test_ids),
                    _dumps_json(selected_variant_ids),
                    len(execution_items) * run_count,
                    now,
                    now,
                ),
            )
            profile_id = self._insert_execution_profile(conn, run_id=run_id, target_info=target_info, profile=profile, now=now)

            for display_order, item in enumerate(execution_items, start=1):
                group_id = self._insert_result_group(
                    conn,
                    run_id=run_id,
                    profile_id=profile_id,
                    item=item,
                    run_count=run_count,
                    now=now,
                )
                for run_no in range(1, run_count + 1):
                    physical_run_id = self._insert_physical_run(
                        conn,
                        group_id=group_id,
                        run_no=run_no,
                        item=item,
                        profile=profile,
                        now=now,
                    )
                    conn.execute(
                        """
                        INSERT INTO audit_results (
                            run_id,
                            test_id,
                            variant_id,
                            display_order,
                            result_label,
                            variant_name,
                            prompt_source_type,
                            prompt_source_label,
                            prompt_variant,
                            transient_prompt_used,
                            execution_scope_label,
                            variant_group_key,
                            editor_snapshot,
                            industry_type,
                            category_name,
                            domain,
                            severity,
                            test_identifier,
                            workbook_row_id,
                            attack_type,
                            test_objective,
                            original_workbook_prompt,
                            actual_prompt_sequence,
                            actual_prompt_steps_json,
                            supporting_documents_snapshot,
                            expected_behavior_snapshot,
                            original_result_guidance_snapshot,
                            execution_status,
                            created_at,
                            stability_group_id,
                            stability_run_id,
                            stability_run_no
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            item["test_id"],
                            item.get("variant_id"),
                            ((display_order - 1) * run_count) + run_no,
                            item["result_label"],
                            item.get("variant_name"),
                            item.get("prompt_source_type"),
                            item.get("prompt_source_label"),
                            item.get("prompt_variant"),
                            1 if item.get("transient_prompt_used") else 0,
                            item.get("execution_scope_label"),
                            item.get("variant_group_key"),
                            item.get("editor_snapshot"),
                            item.get("industry_type", "Generic"),
                            item["category_name"],
                            item.get("domain"),
                            item["severity"],
                            item["test_identifier"],
                            item["workbook_row_id"],
                            item["attack_type"],
                            item["test_objective"],
                            item["original_workbook_prompt"],
                            item["actual_prompt_sequence"],
                            _dumps_json(item["actual_prompt_steps"]),
                            _dumps_json(item.get("supporting_documents") or {}),
                            item["expected_behavior_snapshot"],
                            item.get("original_result_guidance_snapshot"),
                            "pending",
                            now,
                            group_id,
                            physical_run_id,
                            run_no,
                        ),
                    )

        return run_id

    def _normalize_execution_profile(self, profile: Optional[dict[str, Any]], *, target_info: dict[str, Any]) -> dict[str, Any]:
        merged = {**DEFAULT_EXECUTION_PROFILE, **(profile or {})}
        mode = str(merged.get("mode_code") or "COMPLIANCE").upper()
        if mode not in {"COMPLIANCE", "ROBUSTNESS", "ADVANCED"}:
            mode = "COMPLIANCE"

        if mode == "COMPLIANCE" and not profile:
            merged.update(
                {
                    "temperature": 0.0,
                    "fixed_seed": True,
                    "seed_strategy": "FIXED",
                    "top_p": 1.0,
                    "run_count_requested": 1,
                    "variability_mode": False,
                }
            )
        elif mode == "ROBUSTNESS":
            merged.setdefault("temperature", 0.7)
            merged["temperature"] = 0.7 if merged.get("temperature") is None else merged["temperature"]
            merged["fixed_seed"] = False if merged.get("fixed_seed") is None else bool(merged.get("fixed_seed"))
            merged["seed_strategy"] = merged.get("seed_strategy") or "PER_RUN_RANDOM"
            merged["run_count_requested"] = int(merged.get("run_count_requested") or 5)
            merged["variability_mode"] = True

        base_seed = merged.get("base_seed")
        if base_seed in (None, ""):
            base_seed = self._stable_seed(f"{target_info.get('target_registry_name')}::{mode}")
        merged["base_seed"] = int(base_seed)
        merged["mode_code"] = mode
        merged["run_count_requested"] = max(1, min(int(merged.get("run_count_requested") or 1), 25))
        merged["top_p"] = 1.0 if merged.get("top_p") in (None, "") else float(merged["top_p"])
        merged["temperature"] = None if merged.get("temperature") in (None, "") else float(merged["temperature"])
        merged["top_k"] = None if merged.get("top_k") in (None, "") else int(merged["top_k"])
        merged["max_tokens"] = None if merged.get("max_tokens") in (None, "") else int(merged["max_tokens"])
        merged["fixed_seed"] = bool(merged.get("fixed_seed"))
        merged["variability_mode"] = bool(merged.get("variability_mode"))
        merged["seed_strategy"] = str(merged.get("seed_strategy") or ("FIXED" if merged["fixed_seed"] else "PER_RUN_RANDOM")).upper()
        return merged

    def _insert_execution_profile(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        target_info: dict[str, Any],
        profile: dict[str, Any],
        now: str,
    ) -> int:
        conn.execute(
            """
            INSERT INTO audit_execution_profile (
                audit_session_id,
                mode_code,
                model_target_type,
                model_target_name,
                provider_name,
                api_style,
                temperature,
                top_p,
                top_k,
                fixed_seed,
                base_seed,
                seed_strategy,
                max_tokens,
                run_count_requested,
                variability_mode,
                created_at,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                profile["mode_code"],
                target_info.get("target_type"),
                target_info.get("model_name") or target_info.get("target_registry_name"),
                profile.get("provider_name") or self._infer_provider_name(target_info),
                profile.get("api_style") or self._infer_api_style(target_info),
                profile.get("temperature"),
                profile.get("top_p"),
                profile.get("top_k"),
                1 if profile.get("fixed_seed") else 0,
                profile.get("base_seed"),
                profile.get("seed_strategy"),
                profile.get("max_tokens"),
                profile.get("run_count_requested"),
                1 if profile.get("variability_mode") else 0,
                now,
                profile.get("created_by"),
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

    def _insert_result_group(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        profile_id: int,
        item: dict[str, Any],
        run_count: int,
        now: str,
    ) -> int:
        conn.execute(
            """
            INSERT INTO audit_test_case_result_group (
                audit_session_id,
                execution_profile_id,
                prompt_source_type,
                prompt_source_ref,
                benchmark_scenario_id,
                industry_type,
                category_code,
                category_name,
                subcategory_name,
                prompt_variant,
                severity_expected,
                expected_behavior_text,
                objective_text,
                run_count_actual,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                profile_id,
                self._prompt_source_type_for_item(item),
                item.get("prompt_source_ref") or item["test_identifier"],
                item.get("benchmark_scenario_id"),
                item.get("industry_type", "Generic"),
                item["category_name"],
                item["category_name"],
                item["attack_type"],
                item.get("prompt_variant", "Base"),
                item["severity"],
                item["expected_behavior_snapshot"],
                item["test_objective"],
                run_count,
                now,
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

    @staticmethod
    def _prompt_source_type_for_item(item: dict[str, Any]) -> str:
        if item.get("prompt_source_type"):
            return str(item["prompt_source_type"])
        if item.get("benchmark_scenario_id") or item.get("result_label") == "Benchmark Scenario":
            return "benchmark"
        if item.get("result_label") == "Adversarial Prompt":
            return "adversarial"
        if item.get("variant_id") or item.get("result_label") == "Variant":
            return "variant"
        return "base"

    @staticmethod
    def _prompt_source_label_for_item(item: dict[str, Any]) -> str:
        if item.get("prompt_source_label"):
            return str(item["prompt_source_label"])
        prompt_source_type = AuditDatabase._prompt_source_type_for_item(item)
        if prompt_source_type == "adversarial":
            return "Adversarial Prompt"
        if prompt_source_type == "variant":
            return f"Variant: {item.get('variant_name') or 'Saved Variant'}"
        if prompt_source_type == "transient_edit":
            return "Unsaved Edit"
        if prompt_source_type == "interactive":
            return "Interactive Audit"
        if prompt_source_type == "benchmark":
            return "Benchmark Scenario"
        return "Workbook Base"

    @staticmethod
    def _execution_scope_label_for_item(item: dict[str, Any]) -> str:
        if item.get("execution_scope_label"):
            return str(item["execution_scope_label"])
        return AuditDatabase._prompt_source_label_for_item(item)

    @staticmethod
    def _variant_group_key_for_item(item: dict[str, Any]) -> str:
        if item.get("variant_group_key"):
            return str(item["variant_group_key"])
        prompt_source_type = AuditDatabase._prompt_source_type_for_item(item)
        if prompt_source_type == "adversarial":
            return f"test-{item['test_id']}:adversarial"
        if prompt_source_type == "variant":
            return f"test-{item['test_id']}:variant-{item.get('variant_id')}"
        if prompt_source_type == "transient_edit":
            return f"test-{item['test_id']}:transient-edit"
        if prompt_source_type == "interactive":
            return f"test-{item['test_id']}:interactive"
        if prompt_source_type == "benchmark":
            return f"test-{item['test_id']}:benchmark-{item.get('benchmark_scenario_id') or 'scenario'}"
        return f"test-{item['test_id']}:base"

    def _insert_physical_run(
        self,
        conn: sqlite3.Connection,
        *,
        group_id: int,
        run_no: int,
        item: dict[str, Any],
        profile: dict[str, Any],
        now: str,
    ) -> int:
        seed_used = self._seed_for_run(profile, run_no)
        conn.execute(
            """
            INSERT INTO audit_test_case_run (
                result_group_id,
                run_no,
                seed_used,
                temperature_used,
                top_p_used,
                top_k_used,
                prompt_text,
                normalized_prompt_text,
                run_status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (
                group_id,
                run_no,
                seed_used,
                profile.get("temperature"),
                profile.get("top_p"),
                profile.get("top_k"),
                item["actual_prompt_sequence"],
                self._normalize_text(item["actual_prompt_sequence"]),
                now,
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

    @staticmethod
    def _seed_for_run(profile: dict[str, Any], run_no: int) -> Optional[int]:
        base_seed = profile.get("base_seed")
        if base_seed is None:
            return None
        strategy = str(profile.get("seed_strategy") or "FIXED").upper()
        if strategy == "SEQUENTIAL":
            return int(base_seed) + run_no - 1
        if strategy == "PER_RUN_RANDOM":
            return AuditDatabase._stable_seed(f"{base_seed}:{run_no}:{uuid.uuid4()}")
        return int(base_seed)

    @staticmethod
    def _stable_seed(value: str) -> int:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return int(digest[:12], 16) % 2_147_483_647

    @staticmethod
    def _infer_provider_name(target_info: dict[str, Any]) -> str:
        endpoint = str(target_info.get("endpoint") or "").lower()
        target_type = str(target_info.get("target_type") or "")
        if "azure" in endpoint:
            return "Azure"
        if "ollama" in endpoint or "11434" in endpoint:
            return "Ollama"
        if "anthropic" in endpoint or "claude" in endpoint:
            return "Claude"
        if "gemini" in endpoint or "google" in endpoint:
            return "Gemini"
        if "openai" in endpoint or "OpenAI" in target_type:
            return "OpenAI"
        return "Custom"

    @staticmethod
    def _infer_api_style(target_info: dict[str, Any]) -> str:
        target_type = str(target_info.get("target_type") or "").lower()
        if "image" in target_type:
            return "image"
        if "video" in target_type:
            return "video"
        if "tts" in target_type:
            return "tts"
        if "completion" in target_type:
            return "completion"
        if "response" in target_type:
            return "response"
        if "browser" in target_type:
            return "browser"
        if "http" in target_type:
            return "http"
        return "chat"

    @staticmethod
    def _normalize_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return re.sub(r"\s+", " ", value).strip().lower()

    @staticmethod
    def _normalize_industry_type(value: Optional[str]) -> str:
        cleaned = str(value or "").strip()
        return cleaned or "Generic"

    def resolve_execution_items(
        self,
        *,
        industry_types: Optional[list[str]] = None,
        category_names: Optional[list[str]] = None,
        domains: Optional[list[str]] = None,
        test_ids: Optional[list[int]] = None,
        variant_ids: Optional[list[int]] = None,
        prompt_source_mode: Optional[str] = None,
        transient_prompt_sequence: Optional[str] = None,
        transient_expected_behavior: Optional[str] = None,
        selected_test_id_for_transient_run: Optional[int] = None,
        target_prompt_profile: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        execution_items: list[dict[str, Any]] = []
        normalized_mode = (prompt_source_mode or "").strip().lower() or None

        base_tests: list[dict[str, Any]] = []
        if normalized_mode != "current_edit":
            base_tests = self.list_tests(
                industry_types=industry_types,
                category_names=category_names,
                domains=domains,
                test_ids=test_ids,
                source_origins=None if test_ids else ["workbook"],
                include_variants=normalized_mode == "all_variants",
            )

        if normalized_mode == "current_edit":
            if selected_test_id_for_transient_run is None:
                return []
            transient_item = self._build_transient_execution_item(
                test_id=int(selected_test_id_for_transient_run),
                transient_prompt_sequence=transient_prompt_sequence,
                transient_expected_behavior=transient_expected_behavior,
            )
            execution_items = [transient_item] if transient_item else []
        elif normalized_mode == "selected_variant":
            execution_items = self._build_variant_execution_items(
                variant_ids=variant_ids or [],
                execution_scope_label="Selected Saved Variant",
            )
        elif normalized_mode == "adversarial":
            execution_items = self._build_adversarial_execution_items(
                base_tests,
                execution_scope_label="Adversarial Prompt",
                target_prompt_profile=target_prompt_profile,
            )
        elif normalized_mode == "both":
            execution_items = [
                *self._build_base_execution_items(
                    base_tests,
                    execution_scope_label="Base + Adversarial",
                    target_prompt_profile=target_prompt_profile,
                ),
                *self._build_adversarial_execution_items(
                    base_tests,
                    execution_scope_label="Base + Adversarial",
                    target_prompt_profile=target_prompt_profile,
                ),
            ]
        elif normalized_mode == "base_and_variant":
            execution_items = [
                *self._build_base_execution_items(base_tests, execution_scope_label="Base + Selected Variant"),
                *self._build_variant_execution_items(
                    variant_ids=variant_ids or [],
                    execution_scope_label="Base + Selected Variant",
                ),
            ]
        elif normalized_mode == "all_variants":
            expanded_variant_ids = self._expand_active_variant_ids_for_tests(base_tests)
            execution_items = self._build_variant_execution_items(
                variant_ids=expanded_variant_ids,
                execution_scope_label="All Active Variants",
            )
        elif normalized_mode == "base":
            execution_items = self._build_base_execution_items(
                base_tests,
                execution_scope_label="Workbook Base",
                target_prompt_profile=target_prompt_profile,
            )
        else:
            include_base_tests = bool(category_names or domains or test_ids) or not (variant_ids or [])
            if include_base_tests:
                execution_items.extend(
                    self._build_base_execution_items(
                        base_tests,
                        execution_scope_label="Workbook Base",
                        target_prompt_profile=target_prompt_profile,
                    )
                )
            execution_items.extend(
                self._build_variant_execution_items(
                    variant_ids=variant_ids or [],
                    execution_scope_label="Selected Saved Variant",
                )
            )

        execution_items.sort(
            key=lambda item: (
                item["category_name"],
                item["workbook_row_id"],
                0 if item.get("prompt_variant") == "Base" else 1,
                item["result_label"],
                item.get("variant_name") or "",
            )
        )
        return execution_items

    def _build_base_execution_items(
        self,
        tests: list[dict[str, Any]],
        *,
        execution_scope_label: str,
        target_prompt_profile: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        execution_items: list[dict[str, Any]] = []
        for test in tests:
            actual_prompt_sequence = self._select_prompt_sequence(
                test=test,
                variant="base",
                target_prompt_profile=target_prompt_profile,
            )
            if not actual_prompt_sequence:
                continue
            execution_items.append(
                {
                    "test_id": int(test["id"]),
                    "variant_id": None,
                    "result_label": "Base Test",
                    "variant_name": None,
                    "prompt_source_type": "base",
                    "prompt_source_label": "Base Prompt",
                    "prompt_variant": "Base",
                    "prompt_source_ref": test["test_identifier"],
                    "transient_prompt_used": False,
                    "execution_scope_label": execution_scope_label,
                    "variant_group_key": f"test-{int(test['id'])}:base",
                    "editor_snapshot": None,
                    "industry_type": self._normalize_industry_type(test.get("industry_type")),
                    "category_name": test["category_name"],
                    "domain": test.get("domain"),
                    "severity": test["severity"],
                    "test_identifier": test["test_identifier"],
                    "workbook_row_id": int(test["workbook_row_id"]),
                    "attack_type": test["attack_type"],
                    "test_objective": test["test_objective"],
                    "original_workbook_prompt": actual_prompt_sequence,
                    "actual_prompt_sequence": actual_prompt_sequence,
                    "actual_prompt_steps": self._parse_prompt_steps(actual_prompt_sequence),
                    "supporting_documents": test.get("supporting_documents") or {},
                    "expected_behavior_snapshot": test["expected_behavior"],
                    "original_result_guidance_snapshot": test.get("original_result_guidance"),
                }
            )
        return execution_items

    def _build_adversarial_execution_items(
        self,
        tests: list[dict[str, Any]],
        *,
        execution_scope_label: str,
        target_prompt_profile: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        execution_items: list[dict[str, Any]] = []
        for test in tests:
            adversarial_prompt = self._select_prompt_sequence(
                test=test,
                variant="adversarial",
                target_prompt_profile=target_prompt_profile,
            )
            if not adversarial_prompt:
                continue
            execution_items.append(
                {
                    "test_id": int(test["id"]),
                    "variant_id": None,
                    "result_label": "Adversarial Prompt",
                    "variant_name": None,
                    "prompt_source_type": "adversarial",
                    "prompt_source_label": "Adversarial Prompt",
                    "prompt_variant": "Adversarial",
                    "prompt_source_ref": test["test_identifier"],
                    "transient_prompt_used": False,
                    "execution_scope_label": execution_scope_label,
                    "variant_group_key": f"test-{int(test['id'])}:adversarial",
                    "editor_snapshot": None,
                    "industry_type": self._normalize_industry_type(test.get("industry_type")),
                    "category_name": test["category_name"],
                    "domain": test.get("domain"),
                    "severity": test["severity"],
                    "test_identifier": test["test_identifier"],
                    "workbook_row_id": int(test["workbook_row_id"]),
                    "attack_type": test["attack_type"],
                    "test_objective": test["test_objective"],
                    "original_workbook_prompt": adversarial_prompt,
                    "actual_prompt_sequence": adversarial_prompt,
                    "actual_prompt_steps": self._parse_prompt_steps(adversarial_prompt),
                    "supporting_documents": test.get("supporting_documents") or {},
                    "expected_behavior_snapshot": test["expected_behavior"],
                    "original_result_guidance_snapshot": test.get("original_result_guidance"),
                }
            )
        return execution_items

    def _select_prompt_sequence(
        self,
        *,
        test: dict[str, Any],
        variant: str,
        target_prompt_profile: Optional[str],
    ) -> str:
        profile = (target_prompt_profile or "").strip().lower()
        if variant == "adversarial":
            candidates = {
                "safe": test.get("safe_adversarial_prompt_sequence") or test.get("adversarial_prompt_sequence"),
                "unsafe": test.get("unsafe_adversarial_prompt_sequence") or test.get("adversarial_prompt_sequence"),
                "default": test.get("adversarial_prompt_sequence") or test.get("safe_adversarial_prompt_sequence") or test.get("unsafe_adversarial_prompt_sequence"),
            }
        else:
            candidates = {
                "safe": test.get("safe_base_prompt_sequence") or test.get("base_prompt_sequence") or test.get("prompt_sequence"),
                "unsafe": test.get("unsafe_base_prompt_sequence") or test.get("base_prompt_sequence") or test.get("prompt_sequence"),
                "default": test.get("base_prompt_sequence") or test.get("prompt_sequence") or test.get("safe_base_prompt_sequence") or test.get("unsafe_base_prompt_sequence"),
            }

        preferred = candidates.get(profile) if profile in {"safe", "unsafe"} else candidates.get("default")
        return str(preferred or "").strip()

    def _build_variant_execution_items(
        self,
        *,
        variant_ids: list[int],
        execution_scope_label: str,
    ) -> list[dict[str, Any]]:
        execution_items: list[dict[str, Any]] = []
        for variant_id in variant_ids:
            variant = self.get_variant(int(variant_id))
            parent_test = self.list_tests(test_ids=[int(variant["parent_test_id"])], source_origins=None, include_variants=False)
            if not parent_test:
                continue
            test = parent_test[0]
            execution_items.append(
                {
                    "test_id": int(test["id"]),
                    "variant_id": int(variant["id"]),
                    "result_label": "Variant",
                    "variant_name": variant["variant_name"],
                    "prompt_source_type": "variant",
                    "prompt_source_label": f"Variant: {variant['variant_name']}",
                    "prompt_variant": "Base",
                    "prompt_source_ref": f"variant:{variant['id']}",
                    "transient_prompt_used": False,
                    "execution_scope_label": execution_scope_label,
                    "variant_group_key": f"test-{int(test['id'])}:variant-{int(variant['id'])}",
                    "editor_snapshot": None,
                    "industry_type": self._normalize_industry_type(test.get("industry_type")),
                    "category_name": test["category_name"],
                    "domain": test.get("domain"),
                    "severity": test["severity"],
                    "test_identifier": test["test_identifier"],
                    "workbook_row_id": int(test["workbook_row_id"]),
                    "attack_type": test["attack_type"],
                    "test_objective": test["test_objective"],
                    "original_workbook_prompt": test["prompt_sequence"],
                    "actual_prompt_sequence": variant["edited_prompt_sequence"],
                    "actual_prompt_steps": variant["edited_prompt_steps"],
                    "supporting_documents": test.get("supporting_documents") or {},
                    "expected_behavior_snapshot": variant.get("edited_expected_behavior") or test["expected_behavior"],
                    "original_result_guidance_snapshot": test.get("original_result_guidance"),
                }
            )
        return execution_items

    def _build_transient_execution_item(
        self,
        *,
        test_id: int,
        transient_prompt_sequence: Optional[str],
        transient_expected_behavior: Optional[str],
    ) -> Optional[dict[str, Any]]:
        tests = self.list_tests(test_ids=[test_id], source_origins=None, include_variants=False)
        if not tests:
            return None
        test = tests[0]
        prompt_sequence = str(transient_prompt_sequence or "").strip()
        if not prompt_sequence:
            return None
        expected_behavior = str(transient_expected_behavior or "").strip() or test["expected_behavior"]
        return {
            "test_id": int(test["id"]),
            "variant_id": None,
            "result_label": "Unsaved Edit",
            "variant_name": None,
            "prompt_source_type": "transient_edit",
            "prompt_source_label": "Unsaved Edit",
            "prompt_variant": "Base",
            "prompt_source_ref": test["test_identifier"],
            "transient_prompt_used": True,
            "execution_scope_label": "Current Edited Prompt",
            "variant_group_key": f"test-{int(test['id'])}:transient-edit",
            "editor_snapshot": prompt_sequence,
            "industry_type": self._normalize_industry_type(test.get("industry_type")),
            "category_name": test["category_name"],
            "domain": test.get("domain"),
            "severity": test["severity"],
            "test_identifier": test["test_identifier"],
            "workbook_row_id": int(test["workbook_row_id"]),
            "attack_type": test["attack_type"],
            "test_objective": test["test_objective"],
            "original_workbook_prompt": test["prompt_sequence"],
            "actual_prompt_sequence": prompt_sequence,
            "actual_prompt_steps": self._parse_prompt_steps(prompt_sequence),
            "supporting_documents": test.get("supporting_documents") or {},
            "expected_behavior_snapshot": expected_behavior,
            "original_result_guidance_snapshot": test.get("original_result_guidance"),
        }

    @staticmethod
    def _expand_active_variant_ids_for_tests(tests: list[dict[str, Any]]) -> list[int]:
        variant_ids: list[int] = []
        for test in tests:
            for variant in test.get("variants", []):
                if variant.get("is_active", True):
                    variant_ids.append(int(variant["id"]))
        return variant_ids

    def mark_run_running(self, run_id: str) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE audit_runs
                SET status = 'running',
                    started_at = COALESCE(started_at, ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (now, now, run_id),
            )

    def mark_result_running(self, result_id: int) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE audit_results
                SET execution_status = 'running',
                    started_at = COALESCE(started_at, ?)
                WHERE id = ?
                """,
                (now, result_id),
            )
            row = conn.execute("SELECT stability_run_id FROM audit_results WHERE id = ?", (result_id,)).fetchone()
            if row and row["stability_run_id"]:
                conn.execute(
                    """
                    UPDATE audit_test_case_run
                    SET run_status = 'RUNNING'
                    WHERE id = ?
                    """,
                    (int(row["stability_run_id"]),),
                )

    def complete_result(
        self,
        *,
        run_id: str,
        result_id: int,
        evaluation: dict[str, Any],
        prompt_sent: str,
        response_text: str,
        interaction_log: list[dict[str, Any]],
        attack_result_id: str,
        conversation_id: str,
    ) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            result_row = conn.execute(
                "SELECT stability_run_id FROM audit_results WHERE id = ?",
                (result_id,),
            ).fetchone()
            prompt_attack_json = _dumps_json(evaluation.get("prompt_attack_assessment") or {})
            response_behavior_json = _dumps_json(evaluation.get("response_behavior_assessment") or {})
            refusal_strength_json = _dumps_json(evaluation.get("refusal_strength_assessment") or {})
            scenario_verdict_json = _dumps_json(evaluation.get("scenario_verdict_assessment") or {})
            matched_rules_json = _dumps_json(evaluation.get("matched_rules") or [])
            detected_entities_json = _dumps_json(evaluation.get("detected_entities") or [])
            evidence_spans_json = _dumps_json(evaluation.get("evidence_spans") or [])
            context_references_json = _dumps_json(evaluation.get("context_references") or {})
            conn.execute(
                """
                UPDATE audit_results
                SET execution_status = 'completed',
                    prompt_sent = ?,
                    response_received = ?,
                    score_status = ?,
                    risk_level = ?,
                    score_value = ?,
                    score_reason = ?,
                    audit_reasoning = ?,
                    attack_detected = ?,
                    attack_family = ?,
                    attack_subtype = ?,
                    attack_severity_potential = ?,
                    policy_domain = ?,
                    expected_behavior_profile = ?,
                    response_behavior_class = ?,
                    response_safety_label = ?,
                    response_safety_risk = ?,
                    attack_outcome = ?,
                    refusal_strength = ?,
                    refusal_style = ?,
                    boundary_clarity = ?,
                    safe_alternative_quality = ?,
                    scoring_version = ?,
                    prompt_attack_assessment = ?,
                    response_behavior_assessment = ?,
                    refusal_strength_assessment = ?,
                    scenario_verdict_assessment = ?,
                    attack_intent = ?,
                    outcome_safety = ?,
                    refusal_quality = ?,
                    matched_rules = ?,
                    detected_entities = ?,
                    evidence_spans = ?,
                    context_references = ?,
                    policy_pack = ?,
                    confidence = ?,
                    interaction_log = ?,
                    attack_result_id = ?,
                    conversation_id = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    prompt_sent,
                    response_text,
                    evaluation["status"],
                    evaluation["risk"],
                    evaluation["score"],
                    evaluation["reason"],
                    evaluation.get("audit_reasoning") or evaluation["reason"],
                    1 if evaluation.get("attack_detected") else 0,
                    evaluation.get("attack_family"),
                    evaluation.get("attack_subtype"),
                    evaluation.get("attack_severity_potential"),
                    evaluation.get("policy_domain"),
                    evaluation.get("expected_behavior_profile"),
                    evaluation.get("response_behavior_class"),
                    evaluation.get("response_safety_label"),
                    evaluation.get("response_safety_risk"),
                    evaluation.get("attack_outcome"),
                    evaluation.get("refusal_strength"),
                    evaluation.get("refusal_style"),
                    evaluation.get("boundary_clarity"),
                    evaluation.get("safe_alternative_quality"),
                    evaluation.get("scoring_version"),
                    prompt_attack_json,
                    response_behavior_json,
                    refusal_strength_json,
                    scenario_verdict_json,
                    evaluation.get("attack_intent"),
                    evaluation.get("outcome_safety"),
                    evaluation.get("refusal_quality"),
                    matched_rules_json,
                    detected_entities_json,
                    evidence_spans_json,
                    context_references_json,
                    evaluation.get("policy_pack"),
                    evaluation.get("confidence"),
                    _dumps_json(interaction_log),
                    attack_result_id,
                    conversation_id,
                    now,
                    result_id,
                ),
            )
            if result_row and result_row["stability_run_id"]:
                conn.execute(
                    """
                    UPDATE audit_test_case_run
                    SET raw_response_text = ?,
                        normalized_response_text = ?,
                        evaluator_safety_label = ?,
                        evaluator_safety_risk = ?,
                        evaluator_compliance_label = ?,
                        attack_family = ?,
                        attack_subtype = ?,
                        attack_severity_potential = ?,
                        policy_domain = ?,
                        expected_behavior_profile = ?,
                        response_behavior_class = ?,
                        attack_outcome = ?,
                        refusal_strength = ?,
                        refusal_style = ?,
                        boundary_clarity = ?,
                        safe_alternative_quality = ?,
                        evaluator_reasoning = ?,
                        scoring_version = ?,
                        prompt_attack_assessment = ?,
                        response_behavior_assessment = ?,
                        refusal_strength_assessment = ?,
                        scenario_verdict_assessment = ?,
                        attack_intent = ?,
                        outcome_safety = ?,
                        refusal_quality = ?,
                        matched_rules = ?,
                        detected_entities = ?,
                        evidence_spans = ?,
                        context_references = ?,
                        policy_pack = ?,
                        confidence = ?,
                        run_status = 'COMPLETED'
                    WHERE id = ?
                    """,
                    (
                        response_text,
                        self._normalize_text(response_text),
                        str(evaluation.get("response_safety_label") or infer_safety_label(evaluation["status"], evaluation["risk"])).upper(),
                        str(evaluation.get("response_safety_risk") or evaluation["risk"]).upper(),
                        str(evaluation["status"]).upper(),
                        evaluation.get("attack_family"),
                        evaluation.get("attack_subtype"),
                        evaluation.get("attack_severity_potential"),
                        evaluation.get("policy_domain"),
                        evaluation.get("expected_behavior_profile"),
                        evaluation.get("response_behavior_class"),
                        evaluation.get("attack_outcome"),
                        str(evaluation.get("refusal_strength") or infer_refusal_strength(response_text, evaluation.get("audit_reasoning") or evaluation["reason"])).upper(),
                        evaluation.get("refusal_style"),
                        evaluation.get("boundary_clarity"),
                        evaluation.get("safe_alternative_quality"),
                        evaluation.get("audit_reasoning") or evaluation["reason"],
                        evaluation.get("scoring_version"),
                        prompt_attack_json,
                        response_behavior_json,
                        refusal_strength_json,
                        scenario_verdict_json,
                        evaluation.get("attack_intent"),
                        evaluation.get("outcome_safety"),
                        evaluation.get("refusal_quality"),
                        matched_rules_json,
                        detected_entities_json,
                        evidence_spans_json,
                        context_references_json,
                        evaluation.get("policy_pack"),
                        evaluation.get("confidence"),
                        int(result_row["stability_run_id"]),
                    ),
                )
            self._recalculate_run_summary(conn, run_id)

    def fail_result(self, *, run_id: str, result_id: int, reason: str) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            result_row = conn.execute(
                "SELECT stability_run_id FROM audit_results WHERE id = ?",
                (result_id,),
            ).fetchone()
            conn.execute(
                """
                UPDATE audit_results
                SET execution_status = 'error',
                    score_status = 'ERROR',
                    risk_level = 'HIGH',
                    score_value = 0,
                    score_reason = ?,
                    audit_reasoning = ?,
                    response_safety_label = 'WARN',
                    response_safety_risk = 'MEDIUM',
                    attack_outcome = 'NEEDS_REVIEW',
                    refusal_strength = 'NOT_APPLICABLE',
                    scoring_version = COALESCE(scoring_version, 'v2'),
                    completed_at = ?
                WHERE id = ?
                """,
                (reason, reason, now, result_id),
            )
            if result_row and result_row["stability_run_id"]:
                conn.execute(
                    """
                    UPDATE audit_test_case_run
                    SET evaluator_safety_label = 'VIOLATION',
                        evaluator_safety_risk = 'HIGH',
                        evaluator_compliance_label = 'FAIL',
                        attack_outcome = 'NEEDS_REVIEW',
                        refusal_strength = 'NONE',
                        evaluator_reasoning = ?,
                        scoring_version = COALESCE(scoring_version, 'v2'),
                        run_status = 'FAILED'
                    WHERE id = ?
                    """,
                    (reason, int(result_row["stability_run_id"])),
                )
            self._recalculate_run_summary(conn, run_id)

    def invalidate_result(self, *, run_id: str, result_id: int, reason: str) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            result_row = conn.execute(
                "SELECT stability_run_id FROM audit_results WHERE id = ?",
                (result_id,),
            ).fetchone()
            conn.execute(
                """
                UPDATE audit_results
                SET execution_status = 'error',
                    score_status = 'INVALID_TEST_INPUT',
                    risk_level = NULL,
                    score_value = NULL,
                    score_reason = ?,
                    audit_reasoning = ?,
                    response_safety_label = NULL,
                    response_safety_risk = NULL,
                    attack_outcome = NULL,
                    refusal_strength = NULL,
                    scoring_version = COALESCE(scoring_version, 'v2'),
                    completed_at = ?
                WHERE id = ?
                """,
                (reason, reason, now, result_id),
            )
            if result_row and result_row["stability_run_id"]:
                conn.execute(
                    """
                    UPDATE audit_test_case_run
                    SET evaluator_safety_label = NULL,
                        evaluator_safety_risk = NULL,
                        evaluator_compliance_label = 'INVALID_TEST_INPUT',
                        attack_outcome = NULL,
                        refusal_strength = NULL,
                        evaluator_reasoning = ?,
                        scoring_version = COALESCE(scoring_version, 'v2'),
                        run_status = 'SKIPPED'
                    WHERE id = ?
                    """,
                    (reason, int(result_row["stability_run_id"])),
                )
            self._recalculate_run_summary(conn, run_id)

    def finalize_run(self, run_id: str) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            self._recalculate_run_summary(conn, run_id)
            self._recalculate_stability_groups(conn, run_id)
            conn.execute(
                """
                UPDATE audit_runs
                SET status = 'completed',
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, now, run_id),
            )

    def fail_run(self, run_id: str, error_message: str) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            self._recalculate_run_summary(conn, run_id)
            self._recalculate_stability_groups(conn, run_id)
            conn.execute(
                """
                UPDATE audit_runs
                SET status = 'failed',
                    error_message = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (error_message, now, now, run_id),
            )

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM audit_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return self._deserialize_run(dict(row))

    def get_run_results(self, run_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM audit_results WHERE run_id = ? ORDER BY display_order, id",
                (run_id,),
            ).fetchall()
        return [self._deserialize_result_row(dict(row)) for row in rows]

    def get_run_detail(self, run_id: str) -> Optional[dict[str, Any]]:
        run = self.get_run(run_id)
        if run is None:
            return None
        run["results"] = self.get_run_results(run_id)
        return run

    def get_recent_runs(self, limit: int = 10, *, completed_only: bool = False) -> list[dict[str, Any]]:
        where_clause = "WHERE status = 'completed'" if completed_only else ""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM audit_runs
                """
                + where_clause
                + """
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._deserialize_run(dict(row)) for row in rows]

    def get_recent_interactive_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM audit_runs AS run
                WHERE EXISTS (
                    SELECT 1
                    FROM audit_results AS result
                    WHERE result.run_id = run.id
                      AND result.prompt_source_type = 'interactive'
                )
                ORDER BY COALESCE(run.completed_at, run.updated_at, run.created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._deserialize_run(dict(row)) for row in rows]

    def get_dashboard_heatmap(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            category_rows = conn.execute(
                """
                SELECT source_sheet_name
                FROM audit_categories
                ORDER BY id
                """
            ).fetchall()
            count_rows = conn.execute(
                """
                SELECT
                    category_name,
                    UPPER(severity) AS severity,
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN score_status IN ('FAIL', 'WARN') THEN 1 ELSE 0 END) AS finding_count
                FROM audit_results
                WHERE execution_status = 'completed'
                GROUP BY category_name, UPPER(severity)
                """
            ).fetchall()

        categories = [str(row["source_sheet_name"]).strip() for row in category_rows]
        counts = {
            (str(row["category_name"]), str(row["severity"]).upper()): {
                "total_count": int(row["total_count"] or 0),
                "finding_count": int(row["finding_count"] or 0),
            }
            for row in count_rows
        }

        heatmap: list[dict[str, Any]] = []
        for category_name in categories:
            for severity in SEVERITY_BUCKETS:
                bucket = counts.get((category_name, severity), {"total_count": 0, "finding_count": 0})
                heatmap.append(
                    {
                        "category_name": category_name,
                        "severity": severity,
                        "count": bucket["finding_count"],
                        "total_count": bucket["total_count"],
                    }
                )
        return heatmap

    def get_dashboard_summary(self, recent_limit: int = 10) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            totals = conn.execute(
                """
                SELECT
                    COUNT(*) AS run_count,
                    COALESCE(SUM(total_tests), 0) AS total_tests,
                    COALESCE(SUM(pass_count), 0) AS pass_count,
                    COALESCE(SUM(warn_count), 0) AS warn_count,
                    COALESCE(SUM(fail_count), 0) AS fail_count,
                    COALESCE(SUM(CASE WHEN error_count > 0 THEN error_count ELSE 0 END), 0) AS error_count
                FROM audit_runs
                WHERE status = 'completed'
                """
            ).fetchone()
            by_category = conn.execute(
                """
                SELECT
                    category_name,
                    SUM(CASE WHEN score_status = 'FAIL' THEN 1 ELSE 0 END) AS violations,
                    SUM(CASE WHEN score_status = 'WARN' THEN 1 ELSE 0 END) AS partials,
                    SUM(CASE WHEN score_status = 'PASS' THEN 1 ELSE 0 END) AS safe,
                    COUNT(*) AS total
                FROM audit_results
                WHERE execution_status = 'completed'
                GROUP BY category_name
                ORDER BY violations DESC, partials DESC, category_name
                """
            ).fetchall()
            risk_distribution = conn.execute(
                """
                SELECT risk_level AS risk, COUNT(*) AS count
                FROM audit_results
                WHERE execution_status = 'completed' AND risk_level IS NOT NULL
                GROUP BY risk_level
                ORDER BY CASE risk_level
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    WHEN 'LOW' THEN 4
                    ELSE 5
                END
                """
            ).fetchall()
            severity_distribution = conn.execute(
                """
                SELECT
                    UPPER(severity) AS severity,
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN score_status IN ('FAIL', 'WARN') THEN 1 ELSE 0 END) AS finding_count
                FROM audit_results
                WHERE execution_status = 'completed'
                GROUP BY UPPER(severity)
                """
            ).fetchall()
            critical_findings_row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM audit_results
                WHERE execution_status = 'completed'
                  AND UPPER(severity) = 'CRITICAL'
                  AND score_status IN ('FAIL', 'WARN')
                """
            ).fetchone()

        total_tests = int(totals["total_tests"]) if totals else 0
        pass_count = int(totals["pass_count"]) if totals else 0
        warn_count = int(totals["warn_count"]) if totals else 0
        fail_count = int(totals["fail_count"]) if totals else 0
        scored_total = pass_count + warn_count + fail_count
        pass_rate = round((pass_count / scored_total) * 100, 2) if scored_total else 0.0
        severity_map = {
            str(row["severity"]).upper(): {
                "severity": str(row["severity"]).upper(),
                "count": int(row["finding_count"] or 0),
                "total_count": int(row["total_count"] or 0),
            }
            for row in severity_distribution
        }

        return {
            "totals": {
                "run_count": int(totals["run_count"]) if totals else 0,
                "total_tests": total_tests,
                "pass_count": pass_count,
                "warn_count": warn_count,
                "fail_count": fail_count,
                "safe_count": pass_count,
                "partial_count": warn_count,
                "violation_count": fail_count,
                "finding_count": warn_count + fail_count,
                "pass_rate": pass_rate,
                "critical_findings": int(critical_findings_row["count"]) if critical_findings_row else 0,
                "error_count": int(totals["error_count"]) if totals else 0,
            },
            "violations_by_category": [dict(row) for row in by_category],
            "risk_distribution": [dict(row) for row in risk_distribution],
            "severity_distribution": [
                severity_map.get(severity, {"severity": severity, "count": 0, "total_count": 0})
                for severity in SEVERITY_BUCKETS
            ],
            "heatmap": self.get_dashboard_heatmap(),
            "recent_runs": self.get_recent_runs(limit=recent_limit, completed_only=True),
        }

    def get_heatmap_dashboard(self, recent_limit: int = 8, activity_days: int = 35, matrix_test_limit: int = 18) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            totals = conn.execute(
                """
                SELECT
                    COUNT(*) AS run_count,
                    COALESCE(SUM(total_tests), 0) AS total_tests,
                    COALESCE(SUM(pass_count), 0) AS pass_count,
                    COALESCE(SUM(warn_count), 0) AS warn_count,
                    COALESCE(SUM(fail_count), 0) AS fail_count,
                    COUNT(DISTINCT COALESCE(NULLIF(model_name, ''), target_registry_name)) AS model_count,
                    COUNT(DISTINCT target_registry_name) AS target_count
                FROM audit_runs
                WHERE status = 'completed'
                """
            ).fetchone()

            recent_runs = conn.execute(
                """
                SELECT *
                FROM audit_runs
                WHERE status = 'completed'
                ORDER BY COALESCE(completed_at, created_at) DESC
                LIMIT ?
                """,
                (recent_limit,),
            ).fetchall()

            activity_rows = conn.execute(
                """
                SELECT
                    substr(COALESCE(completed_at, created_at), 1, 10) AS activity_date,
                    COUNT(*) AS run_count,
                    COALESCE(SUM(total_tests), 0) AS total_tests,
                    COALESCE(SUM(fail_count), 0) AS fail_count,
                    COALESCE(SUM(warn_count), 0) AS warn_count,
                    CASE
                        WHEN COUNT(*) = 1 THEN MIN(id)
                        ELSE NULL
                    END AS single_run_id
                FROM audit_runs
                WHERE status = 'completed'
                  AND date(COALESCE(completed_at, created_at)) >= date('now', ?)
                GROUP BY substr(COALESCE(completed_at, created_at), 1, 10)
                ORDER BY activity_date ASC
                """,
                (f"-{activity_days - 1} day",),
            ).fetchall()

            risk_rows = conn.execute(
                """
                SELECT
                    category_name,
                    MIN(100, MAX(0, CAST((score_value / 10) AS INTEGER) * 10)) AS score_bucket,
                    COUNT(*) AS result_count,
                    SUM(CASE WHEN score_status = 'FAIL' THEN 1 ELSE 0 END) AS fail_count,
                    SUM(CASE WHEN score_status = 'WARN' THEN 1 ELSE 0 END) AS warn_count,
                    ROUND(AVG(score_value), 2) AS avg_score
                FROM audit_results
                WHERE execution_status = 'completed' AND score_value IS NOT NULL
                GROUP BY category_name, MIN(100, MAX(0, CAST((score_value / 10) AS INTEGER) * 10))
                ORDER BY category_name, score_bucket
                """
            ).fetchall()

            top_tests = conn.execute(
                """
                SELECT test_identifier
                FROM audit_results
                WHERE execution_status = 'completed'
                GROUP BY test_identifier
                ORDER BY
                    SUM(CASE WHEN score_status IN ('FAIL', 'WARN') THEN 1 ELSE 0 END) DESC,
                    MAX(COALESCE(completed_at, created_at)) DESC,
                    test_identifier
                LIMIT ?
                """,
                (matrix_test_limit,),
            ).fetchall()

            model_rows: list[sqlite3.Row] = []
            if top_tests:
                placeholders = ", ".join("?" for _ in top_tests)
                model_rows = conn.execute(
                    f"""
                    SELECT
                        test_identifier,
                        attack_type,
                        category_name,
                        COALESCE(NULLIF(r.model_name, ''), r.target_registry_name) AS model_name,
                        COUNT(*) AS result_count,
                        SUM(CASE WHEN ar.score_status = 'PASS' THEN 1 ELSE 0 END) AS pass_count,
                        SUM(CASE WHEN ar.score_status = 'WARN' THEN 1 ELSE 0 END) AS warn_count,
                        SUM(CASE WHEN ar.score_status = 'FAIL' THEN 1 ELSE 0 END) AS fail_count,
                        CASE
                            WHEN COUNT(DISTINCT ar.run_id) = 1 THEN MIN(ar.run_id)
                            ELSE NULL
                        END AS single_run_id
                    FROM audit_results ar
                    INNER JOIN audit_runs r ON r.id = ar.run_id
                    WHERE ar.execution_status = 'completed'
                      AND ar.test_identifier IN ({placeholders})
                    GROUP BY test_identifier, attack_type, category_name, COALESCE(NULLIF(r.model_name, ''), r.target_registry_name)
                    ORDER BY category_name, test_identifier, model_name
                    """,
                    tuple(row["test_identifier"] for row in top_tests),
                ).fetchall()

            categories = [
                str(row["source_sheet_name"]).strip()
                for row in conn.execute(
                    """
                    SELECT source_sheet_name
                    FROM audit_categories
                    ORDER BY id
                    """
                ).fetchall()
            ]

        total_tests = int(totals["total_tests"]) if totals else 0
        pass_count = int(totals["pass_count"]) if totals else 0
        warn_count = int(totals["warn_count"]) if totals else 0
        fail_count = int(totals["fail_count"]) if totals else 0
        scored_total = pass_count + warn_count + fail_count
        pass_rate = round((pass_count / scored_total) * 100, 2) if scored_total else 0.0

        run_items = [self._deserialize_run(dict(row)) for row in recent_runs]
        run_order = [run["id"] for run in run_items]
        run_labels = [
            {
                "run_id": run["id"],
                "label": run["id"][:8],
                "model_name": run.get("model_name") or run.get("target_registry_name"),
                "completed_at": run.get("completed_at") or run["created_at"],
            }
            for run in run_items
        ]

        pass_rate_map: dict[tuple[str, str], dict[str, Any]] = {}
        if run_order:
            with closing(self._connect()) as conn:
                placeholders = ", ".join("?" for _ in run_order)
                run_matrix_rows = conn.execute(
                    f"""
                    SELECT
                        category_name,
                        run_id,
                        COUNT(*) AS total_count,
                        SUM(CASE WHEN score_status = 'PASS' THEN 1 ELSE 0 END) AS pass_count,
                        SUM(CASE WHEN score_status IN ('FAIL', 'WARN') THEN 1 ELSE 0 END) AS finding_count
                    FROM audit_results
                    WHERE execution_status = 'completed'
                      AND run_id IN ({placeholders})
                    GROUP BY category_name, run_id
                    """,
                    tuple(run_order),
                ).fetchall()
            pass_rate_map = {
                (str(row["category_name"]), str(row["run_id"])): {
                    "category_name": str(row["category_name"]),
                    "run_id": str(row["run_id"]),
                    "total_count": int(row["total_count"] or 0),
                    "finding_count": int(row["finding_count"] or 0),
                    "pass_rate": round((int(row["pass_count"] or 0) / int(row["total_count"] or 1)) * 100, 2) if int(row["total_count"] or 0) else None,
                    "drilldown_supported": int(row["total_count"] or 0) > 0,
                }
                for row in run_matrix_rows
            }

        pass_rate_cells: list[dict[str, Any]] = []
        for category_name in categories:
            for run in run_items:
                pass_rate_cells.append(
                    pass_rate_map.get(
                        (category_name, run["id"]),
                        {
                            "category_name": category_name,
                            "run_id": run["id"],
                            "total_count": 0,
                            "finding_count": 0,
                            "pass_rate": None,
                            "drilldown_supported": False,
                        },
                    )
                )

        activity_cells = []
        activity_map = {str(row["activity_date"]): dict(row) for row in activity_rows}
        with closing(self._connect()) as conn:
            date_rows = conn.execute(
                """
                SELECT date('now', ?) AS activity_date
                """,
                (f"-{activity_days - 1} day",),
            ).fetchall()
        if date_rows:
            start_date = str(date_rows[0]["activity_date"])
            start = datetime.fromisoformat(start_date)
            for offset in range(activity_days):
                day = start + timedelta(days=offset)
                iso_day = day.date().isoformat()
                item = activity_map.get(iso_day)
                if item:
                    total = int(item["total_tests"] or 0)
                    findings = int(item["fail_count"] or 0) + int(item["warn_count"] or 0)
                    activity_cells.append(
                        {
                            "activity_date": iso_day,
                            "run_count": int(item["run_count"] or 0),
                            "total_tests": total,
                            "finding_count": findings,
                            "failure_density": round((findings / total) * 100, 2) if total else 0.0,
                            "single_run_id": item.get("single_run_id"),
                            "drilldown_supported": bool(item.get("single_run_id")),
                            "drilldown_reason": None if item.get("single_run_id") else "Multiple runs occurred on this day; open a specific run from Recent Audits for precise findings.",
                        }
                    )
                else:
                    activity_cells.append(
                        {
                            "activity_date": iso_day,
                            "run_count": 0,
                            "total_tests": 0,
                            "finding_count": 0,
                            "failure_density": 0.0,
                            "single_run_id": None,
                            "drilldown_supported": False,
                            "drilldown_reason": "No completed structured audit runs occurred on this day.",
                        }
                    )

        model_names = sorted({str(row["model_name"]) for row in model_rows if row["model_name"]})
        model_matrix = [
            {
                "test_identifier": str(row["test_identifier"]),
                "attack_type": str(row["attack_type"]),
                "category_name": str(row["category_name"]),
                "model_name": str(row["model_name"]),
                "pass_count": int(row["pass_count"] or 0),
                "warn_count": int(row["warn_count"] or 0),
                "fail_count": int(row["fail_count"] or 0),
                "result_count": int(row["result_count"] or 0),
                "dominant_status": (
                    "FAIL"
                    if int(row["fail_count"] or 0) >= max(int(row["warn_count"] or 0), int(row["pass_count"] or 0))
                    else "WARN"
                    if int(row["warn_count"] or 0) >= int(row["pass_count"] or 0)
                    else "PASS"
                ),
                "drilldown_run_id": row["single_run_id"],
                "drilldown_supported": bool(row["single_run_id"]),
            }
            for row in model_rows
        ]

        risk_distribution = []
        for row in risk_rows:
            result_count = int(row["result_count"] or 0)
            finding_count = int(row["fail_count"] or 0) + int(row["warn_count"] or 0)
            risk_distribution.append(
                {
                    "category_name": str(row["category_name"]),
                    "score_bucket": int(row["score_bucket"] or 0),
                    "avg_score": float(row["avg_score"] or 0.0),
                    "result_count": result_count,
                    "finding_count": finding_count,
                    "failure_density": round((finding_count / result_count) * 100, 2) if result_count else 0.0,
                }
            )

        return {
            "totals": {
                "run_count": int(totals["run_count"]) if totals else 0,
                "total_tests": total_tests,
                "pass_count": pass_count,
                "warn_count": warn_count,
                "fail_count": fail_count,
                "pass_rate": pass_rate,
                "model_count": int(totals["model_count"]) if totals else 0,
                "target_count": int(totals["target_count"]) if totals else 0,
            },
            "category_severity_matrix": self.get_dashboard_heatmap(),
            "run_labels": run_labels,
            "category_run_pass_rate": pass_rate_cells,
            "activity_heatmap": activity_cells,
            "model_names": model_names,
            "test_model_matrix": model_matrix,
            "risk_score_distribution": risk_distribution,
            "recent_runs": run_items,
        }

    def ensure_legacy_stability_records(self) -> None:
        """Create one-run stability rows for completed legacy results lacking multi-run metadata."""
        now = _utc_now()
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """
                SELECT
                    ar.*,
                    r.target_type,
                    r.target_registry_name,
                    r.model_name,
                    r.endpoint
                FROM audit_results ar
                INNER JOIN audit_runs r ON r.id = ar.run_id
                WHERE ar.execution_status = 'completed'
                  AND ar.stability_run_id IS NULL
                ORDER BY ar.run_id, ar.display_order, ar.id
                """
            ).fetchall()
            profile_cache: dict[str, int] = {}
            for row in rows:
                run_id = str(row["run_id"])
                if run_id not in profile_cache:
                    existing = conn.execute(
                        "SELECT id FROM audit_execution_profile WHERE audit_session_id = ? ORDER BY id LIMIT 1",
                        (run_id,),
                    ).fetchone()
                    if existing:
                        profile_cache[run_id] = int(existing["id"])
                    else:
                        conn.execute(
                            """
                            INSERT INTO audit_execution_profile (
                                audit_session_id,
                                mode_code,
                                model_target_type,
                                model_target_name,
                                provider_name,
                                api_style,
                                temperature,
                                top_p,
                                fixed_seed,
                                base_seed,
                                seed_strategy,
                                run_count_requested,
                                variability_mode,
                                created_at,
                                created_by
                            )
                            VALUES (?, 'COMPLIANCE', ?, ?, ?, ?, 0.0, 1.0, 1, ?, 'FIXED', 1, 0, ?, 'legacy-adapter')
                            """,
                            (
                                run_id,
                                row["target_type"],
                                row["model_name"] or row["target_registry_name"],
                                self._infer_provider_name(dict(row)),
                                self._infer_api_style(dict(row)),
                                self._stable_seed(run_id),
                                now,
                            ),
                        )
                        profile_cache[run_id] = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

                conn.execute(
                    """
                    INSERT INTO audit_test_case_result_group (
                        audit_session_id,
                        execution_profile_id,
                        prompt_source_type,
                        prompt_source_ref,
                        category_code,
                        category_name,
                        subcategory_name,
                        severity_expected,
                        expected_behavior_text,
                        objective_text,
                        run_count_actual,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        run_id,
                        profile_cache[run_id],
                        "variant" if row["variant_id"] else "excel",
                        row["test_identifier"],
                        row["category_name"],
                        row["category_name"],
                        row["attack_type"],
                        row["severity"],
                        row["expected_behavior_snapshot"],
                        row["test_objective"],
                        now,
                    ),
                )
                group_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
                evaluation = evaluate_response(
                    response_text=row["response_received"] or "",
                    expected_behavior=row["expected_behavior_snapshot"] or "",
                    category_name=row["category_name"] or "",
                    scoring_guidance=row["original_result_guidance_snapshot"] or "",
                    prompt_sequence=row["actual_prompt_sequence"] or "",
                    attack_type=row["attack_type"] or "",
                )
                conn.execute(
                    """
                    INSERT INTO audit_test_case_run (
                        result_group_id,
                        run_no,
                        seed_used,
                        temperature_used,
                        top_p_used,
                        prompt_text,
                        normalized_prompt_text,
                        raw_response_text,
                        normalized_response_text,
                        evaluator_safety_label,
                        evaluator_safety_risk,
                        evaluator_compliance_label,
                        attack_family,
                        attack_subtype,
                        attack_severity_potential,
                        policy_domain,
                        expected_behavior_profile,
                        response_behavior_class,
                        attack_outcome,
                        refusal_strength,
                        refusal_style,
                        boundary_clarity,
                        safe_alternative_quality,
                        evaluator_reasoning,
                        scoring_version,
                        prompt_attack_assessment,
                        response_behavior_assessment,
                        refusal_strength_assessment,
                        scenario_verdict_assessment,
                        run_status,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        group_id,
                        1,
                        self._stable_seed(f"{run_id}:{row['id']}"),
                        0.0,
                        1.0,
                        row["prompt_sent"] or row["actual_prompt_sequence"],
                        self._normalize_text(row["prompt_sent"] or row["actual_prompt_sequence"]),
                        row["response_received"],
                        self._normalize_text(row["response_received"]),
                        evaluation.get("response_safety_label"),
                        evaluation.get("response_safety_risk"),
                        evaluation.get("status"),
                        evaluation.get("attack_family"),
                        evaluation.get("attack_subtype"),
                        evaluation.get("attack_severity_potential"),
                        evaluation.get("policy_domain"),
                        evaluation.get("expected_behavior_profile"),
                        evaluation.get("response_behavior_class"),
                        evaluation.get("attack_outcome"),
                        evaluation.get("refusal_strength"),
                        evaluation.get("refusal_style"),
                        evaluation.get("boundary_clarity"),
                        evaluation.get("safe_alternative_quality"),
                        evaluation.get("audit_reasoning") or evaluation.get("reason"),
                        evaluation.get("scoring_version"),
                        _dumps_json(evaluation.get("prompt_attack_assessment") or {}),
                        _dumps_json(evaluation.get("response_behavior_assessment") or {}),
                        _dumps_json(evaluation.get("refusal_strength_assessment") or {}),
                        _dumps_json(evaluation.get("scenario_verdict_assessment") or {}),
                        "COMPLETED",
                        now,
                    ),
                )
                physical_run_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
                conn.execute(
                    """
                    UPDATE audit_results
                    SET stability_group_id = ?,
                        stability_run_id = ?,
                        stability_run_no = 1,
                        attack_detected = ?,
                        attack_family = ?,
                        attack_subtype = ?,
                        attack_severity_potential = ?,
                        policy_domain = ?,
                        expected_behavior_profile = ?,
                        response_behavior_class = ?,
                        response_safety_label = ?,
                        response_safety_risk = ?,
                        attack_outcome = ?,
                        refusal_strength = ?,
                        refusal_style = ?,
                        boundary_clarity = ?,
                        safe_alternative_quality = ?,
                        scoring_version = ?,
                        prompt_attack_assessment = ?,
                        response_behavior_assessment = ?,
                        refusal_strength_assessment = ?,
                        scenario_verdict_assessment = ?
                    WHERE id = ?
                    """,
                    (
                        group_id,
                        physical_run_id,
                        1 if evaluation.get("attack_detected") else 0,
                        evaluation.get("attack_family"),
                        evaluation.get("attack_subtype"),
                        evaluation.get("attack_severity_potential"),
                        evaluation.get("policy_domain"),
                        evaluation.get("expected_behavior_profile"),
                        evaluation.get("response_behavior_class"),
                        evaluation.get("response_safety_label"),
                        evaluation.get("response_safety_risk"),
                        evaluation.get("attack_outcome"),
                        evaluation.get("refusal_strength"),
                        evaluation.get("refusal_style"),
                        evaluation.get("boundary_clarity"),
                        evaluation.get("safe_alternative_quality"),
                        evaluation.get("scoring_version"),
                        _dumps_json(evaluation.get("prompt_attack_assessment") or {}),
                        _dumps_json(evaluation.get("response_behavior_assessment") or {}),
                        _dumps_json(evaluation.get("refusal_strength_assessment") or {}),
                        _dumps_json(evaluation.get("scenario_verdict_assessment") or {}),
                        int(row["id"]),
                    ),
                )
                self._recalculate_single_stability_group(conn, group_id)

    def _recalculate_stability_groups(self, conn: sqlite3.Connection, run_id: str) -> None:
        group_rows = conn.execute(
            "SELECT id FROM audit_test_case_result_group WHERE audit_session_id = ?",
            (run_id,),
        ).fetchall()
        for row in group_rows:
            self._recalculate_single_stability_group(conn, int(row["id"]))

    def _recalculate_single_stability_group(self, conn: sqlite3.Connection, group_id: int) -> None:
        rows = [dict(row) for row in conn.execute(
            """
            SELECT *
            FROM audit_test_case_run
            WHERE result_group_id = ?
            ORDER BY run_no
            """,
            (group_id,),
        ).fetchall()]
        aggregate = aggregate_runs(rows)
        conn.execute(
            "UPDATE audit_test_case_run SET is_worst_case = 0, is_best_case = 0 WHERE result_group_id = ?",
            (group_id,),
        )
        if aggregate.get("worst_case_run_no") is not None:
            conn.execute(
                "UPDATE audit_test_case_run SET is_worst_case = 1 WHERE result_group_id = ? AND run_no = ?",
                (group_id, aggregate["worst_case_run_no"]),
            )
        if aggregate.get("best_case_run_no") is not None:
            conn.execute(
                "UPDATE audit_test_case_run SET is_best_case = 1 WHERE result_group_id = ? AND run_no = ?",
                (group_id, aggregate["best_case_run_no"]),
            )
        conn.execute(
            """
            UPDATE audit_test_case_result_group
            SET run_count_actual = ?,
                aggregate_verdict = ?,
                aggregate_risk_level = ?,
                pass_rate = ?,
                warn_rate = ?,
                fail_rate = ?,
                safe_rate = ?,
                attack_success_rate = ?,
                resistance_rate = ?,
                variance_score = ?,
                stability_score = ?,
                worst_case_verdict = ?,
                worst_case_risk_level = ?,
                best_case_verdict = ?,
                summary_reasoning = ?
            WHERE id = ?
            """,
            (
                aggregate["run_count_actual"],
                aggregate["aggregate_verdict"],
                aggregate["aggregate_risk_level"],
                aggregate["pass_rate"],
                aggregate["warn_rate"],
                aggregate["fail_rate"],
                aggregate["safe_rate"],
                aggregate["attack_success_rate"],
                aggregate["resistance_rate"],
                aggregate["variance_score"],
                aggregate["stability_score"],
                aggregate["worst_case_verdict"],
                aggregate["worst_case_risk_level"],
                aggregate["best_case_verdict"],
                aggregate["summary_reasoning"],
                group_id,
            ),
        )

    def get_stability_dashboard(self, limit: int = 100) -> dict[str, Any]:
        self.ensure_legacy_stability_records()
        with closing(self._connect()) as conn:
            groups = [dict(row) for row in conn.execute(
                """
                SELECT
                    g.*,
                    p.mode_code,
                    p.model_target_type,
                    p.model_target_name,
                    p.provider_name,
                    p.api_style,
                    p.temperature,
                    p.top_p,
                    p.top_k,
                    p.fixed_seed,
                    p.base_seed,
                    p.seed_strategy,
                    p.max_tokens,
                    p.run_count_requested,
                    p.variability_mode,
                    r.target_registry_name,
                    r.model_name,
                    r.endpoint,
                    r.completed_at,
                    r.created_at AS session_created_at
                FROM audit_test_case_result_group g
                INNER JOIN audit_execution_profile p ON p.id = g.execution_profile_id
                INNER JOIN audit_runs r ON r.id = g.audit_session_id
                ORDER BY COALESCE(r.completed_at, r.created_at) DESC, g.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()]

            by_category = [dict(row) for row in conn.execute(
                """
                SELECT
                    category_name,
                    COUNT(*) AS group_count,
                    ROUND(AVG(stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(fail_rate), 2) AS avg_fail_rate,
                    SUM(CASE WHEN aggregate_verdict = 'FAIL' THEN 1 ELSE 0 END) AS fail_groups,
                    SUM(CASE WHEN aggregate_verdict = 'WARN' THEN 1 ELSE 0 END) AS warn_groups
                FROM audit_test_case_result_group
                GROUP BY category_name
                ORDER BY avg_fail_rate DESC, avg_stability_score ASC, category_name
                """
            ).fetchall()]

            by_target = [dict(row) for row in conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(r.model_name, ''), r.target_registry_name) AS target_name,
                    COUNT(*) AS group_count,
                    ROUND(AVG(g.stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(g.fail_rate), 2) AS avg_fail_rate
                FROM audit_test_case_result_group g
                INNER JOIN audit_runs r ON r.id = g.audit_session_id
                GROUP BY COALESCE(NULLIF(r.model_name, ''), r.target_registry_name)
                ORDER BY avg_stability_score ASC, avg_fail_rate DESC
                """
            ).fetchall()]

            mode_rows = [dict(row) for row in conn.execute(
                """
                SELECT
                    p.mode_code,
                    COUNT(*) AS group_count,
                    ROUND(AVG(g.stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(g.fail_rate), 2) AS avg_fail_rate
                FROM audit_test_case_result_group g
                INNER JOIN audit_execution_profile p ON p.id = g.execution_profile_id
                GROUP BY p.mode_code
                ORDER BY p.mode_code
                """
            ).fetchall()]

            summary = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_groups,
                    ROUND(AVG(stability_score), 2) AS avg_stability_score,
                    ROUND(AVG(fail_rate), 2) AS avg_fail_rate,
                    SUM(CASE WHEN worst_case_verdict = 'FAIL' THEN 1 ELSE 0 END) AS worst_case_fail_count
                FROM audit_test_case_result_group
                """
            ).fetchone()

        worst_category = by_category[0]["category_name"] if by_category else None
        most_unstable_target = by_target[0]["target_name"] if by_target else None
        return {
            "summary": {
                "total_groups": int(summary["total_groups"] or 0) if summary else 0,
                "avg_stability_score": float(summary["avg_stability_score"] or 0.0) if summary else 0.0,
                "avg_fail_rate": float(summary["avg_fail_rate"] or 0.0) if summary else 0.0,
                "worst_category": worst_category,
                "most_unstable_target": most_unstable_target,
                "worst_case_fail_count": int(summary["worst_case_fail_count"] or 0) if summary else 0,
            },
            "by_category": by_category,
            "by_target": by_target,
            "by_mode": mode_rows,
            "groups": groups,
        }

    def get_stability_group_detail(self, group_id: int) -> Optional[dict[str, Any]]:
        self.ensure_legacy_stability_records()
        with closing(self._connect()) as conn:
            group = conn.execute(
                """
                SELECT
                    g.*,
                    p.mode_code,
                    p.model_target_type,
                    p.model_target_name,
                    p.provider_name,
                    p.api_style,
                    p.temperature,
                    p.top_p,
                    p.top_k,
                    p.fixed_seed,
                    p.base_seed,
                    p.seed_strategy,
                    p.max_tokens,
                    p.run_count_requested,
                    p.variability_mode,
                    r.target_registry_name,
                    r.model_name,
                    r.endpoint,
                    r.completed_at,
                    r.created_at AS session_created_at
                FROM audit_test_case_result_group g
                INNER JOIN audit_execution_profile p ON p.id = g.execution_profile_id
                INNER JOIN audit_runs r ON r.id = g.audit_session_id
                WHERE g.id = ?
                """,
                (group_id,),
            ).fetchone()
            if group is None:
                return None
            runs = [dict(row) for row in conn.execute(
                """
                SELECT *
                FROM audit_test_case_run
                WHERE result_group_id = ?
                ORDER BY run_no
                """,
                (group_id,),
            ).fetchall()]
            traces = {
                int(row["run_id"]): []
                for row in conn.execute("SELECT DISTINCT run_id FROM audit_retrieval_trace WHERE run_id IN (SELECT id FROM audit_test_case_run WHERE result_group_id = ?)", (group_id,)).fetchall()
            }
            trace_rows = conn.execute(
                """
                SELECT *
                FROM audit_retrieval_trace
                WHERE run_id IN (SELECT id FROM audit_test_case_run WHERE result_group_id = ?)
                ORDER BY run_id, retrieval_rank, id
                """,
                (group_id,),
            ).fetchall()
            for row in trace_rows:
                item = dict(row)
                traces.setdefault(int(item["run_id"]), []).append(item)
        run_items = []
        for run in runs:
            run["retrieval_traces"] = traces.get(int(run["id"]), [])
            run_items.append(self._deserialize_stability_run(run))
        return {"group": dict(group), "runs": run_items}

    def get_result_execution_parameters(self, result_id: int) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT
                    tr.seed_used,
                    tr.temperature_used,
                    tr.top_p_used,
                    tr.top_k_used,
                    p.max_tokens,
                    p.mode_code,
                    p.fixed_seed,
                    p.seed_strategy
                FROM audit_results ar
                LEFT JOIN audit_test_case_run tr ON tr.id = ar.stability_run_id
                LEFT JOIN audit_test_case_result_group g ON g.id = ar.stability_group_id
                LEFT JOIN audit_execution_profile p ON p.id = g.execution_profile_id
                WHERE ar.id = ?
                """,
                (result_id,),
            ).fetchone()
        return dict(row) if row else {}

    def get_audit_context_for_attack(self, attack_result_id: str, conversation_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        with closing(self._connect()) as conn:
            if conversation_id:
                row = conn.execute(
                    """
                    SELECT
                        category_name,
                        attack_type,
                        expected_behavior_snapshot,
                        original_result_guidance_snapshot,
                        severity,
                        test_identifier,
                        run_id
                    FROM audit_results
                    WHERE attack_result_id = ?
                      AND conversation_id = ?
                    ORDER BY completed_at DESC, id DESC
                    LIMIT 1
                    """,
                    (attack_result_id, conversation_id),
                ).fetchone()
            else:
                row = None
            if row is None:
                row = conn.execute(
                    """
                    SELECT
                        category_name,
                        attack_type,
                        expected_behavior_snapshot,
                        original_result_guidance_snapshot,
                        severity,
                        test_identifier,
                        run_id
                    FROM audit_results
                    WHERE attack_result_id = ?
                    ORDER BY completed_at DESC, id DESC
                    LIMIT 1
                    """,
                    (attack_result_id,),
                ).fetchone()
        return dict(row) if row else None

    def save_interactive_audit_conversation(
        self,
        *,
        attack_result_id: str,
        conversation_id: str,
        target_info: dict[str, Any],
        linked_context: dict[str, Any],
        turns: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> str:
        if not turns:
            raise ValueError("Interactive Audit conversation has no assistant turns to save.")

        now = _utc_now()
        category_name = str(linked_context.get("category_name") or "Interactive Audit").strip() or "Interactive Audit"
        category_id = self.ensure_category(category_name, source_sheet_name=category_name)
        target_registry_name = (
            str(target_info.get("target_registry_name") or "").strip()
            or f"interactive::{str(target_info.get('target_type') or 'UnknownTarget')}::{str(target_info.get('model_name') or attack_result_id[:8])}"
        )
        existing_run_id = self._get_interactive_run_id(
            attack_result_id=attack_result_id,
            conversation_id=conversation_id,
        )
        run_id = existing_run_id or str(uuid.uuid4())

        selected_test_ids: list[int] = []
        pass_count = int(summary.get("pass_count") or 0)
        warn_count = int(summary.get("warn_count") or 0)
        fail_count = int(summary.get("fail_count") or 0)

        with closing(self._connect()) as conn, conn:
            if existing_run_id:
                previous_test_rows = conn.execute(
                    "SELECT DISTINCT test_id FROM audit_results WHERE run_id = ?",
                    (run_id,),
                ).fetchall()
                previous_test_ids = [int(row["test_id"]) for row in previous_test_rows]
                conn.execute("DELETE FROM audit_results WHERE run_id = ?", (run_id,))
                if previous_test_ids:
                    placeholders = ", ".join("?" for _ in previous_test_ids)
                    conn.execute(
                        f"DELETE FROM audit_tests WHERE id IN ({placeholders}) AND source_origin = 'interactive'",
                        tuple(previous_test_ids),
                    )
                conn.execute(
                    """
                    UPDATE audit_runs
                    SET
                        target_id = ?,
                        target_registry_name = ?,
                        target_type = ?,
                        model_name = ?,
                        endpoint = ?,
                        supports_multi_turn = ?,
                        status = 'completed',
                        selected_categories = ?,
                        selected_test_ids = ?,
                        selected_variant_ids = '[]',
                        total_tests = ?,
                        completed_tests = ?,
                        pass_count = ?,
                        warn_count = ?,
                        fail_count = ?,
                        error_count = 0,
                        started_at = COALESCE(started_at, ?),
                        completed_at = ?,
                        updated_at = ?,
                        error_message = NULL
                    WHERE id = ?
                    """,
                    (
                        target_registry_name,
                        target_registry_name,
                        str(target_info.get("target_type") or "InteractiveAuditTarget"),
                        target_info.get("model_name"),
                        target_info.get("endpoint"),
                        1,
                        _dumps_json([category_name]),
                        _dumps_json([]),
                        len(turns),
                        len(turns),
                        pass_count,
                        warn_count,
                        fail_count,
                        now,
                        now,
                        now,
                        run_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO audit_runs (
                        id,
                        target_id,
                        target_registry_name,
                        target_type,
                        model_name,
                        endpoint,
                        supports_multi_turn,
                        status,
                        selected_categories,
                        selected_test_ids,
                        selected_variant_ids,
                        total_tests,
                        completed_tests,
                        pass_count,
                        warn_count,
                        fail_count,
                        error_count,
                        created_at,
                        started_at,
                        completed_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, '[]', ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        target_registry_name,
                        target_registry_name,
                        str(target_info.get("target_type") or "InteractiveAuditTarget"),
                        target_info.get("model_name"),
                        target_info.get("endpoint"),
                        1,
                        _dumps_json([category_name]),
                        _dumps_json([]),
                        len(turns),
                        len(turns),
                        pass_count,
                        warn_count,
                        fail_count,
                        now,
                        now,
                        now,
                        now,
                    ),
                )

            for display_order, turn in enumerate(turns, start=1):
                workbook_row_id = int(
                    conn.execute(
                        """
                        SELECT COALESCE(MAX(workbook_row_id), 0) + 1 AS next_row
                        FROM audit_tests
                        WHERE category_id = ? AND source_origin = 'interactive'
                        """,
                        (category_id,),
                    ).fetchone()["next_row"]
                )
                test_objective = str(turn.get("latest_user_prompt") or f"Interactive Audit turn {turn.get('assistant_turn_number') or display_order}").strip()
                prompt_sequence = str(turn.get("prompt_sequence") or "").strip()
                prompt_steps = self._parse_prompt_steps(prompt_sequence) or [prompt_sequence]
                expected_behavior = str(turn.get("expected_behavior_text") or "Provide only safe, bounded, policy-compliant information.").strip()
                severity = str(linked_context.get("severity") or turn.get("final_risk_level") or "MEDIUM").upper()

                conn.execute(
                    """
                    INSERT INTO audit_tests (
                        category_id,
                        workbook_row_id,
                        attack_type,
                        test_objective,
                        prompt_sequence,
                        prompt_steps_json,
                        supporting_documents,
                        expected_behavior,
                        original_result_guidance,
                        domain,
                        severity,
                        source_origin,
                        is_active,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'interactive', 0, ?, ?)
                    """,
                    (
                        category_id,
                        workbook_row_id,
                        str(turn.get("attack_family") or linked_context.get("attack_type") or "Interactive Audit"),
                        test_objective,
                        prompt_sequence,
                        _dumps_json(prompt_steps),
                        None,
                        expected_behavior,
                        linked_context.get("original_result_guidance_snapshot"),
                        None,
                        severity,
                        now,
                        now,
                    ),
                )
                test_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
                selected_test_ids.append(test_id)

                interaction_log = [
                    {"role": "user", "content": turn.get("latest_user_prompt") or turn.get("prompt_sequence") or ""},
                    {"role": "assistant", "content": turn.get("response_text") or ""},
                ]
                assistant_turn = int(turn.get("assistant_turn_number") or display_order)

                conn.execute(
                    """
                    INSERT INTO audit_results (
                        run_id,
                        test_id,
                        variant_id,
                        display_order,
                        result_label,
                        variant_name,
                        prompt_source_type,
                        prompt_source_label,
                        transient_prompt_used,
                        execution_scope_label,
                        variant_group_key,
                        editor_snapshot,
                        category_name,
                        domain,
                        severity,
                        test_identifier,
                        workbook_row_id,
                        attack_type,
                        test_objective,
                        original_workbook_prompt,
                        actual_prompt_sequence,
                        actual_prompt_steps_json,
                        supporting_documents_snapshot,
                        prompt_sent,
                        response_received,
                        expected_behavior_snapshot,
                        original_result_guidance_snapshot,
                        score_status,
                        risk_level,
                        score_value,
                        score_reason,
                        audit_reasoning,
                        attack_detected,
                        attack_family,
                        attack_subtype,
                        attack_severity_potential,
                        policy_domain,
                        expected_behavior_profile,
                        response_behavior_class,
                        response_safety_label,
                        response_safety_risk,
                        attack_outcome,
                        refusal_strength,
                        refusal_style,
                        boundary_clarity,
                        safe_alternative_quality,
                        scoring_version,
                        prompt_attack_assessment,
                        response_behavior_assessment,
                        refusal_strength_assessment,
                        scenario_verdict_assessment,
                        interaction_log,
                        execution_status,
                        attack_result_id,
                        conversation_id,
                        created_at,
                        started_at,
                        completed_at
                    )
                    VALUES (?, ?, NULL, ?, ?, NULL, ?, ?, 0, ?, ?, NULL, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        test_id,
                        display_order,
                        "Interactive Turn",
                        "interactive",
                        f"Interactive Turn {assistant_turn}",
                        "Interactive Audit",
                        f"test-{test_id}:interactive:turn-{assistant_turn}",
                        category_name,
                        severity,
                        f"Interactive::{attack_result_id[:8]}::T{assistant_turn}",
                        workbook_row_id,
                        str(turn.get("attack_family") or linked_context.get("attack_type") or "Interactive Audit"),
                        test_objective,
                        prompt_sequence,
                        prompt_sequence,
                        _dumps_json(prompt_steps),
                        _dumps_json({}),
                        str(turn.get("latest_user_prompt") or prompt_sequence),
                        str(turn.get("response_text") or ""),
                        expected_behavior,
                        linked_context.get("original_result_guidance_snapshot"),
                        str(turn.get("compliance_verdict") or "NEEDS_REVIEW"),
                        str(turn.get("final_risk_level") or "MEDIUM"),
                        int(turn.get("score") or 0),
                        str(turn.get("short_reason") or ""),
                        str(turn.get("full_reason") or turn.get("short_reason") or ""),
                        1 if turn.get("attack_detected") else 0,
                        turn.get("attack_family"),
                        turn.get("attack_subtype"),
                        (turn.get("prompt_attack_assessment") or {}).get("attack_severity_potential"),
                        (turn.get("prompt_attack_assessment") or {}).get("policy_domain"),
                        turn.get("expected_behavior_profile"),
                        turn.get("response_behavior_class"),
                        turn.get("response_safety_label"),
                        turn.get("response_safety_risk"),
                        turn.get("attack_outcome"),
                        turn.get("refusal_strength"),
                        (turn.get("refusal_strength_assessment") or {}).get("refusal_style"),
                        (turn.get("refusal_strength_assessment") or {}).get("boundary_clarity"),
                        (turn.get("refusal_strength_assessment") or {}).get("safe_alternative_quality"),
                        turn.get("scoring_version"),
                        _dumps_json(turn.get("prompt_attack_assessment") or {}),
                        _dumps_json(turn.get("response_behavior_assessment") or {}),
                        _dumps_json(turn.get("refusal_strength_assessment") or {}),
                        _dumps_json(turn.get("scenario_verdict_assessment") or {}),
                        _dumps_json(interaction_log),
                        attack_result_id,
                        conversation_id,
                        now,
                        now,
                        now,
                    ),
                )

            conn.execute(
                """
                UPDATE audit_runs
                SET selected_test_ids = ?, updated_at = ?
                WHERE id = ?
                """,
                (_dumps_json(selected_test_ids), now, run_id),
            )

        return run_id

    def _get_interactive_run_id(self, *, attack_result_id: str, conversation_id: str) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT run_id
                FROM audit_results
                WHERE attack_result_id = ?
                  AND conversation_id = ?
                  AND prompt_source_type = 'interactive'
                ORDER BY id DESC
                LIMIT 1
                """,
                (attack_result_id, conversation_id),
            ).fetchone()
        return str(row["run_id"]) if row else None

    def get_target_capability_catalog(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM audit_target_capability_catalog
                ORDER BY sort_order, display_name
                """
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["supports_deterministic_seed"] = bool(item["supports_deterministic_seed"])
            item["supports_temperature"] = bool(item["supports_temperature"])
            item["supports_multi_run"] = bool(item["supports_multi_run"])
            item["is_builtin"] = bool(item["is_builtin"])
            items.append(item)
        return items

    def get_retrieval_traces_for_run(self, physical_run_id: int) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            return [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM audit_retrieval_trace
                    WHERE run_id = ?
                    ORDER BY retrieval_rank, id
                    """,
                    (physical_run_id,),
                ).fetchall()
            ]

    def add_retrieval_trace(self, physical_run_id: int, trace: dict[str, Any]) -> dict[str, Any]:
        """Persist retrieval evidence for a physical audit run."""
        with closing(self._connect()) as conn, conn:
            run = conn.execute("SELECT id FROM audit_test_case_run WHERE id = ?", (physical_run_id,)).fetchone()
            if run is None:
                raise ValueError(f"Unknown physical audit run '{physical_run_id}'")
            conn.execute(
                """
                INSERT INTO audit_retrieval_trace (
                    run_id,
                    document_id,
                    document_name,
                    document_type,
                    page_no,
                    chunk_id,
                    ocr_used,
                    retrieved_text_excerpt,
                    retrieval_rank,
                    retrieval_score,
                    source_uri,
                    citation_label
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    physical_run_id,
                    trace.get("document_id"),
                    trace.get("document_name"),
                    trace.get("document_type"),
                    trace.get("page_no"),
                    trace.get("chunk_id"),
                    1 if trace.get("ocr_used") else 0,
                    trace.get("retrieved_text_excerpt"),
                    trace.get("retrieval_rank"),
                    trace.get("retrieval_score"),
                    trace.get("source_uri"),
                    trace.get("citation_label"),
                ),
            )
            trace_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
            row = conn.execute("SELECT * FROM audit_retrieval_trace WHERE id = ?", (trace_id,)).fetchone()
        if row is None:
            raise ValueError("Failed to persist retrieval trace")
        item = dict(row)
        item["ocr_used"] = bool(item["ocr_used"])
        return item

    def get_audit_report_payload(self, run_id: str) -> Optional[dict[str, Any]]:
        """Build an additive structured report payload for legacy and multi-run sessions."""
        run = self.get_run_detail(run_id)
        if run is None:
            return None
        self.ensure_legacy_stability_records()
        with closing(self._connect()) as conn:
            profile = conn.execute(
                """
                SELECT *
                FROM audit_execution_profile
                WHERE audit_session_id = ?
                ORDER BY id
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            groups = [dict(row) for row in conn.execute(
                """
                SELECT *
                FROM audit_test_case_result_group
                WHERE audit_session_id = ?
                ORDER BY id
                """,
                (run_id,),
            ).fetchall()]

        profile_item = dict(profile) if profile else {
            "mode_code": "COMPLIANCE",
            "temperature": 0.0,
            "top_p": 1.0,
            "fixed_seed": 1,
            "seed_strategy": "FIXED",
            "run_count_requested": 1,
            "variability_mode": 0,
            "created_by": "legacy-adapter",
        }
        report_groups = []
        for group in groups:
            detail = self.get_stability_group_detail(int(group["id"]))
            runs = detail["runs"] if detail else []
            worst = next((item for item in runs if item.get("is_worst_case")), None)
            best = next((item for item in runs if item.get("is_best_case")), None)
            report_groups.append(
                {
                    **group,
                    "single_run_note": "Single-run result; no variance measured." if int(group.get("run_count_actual") or 1) <= 1 else None,
                    "worst_case_response_excerpt": (worst or {}).get("raw_response_text"),
                    "best_case_response_excerpt": (best or {}).get("raw_response_text"),
                    "attack_success_rate": group.get("attack_success_rate"),
                    "resistance_rate": group.get("resistance_rate"),
                    "runs": runs,
                }
            )

        return {
            "run": run,
            "execution_profile": {
                **profile_item,
                "fixed_seed": bool(profile_item.get("fixed_seed")),
                "variability_mode": bool(profile_item.get("variability_mode")),
            },
            "summary": {
                "mode": profile_item.get("mode_code", "COMPLIANCE"),
                "run_count": int(profile_item.get("run_count_requested") or 1),
                "temperature": profile_item.get("temperature"),
                "top_p": profile_item.get("top_p"),
                "seed_strategy": profile_item.get("seed_strategy"),
                "scoring_version": "v2",
                "single_run_note": "Single-run result; no variance measured." if int(profile_item.get("run_count_requested") or 1) <= 1 else None,
            },
            "result_groups": report_groups,
        }

    def create_rerun_for_stability_group(self, group_id: int) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT
                    ar.*,
                    r.target_registry_name,
                    r.target_type,
                    r.model_name,
                    r.endpoint,
                    r.supports_multi_turn,
                    p.mode_code,
                    p.provider_name,
                    p.api_style,
                    p.temperature,
                    p.top_p,
                    p.top_k,
                    p.fixed_seed,
                    p.base_seed,
                    p.seed_strategy,
                    p.max_tokens,
                    p.run_count_requested,
                    p.variability_mode
                FROM audit_results ar
                INNER JOIN audit_runs r ON r.id = ar.run_id
                INNER JOIN audit_test_case_result_group g ON g.id = ar.stability_group_id
                INNER JOIN audit_execution_profile p ON p.id = g.execution_profile_id
                WHERE ar.stability_group_id = ?
                ORDER BY ar.stability_run_no, ar.id
                LIMIT 1
                """,
                (group_id,),
            ).fetchone()
        if row is None:
            return None

        item = dict(row)
        target_info = {
            "target_registry_name": item["target_registry_name"],
            "target_type": item["target_type"],
            "model_name": item["model_name"],
            "endpoint": item["endpoint"],
            "supports_multi_turn": bool(item["supports_multi_turn"]),
        }
        execution_item = {
            "test_id": item["test_id"],
            "variant_id": item["variant_id"],
            "result_label": item["result_label"],
            "variant_name": item["variant_name"],
            "category_name": item["category_name"],
            "domain": item["domain"],
            "severity": item["severity"],
            "test_identifier": item["test_identifier"],
            "workbook_row_id": item["workbook_row_id"],
            "attack_type": item["attack_type"],
            "test_objective": item["test_objective"],
            "original_workbook_prompt": item["original_workbook_prompt"],
            "actual_prompt_sequence": item["actual_prompt_sequence"],
            "actual_prompt_steps": _loads_json(item["actual_prompt_steps_json"], []),
            "expected_behavior_snapshot": item["expected_behavior_snapshot"],
            "original_result_guidance_snapshot": item["original_result_guidance_snapshot"],
        }
        profile = {
            "mode_code": item["mode_code"],
            "provider_name": item["provider_name"],
            "api_style": item["api_style"],
            "temperature": item["temperature"],
            "top_p": item["top_p"],
            "top_k": item["top_k"],
            "fixed_seed": bool(item["fixed_seed"]),
            "base_seed": item["base_seed"],
            "seed_strategy": item["seed_strategy"],
            "max_tokens": item["max_tokens"],
            "run_count_requested": item["run_count_requested"],
            "variability_mode": bool(item["variability_mode"]),
            "created_by": "stability-rerun",
        }
        return self.create_run(
            category_names=[item["category_name"]],
            target_info=target_info,
            execution_items=[execution_item],
            execution_profile=profile,
        )

    def create_benchmark_source(
        self,
        *,
        source: dict[str, Any],
        scenarios: Optional[list[dict[str, Any]]] = None,
        media: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        metadata = source.get("metadata_json", source.get("metadata", {})) or {}
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO benchmark_source (
                    source_name,
                    source_type,
                    source_uri,
                    benchmark_family,
                    model_name,
                    version,
                    category_name,
                    subcategory_name,
                    scenario_id,
                    title,
                    description,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source["source_name"].strip(),
                    source["source_type"].strip(),
                    source.get("source_uri"),
                    source.get("benchmark_family"),
                    source.get("model_name"),
                    source.get("version"),
                    source.get("category_name"),
                    source.get("subcategory_name"),
                    source.get("scenario_id"),
                    source["title"].strip(),
                    source.get("description"),
                    _dumps_json(metadata),
                    now,
                ),
            )
            source_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
            scenario_id_by_code: dict[str, int] = {}
            for scenario in scenarios or []:
                scenario_id = self._insert_benchmark_scenario(conn, source_id=source_id, scenario=scenario, now=now)
                scenario_id_by_code[str(scenario.get("scenario_code") or scenario_id)] = scenario_id
                if scenario.get("scenario_id") is not None:
                    scenario_id_by_code[str(scenario["scenario_id"])] = scenario_id
                if scenario.get("id") is not None:
                    scenario_id_by_code[str(scenario["id"])] = scenario_id
            for media_item in media or []:
                scenario_ref = media_item.get("scenario_id")
                resolved_scenario_id = None
                if scenario_ref is not None:
                    resolved_scenario_id = scenario_id_by_code.get(str(scenario_ref))
                self._insert_benchmark_media(conn, source_id=source_id, scenario_id=resolved_scenario_id, media_item=media_item)
        item = self.get_benchmark_source(source_id)
        if item is None:
            raise ValueError("Failed to create benchmark source")
        return item

    def _insert_benchmark_scenario(
        self,
        conn: sqlite3.Connection,
        *,
        source_id: int,
        scenario: dict[str, Any],
        now: str,
    ) -> int:
        conn.execute(
            """
            INSERT INTO benchmark_scenario (
                benchmark_source_id,
                scenario_code,
                title,
                category_name,
                subcategory_name,
                objective_text,
                prompt_text,
                expected_behavior_text,
                modality,
                recommended_target_types,
                tags,
                severity_hint,
                replay_supported,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                str(scenario.get("scenario_code") or f"scenario-{source_id}-{now}").strip(),
                str(scenario["title"]).strip(),
                scenario.get("category_name") or "Unspecified",
                scenario.get("subcategory_name"),
                scenario.get("objective_text"),
                scenario.get("prompt_text"),
                scenario.get("expected_behavior_text"),
                scenario.get("modality") or "text",
                _dumps_json(scenario.get("recommended_target_types") or []),
                _dumps_json(scenario.get("tags") or []),
                scenario.get("severity_hint"),
                1 if scenario.get("replay_supported", bool(scenario.get("prompt_text"))) else 0,
                now,
            ),
        )
        return int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])

    @staticmethod
    def _insert_benchmark_media(
        conn: sqlite3.Connection,
        *,
        source_id: int,
        scenario_id: Optional[int],
        media_item: dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO benchmark_media (
                benchmark_source_id,
                scenario_id,
                media_type,
                media_uri,
                thumbnail_uri,
                caption,
                sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                scenario_id,
                media_item["media_type"],
                media_item["media_uri"],
                media_item.get("thumbnail_uri"),
                media_item.get("caption"),
                int(media_item.get("sort_order") or 0),
            ),
        )

    def get_benchmark_source(self, source_id: int) -> Optional[dict[str, Any]]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM benchmark_source WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            return None
        return self._deserialize_benchmark_source(dict(row))

    def list_benchmark_sources(
        self,
        *,
        source_type: Optional[str] = None,
        benchmark_family: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM benchmark_source WHERE 1 = 1"
        params: list[Any] = []
        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)
        if benchmark_family:
            query += " AND benchmark_family = ?"
            params.append(benchmark_family)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with closing(self._connect()) as conn:
            return [self._deserialize_benchmark_source(dict(row)) for row in conn.execute(query, params).fetchall()]

    def list_benchmark_scenarios(
        self,
        *,
        source_type: Optional[str] = None,
        category_name: Optional[str] = None,
        query_text: Optional[str] = None,
        replay_supported: Optional[bool] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                s.*,
                bs.source_name,
                bs.source_type,
                bs.source_uri,
                bs.benchmark_family,
                bs.model_name AS source_model_name,
                bs.version AS source_version,
                bs.title AS source_title,
                bs.description AS source_description,
                bs.metadata_json AS source_metadata_json
            FROM benchmark_scenario s
            INNER JOIN benchmark_source bs ON bs.id = s.benchmark_source_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if source_type:
            query += " AND bs.source_type = ?"
            params.append(source_type)
        if category_name:
            query += " AND s.category_name = ?"
            params.append(category_name)
        if replay_supported is not None:
            query += " AND s.replay_supported = ?"
            params.append(1 if replay_supported else 0)
        if query_text:
            like = f"%{query_text.strip()}%"
            query += " AND (s.title LIKE ? OR s.scenario_code LIKE ? OR s.objective_text LIKE ? OR s.prompt_text LIKE ?)"
            params.extend([like, like, like, like])
        query += " ORDER BY bs.created_at DESC, s.id DESC LIMIT ?"
        params.append(limit)
        with closing(self._connect()) as conn:
            return [self._deserialize_benchmark_scenario(dict(row)) for row in conn.execute(query, params).fetchall()]

    def get_benchmark_scenario(self, scenario_id: int) -> Optional[dict[str, Any]]:
        query = """
            SELECT
                s.*,
                bs.source_name,
                bs.source_type,
                bs.source_uri,
                bs.benchmark_family,
                bs.model_name AS source_model_name,
                bs.version AS source_version,
                bs.title AS source_title,
                bs.description AS source_description,
                bs.metadata_json AS source_metadata_json
            FROM benchmark_scenario s
            INNER JOIN benchmark_source bs ON bs.id = s.benchmark_source_id
            WHERE s.id = ?
        """
        with closing(self._connect()) as conn:
            row = conn.execute(query, (scenario_id,)).fetchone()
        if row is None:
            return None
        return self._deserialize_benchmark_scenario(dict(row))

    def get_benchmark_client_results(self, scenario_id: int, *, limit: int = 25) -> list[dict[str, Any]]:
        """Return structured replay results linked to a public benchmark scenario."""

        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT ar.*
                FROM audit_results ar
                INNER JOIN audit_tests t ON t.id = ar.test_id
                WHERE t.source_origin = 'benchmark'
                    AND t.workbook_row_id = ?
                ORDER BY ar.created_at DESC, ar.id DESC
                LIMIT ?
                """,
                (1_000_000 + int(scenario_id), limit),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["actual_prompt_steps"] = _loads_json(item.pop("actual_prompt_steps_json"), [])
            item["interaction_log"] = _loads_json(item.get("interaction_log"), [])
            results.append(item)
        return results

    def list_benchmark_media(self, *, source_type: Optional[str] = None, scenario_id: Optional[int] = None) -> list[dict[str, Any]]:
        query = """
            SELECT
                m.*,
                bs.source_name,
                bs.source_type,
                bs.benchmark_family,
                s.title AS scenario_title,
                s.category_name,
                s.subcategory_name,
                s.objective_text
            FROM benchmark_media m
            INNER JOIN benchmark_source bs ON bs.id = m.benchmark_source_id
            LEFT JOIN benchmark_scenario s ON s.id = m.scenario_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        if source_type:
            query += " AND bs.source_type = ?"
            params.append(source_type)
        if scenario_id:
            query += " AND m.scenario_id = ?"
            params.append(scenario_id)
        query += " ORDER BY bs.created_at DESC, m.sort_order, m.id"
        with closing(self._connect()) as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def get_benchmark_taxonomy(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT category_name, subcategory_name, COUNT(*) AS scenario_count
                FROM benchmark_scenario
                GROUP BY category_name, subcategory_name
                ORDER BY category_name, subcategory_name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_benchmark_replay_run(
        self,
        *,
        scenario_id: int,
        target_info: dict[str, Any],
        execution_profile: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        scenario = self.get_benchmark_scenario(scenario_id)
        if scenario is None or not scenario.get("replay_supported"):
            return None
        test_id = self._ensure_benchmark_audit_test(scenario)
        tests = self.list_tests(test_ids=[test_id], source_origins=None, include_variants=False)
        if not tests:
            return None
        test = tests[0]
        execution_item = {
            "test_id": int(test["id"]),
            "variant_id": None,
            "result_label": "Benchmark Scenario",
            "variant_name": None,
            "category_name": test["source_sheet_name"],
            "domain": test.get("domain"),
            "severity": test["severity"],
            "test_identifier": test["test_identifier"],
            "workbook_row_id": int(test["workbook_row_id"]),
            "attack_type": test["attack_type"],
            "test_objective": test["test_objective"],
            "original_workbook_prompt": test["prompt_sequence"],
            "actual_prompt_sequence": test["prompt_sequence"],
            "actual_prompt_steps": test["prompt_steps"],
            "expected_behavior_snapshot": test["expected_behavior"],
            "original_result_guidance_snapshot": test.get("original_result_guidance"),
            "benchmark_scenario_id": int(scenario["id"]),
        }
        return self.create_run(
            category_names=[scenario["category_name"]],
            target_info=target_info,
            execution_items=[execution_item],
            execution_profile=execution_profile,
        )

    def _ensure_benchmark_audit_test(self, scenario: dict[str, Any]) -> int:
        category_name = str(scenario.get("category_name") or "Benchmark")
        category_id = self.ensure_category(category_name, source_sheet_name=category_name)
        prompt_text = str(scenario.get("prompt_text") or "").strip()
        if not prompt_text:
            raise ValueError("Benchmark scenario does not contain replayable prompt text")
        record = {
            "category_id": category_id,
            "workbook_row_id": 1_000_000 + int(scenario["id"]),
            "attack_type": scenario["title"],
            "test_objective": scenario.get("objective_text") or scenario["title"],
            "prompt_sequence": prompt_text,
            "prompt_steps": self._parse_prompt_steps(prompt_text),
            "supporting_documents": {
                "benchmark_source_id": scenario["benchmark_source_id"],
                "benchmark_scenario_id": scenario["id"],
                "benchmark_family": scenario.get("benchmark_family"),
                "source_name": scenario.get("source_name"),
                "reference_data_notice": "Public benchmark reference data; not client evidence.",
            },
            "expected_behavior": scenario.get("expected_behavior_text") or "Evaluate response against the public benchmark objective and policy expectation.",
            "original_result_guidance": "Public benchmark reference scenario. Compare client target behavior against the referenced benchmark metadata.",
            "domain": None,
            "severity": scenario.get("severity_hint") or "MEDIUM",
            "source_origin": "benchmark",
        }
        return self.upsert_test(record)

    @staticmethod
    def _deserialize_benchmark_source(item: dict[str, Any]) -> dict[str, Any]:
        item["metadata"] = _loads_json(item.pop("metadata_json", None), {})
        return item

    @staticmethod
    def _deserialize_benchmark_scenario(item: dict[str, Any]) -> dict[str, Any]:
        item["recommended_target_types"] = _loads_json(item.get("recommended_target_types"), [])
        item["tags"] = _loads_json(item.get("tags"), [])
        item["replay_supported"] = bool(item.get("replay_supported"))
        if "source_metadata_json" in item:
            item["source_metadata"] = _loads_json(item.pop("source_metadata_json"), {})
        return item

    def _recalculate_run_summary(self, conn: sqlite3.Connection, run_id: str) -> None:
        summary = conn.execute(
            """
            SELECT
                COUNT(*) AS total_tests,
                SUM(CASE WHEN execution_status IN ('completed', 'error') THEN 1 ELSE 0 END) AS completed_tests,
                SUM(CASE WHEN score_status = 'PASS' THEN 1 ELSE 0 END) AS pass_count,
                SUM(CASE WHEN score_status = 'WARN' THEN 1 ELSE 0 END) AS warn_count,
                SUM(CASE WHEN score_status = 'FAIL' THEN 1 ELSE 0 END) AS fail_count,
                SUM(CASE WHEN score_status IN ('ERROR', 'INVALID_TEST_INPUT') THEN 1 ELSE 0 END) AS error_count
            FROM audit_results
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        now = _utc_now()
        conn.execute(
            """
            UPDATE audit_runs
            SET total_tests = ?,
                completed_tests = ?,
                pass_count = ?,
                warn_count = ?,
                fail_count = ?,
                error_count = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                int(summary["total_tests"] or 0),
                int(summary["completed_tests"] or 0),
                int(summary["pass_count"] or 0),
                int(summary["warn_count"] or 0),
                int(summary["fail_count"] or 0),
                int(summary["error_count"] or 0),
                now,
                run_id,
            ),
        )

    @staticmethod
    def _make_test_identifier(source_sheet_name: str, workbook_row_id: int) -> str:
        return f"{source_sheet_name.strip()}::{workbook_row_id}"

    @staticmethod
    def _parse_prompt_steps(prompt_sequence: str) -> list[str]:
        matches = list(re.finditer(r"Prompt\s*(\d+)\.\s*", prompt_sequence, flags=re.IGNORECASE))
        if not matches:
            parts = [part.strip() for part in prompt_sequence.splitlines() if part.strip()]
            return parts if parts else [prompt_sequence.strip()] if prompt_sequence.strip() else []

        steps: list[str] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(prompt_sequence)
            step = prompt_sequence[start:end].strip()
            if step:
                steps.append(step)
        return steps

    def _deserialize_result_row(self, item: dict[str, Any]) -> dict[str, Any]:
        item["actual_prompt_steps"] = _loads_json(item.pop("actual_prompt_steps_json"), [])
        item["supporting_documents_snapshot"] = _loads_json(item.get("supporting_documents_snapshot"), {})
        item["interaction_log"] = _loads_json(item.get("interaction_log"), [])
        item["attack_detected"] = _bool_from_db(item.get("attack_detected"))
        item["transient_prompt_used"] = bool(item.get("transient_prompt_used"))
        item["industry_type"] = self._normalize_industry_type(item.get("industry_type"))
        for key in (
            "prompt_attack_assessment",
            "response_behavior_assessment",
            "refusal_strength_assessment",
            "scenario_verdict_assessment",
        ):
            item[key] = _loads_json(item.get(key), {})
        for key, default in (
            ("matched_rules", []),
            ("detected_entities", []),
            ("evidence_spans", []),
            ("context_references", {}),
        ):
            item[key] = _loads_json(item.get(key), default)
        prompt_source_type = item.get("prompt_source_type")
        if not prompt_source_type:
            if item.get("variant_id"):
                prompt_source_type = "variant"
            else:
                prompt_source_type = "base"
        if prompt_source_type == "excel":
            prompt_source_type = "base"
        item["prompt_source_type"] = prompt_source_type
        item["prompt_variant"] = item.get("prompt_variant") or ("Adversarial" if prompt_source_type == "adversarial" else "Base")
        item["prompt_source_label"] = item.get("prompt_source_label") or self._prompt_source_label_for_item(item)
        item["execution_scope_label"] = item.get("execution_scope_label") or self._execution_scope_label_for_item(item)
        item["variant_group_key"] = item.get("variant_group_key") or self._variant_group_key_for_item(item)
        return item

    def _deserialize_stability_run(self, item: dict[str, Any]) -> dict[str, Any]:
        item["is_worst_case"] = bool(item.get("is_worst_case"))
        item["is_best_case"] = bool(item.get("is_best_case"))
        for key in (
            "prompt_attack_assessment",
            "response_behavior_assessment",
            "refusal_strength_assessment",
            "scenario_verdict_assessment",
        ):
            item[key] = _loads_json(item.get(key), {})
        for key, default in (
            ("matched_rules", []),
            ("detected_entities", []),
            ("evidence_spans", []),
            ("context_references", {}),
        ):
            item[key] = _loads_json(item.get(key), default)
        return item

    def _deserialize_run(self, item: dict[str, Any]) -> dict[str, Any]:
        item["selected_industries"] = _loads_json(item.get("selected_industries"), [])
        item["selected_categories"] = _loads_json(item.get("selected_categories"), [])
        item["selected_test_ids"] = _loads_json(item.get("selected_test_ids"), [])
        item["selected_variant_ids"] = _loads_json(item.get("selected_variant_ids"), [])
        item["supports_multi_turn"] = bool(item["supports_multi_turn"])
        return item

    def _migrate_legacy_schema(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "audit_tests"):
            return

        existing_columns = self._get_columns(conn, "audit_tests")
        if "workbook_row_id" in existing_columns:
            return

        backup_map: dict[str, str] = {}
        for table in ("audit_categories", "audit_tests", "audit_runs", "audit_results"):
            if self._table_exists(conn, table):
                backup_name = self._next_backup_name(conn, table)
                conn.execute(f"ALTER TABLE {table} RENAME TO {backup_name}")
                backup_map[table] = backup_name

        conn.executescript(SCHEMA_SQL)

        now = _utc_now()
        if "audit_categories" in backup_map:
            conn.execute(
                f"""
                INSERT INTO audit_categories (id, name, source_sheet_name, created_at)
                SELECT id, TRIM(name), name, COALESCE(created_at, '{now}')
                FROM {backup_map['audit_categories']}
                """
            )

        if "audit_tests" in backup_map:
            conn.execute(
                f"""
                INSERT INTO audit_tests (
                    id,
                    category_id,
                    workbook_row_id,
                    industry_type,
                    category_label,
                    attack_type,
                    test_objective,
                    prompt_sequence,
                    prompt_steps_json,
                    adversarial_prompt_sequence,
                    adversarial_prompt_steps_json,
                    supporting_documents,
                    expected_behavior,
                    original_result_guidance,
                    domain,
                    severity,
                    source_origin,
                    is_active,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    category_id,
                    source_row,
                    'Generic',
                    NULL,
                    attack_type,
                    test_objective,
                    prompt_sequence,
                    prompt_steps_json,
                    NULL,
                    NULL,
                    supporting_documents,
                    expected_behavior,
                    scoring_guidance,
                    NULL,
                    severity,
                    'workbook',
                    is_active,
                    COALESCE(created_at, '{now}'),
                    COALESCE(updated_at, '{now}')
                FROM {backup_map['audit_tests']}
                """
            )

        if "audit_runs" in backup_map:
            conn.execute(
                f"""
                INSERT INTO audit_runs (
                    id,
                    target_id,
                    target_registry_name,
                    target_type,
                    model_name,
                    endpoint,
                    supports_multi_turn,
                    status,
                    selected_industries,
                    selected_categories,
                    selected_test_ids,
                    selected_variant_ids,
                    total_tests,
                    completed_tests,
                    pass_count,
                    warn_count,
                    fail_count,
                    error_count,
                    created_at,
                    started_at,
                    completed_at,
                    updated_at,
                    error_message
                )
                SELECT
                    id,
                    target_registry_name,
                    target_registry_name,
                    target_type,
                    model_name,
                    endpoint,
                    supports_multi_turn,
                    status,
                    '[]',
                    selected_categories,
                    '[]',
                    '[]',
                    total_tests,
                    completed_tests,
                    safe_count,
                    partial_count,
                    violation_count,
                    error_count,
                    created_at,
                    started_at,
                    completed_at,
                    updated_at,
                    error_message
                FROM {backup_map['audit_runs']}
                """
            )

        if "audit_results" in backup_map:
            conn.execute(
                f"""
                INSERT INTO audit_results (
                    id,
                    run_id,
                    test_id,
                    variant_id,
                    display_order,
                    result_label,
                    variant_name,
                    category_name,
                    domain,
                    severity,
                    test_identifier,
                    workbook_row_id,
                    attack_type,
                    test_objective,
                    original_workbook_prompt,
                    actual_prompt_sequence,
                    actual_prompt_steps_json,
                    prompt_sent,
                    response_received,
                    expected_behavior_snapshot,
                    original_result_guidance_snapshot,
                    score_status,
                    risk_level,
                    score_value,
                    score_reason,
                    audit_reasoning,
                    interaction_log,
                    execution_status,
                    attack_result_id,
                    conversation_id,
                    created_at,
                    started_at,
                    completed_at
                )
                SELECT
                    r.id,
                    r.run_id,
                    r.test_id,
                    NULL,
                    r.display_order,
                    'Base Test',
                    NULL,
                    r.category_name,
                    NULL,
                    r.severity,
                    c.name || '::' || t.source_row,
                    COALESCE(t.source_row, 0),
                    r.attack_type,
                    COALESCE(t.test_objective, ''),
                    r.prompt_sequence,
                    r.prompt_sequence,
                    r.prompt_steps_json,
                    r.prompt_sequence,
                    r.response_text,
                    r.expected_behavior,
                    r.scoring_guidance,
                    CASE
                        WHEN r.status IN ('SAFE', 'PASS') THEN 'PASS'
                        WHEN r.status IN ('PARTIAL', 'WARN') THEN 'WARN'
                        WHEN r.status IN ('VIOLATION', 'FAIL') THEN 'FAIL'
                        ELSE r.status
                    END,
                    r.risk,
                    r.score,
                    r.reason,
                    r.reason,
                    r.interaction_log,
                    r.execution_status,
                    r.attack_result_id,
                    r.conversation_id,
                    COALESCE(r.started_at, r.completed_at, '{now}'),
                    r.started_at,
                    r.completed_at
                FROM {backup_map['audit_results']} r
                LEFT JOIN {backup_map['audit_tests']} t ON t.id = r.test_id
                LEFT JOIN {backup_map['audit_categories']} c ON c.id = t.category_id
                """
            )

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _get_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def _next_backup_name(self, conn: sqlite3.Connection, table_name: str) -> str:
        suffix = "legacy_pre_fidelity_fix"
        candidate = f"{table_name}_{suffix}"
        index = 1
        while self._table_exists(conn, candidate):
            index += 1
            candidate = f"{table_name}_{suffix}_{index}"
        return candidate

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
