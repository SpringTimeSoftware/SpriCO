# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""Audit API routes backed by workbook-faithful SQLite data."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
import yaml

from audit.auditspec import AuditSpecValidationError, parse_auditspec_content
from audit.benchmark_importer import parse_flipattack_artifact
from audit.database import AuditDatabase
from audit.executor import AuditExecutor
from audit.grounding import evaluate_grounding, extract_retrieval_evidence_from_message
from audit.import_excel import import_workbook
from audit.scorer import describe_expected_behavior_profile, evaluate_response
from audit.stability import aggregate_runs
from pyrit.backend.services.attack_service import get_attack_service
from pyrit.backend.services.target_service import get_target_service
from pyrit.backend.sprico.evidence_store import SpriCOEvidenceStore
from pyrit.backend.sprico.findings import SpriCOFindingStore, finding_requires_action
from pyrit.backend.sprico.policy_store import SpriCOPolicyStore
from pyrit.backend.sprico.runs import SpriCORunRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])
repository = AuditDatabase()
repository.initialize()
_interactive_evidence_store = SpriCOEvidenceStore()
_finding_store = SpriCOFindingStore(evidence_store=_interactive_evidence_store)
_run_registry = SpriCORunRegistry(evidence_store=_interactive_evidence_store, finding_store=_finding_store)
_policy_store = SpriCOPolicyStore()


class AuditOption(BaseModel):
    name: str
    source_sheet_name: Optional[str] = None
    test_count: int


class AuditOptionsResponse(BaseModel):
    industries: list[AuditOption]
    categories: list[AuditOption]
    domains: list[AuditOption]
    has_real_domains: bool
    total_tests: int
    database_path: str


class WorkbookImportResponse(BaseModel):
    workbook_name: str
    source_label: Optional[str] = None
    industry_type: str
    imported_rows: int
    per_sheet_counts: dict[str, int]
    has_real_domain_column: bool
    database_path: str


class AuditVariantResponse(BaseModel):
    id: int
    parent_test_id: int
    variant_name: str
    edited_prompt_sequence: str
    edited_prompt_steps: list[str]
    edited_expected_behavior: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str
    updated_at: str
    test_label: str


class AuditTestResponse(BaseModel):
    id: int
    test_identifier: str
    workbook_row_id: int
    industry_type: str
    category_name: str
    source_sheet_name: str
    name: str
    attack_type: str
    test_objective: str
    canonical_question: Optional[str] = None
    prompt_sequence: str
    prompt_steps: list[str]
    base_prompt_sequence: str
    base_prompt_steps: list[str]
    adversarial_prompt_sequence: Optional[str] = None
    adversarial_prompt_steps: list[str] = Field(default_factory=list)
    safe_base_prompt_sequence: Optional[str] = None
    unsafe_base_prompt_sequence: Optional[str] = None
    safe_adversarial_prompt_sequence: Optional[str] = None
    unsafe_adversarial_prompt_sequence: Optional[str] = None
    has_adversarial_prompt: bool = False
    expected_behavior: str
    expected_answer: Optional[str] = None
    original_result_guidance: Optional[str] = None
    domain: Optional[str] = None
    severity: str
    source_origin: str
    test_label: str
    supporting_documents: dict[str, Any] = Field(default_factory=dict)
    variants: list[AuditVariantResponse] = Field(default_factory=list)


class CreateAuditVariantRequest(BaseModel):
    variant_name: str
    edited_prompt_sequence: str
    edited_expected_behavior: Optional[str] = None
    created_by: Optional[str] = None


class AuditExecutionProfileRequest(BaseModel):
    mode_code: str = "COMPLIANCE"
    provider_name: Optional[str] = None
    api_style: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = 1.0
    top_k: Optional[int] = None
    fixed_seed: bool = True
    base_seed: Optional[int] = None
    seed_strategy: Optional[str] = "FIXED"
    max_tokens: Optional[int] = None
    run_count_requested: int = Field(default=1, ge=1, le=25)
    variability_mode: bool = False
    created_by: Optional[str] = None


class CreateAuditRunRequest(BaseModel):
    industries: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    test_ids: list[int] = Field(default_factory=list)
    variant_ids: list[int] = Field(default_factory=list)
    prompt_source_mode: Optional[str] = None
    transient_prompt_sequence: Optional[str] = None
    transient_expected_behavior: Optional[str] = None
    selected_test_id_for_transient_run: Optional[int] = None
    target_registry_name: str
    policy_id: Optional[str] = None
    run_source: Optional[str] = "audit_workstation"
    allow_text_target: bool = False
    execution_profile: Optional[AuditExecutionProfileRequest] = None


class AuditResultRow(BaseModel):
    id: int
    test_id: int
    variant_id: Optional[int] = None
    display_order: int
    result_label: str
    variant_name: Optional[str] = None
    prompt_source_type: Optional[str] = None
    prompt_source_label: Optional[str] = None
    prompt_variant: Optional[str] = None
    run_source: Optional[str] = None
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None
    suite_id: Optional[str] = None
    suite_test_id: Optional[str] = None
    suite_name: Optional[str] = None
    assertion_results: list[dict[str, Any]] = Field(default_factory=list)
    assertion_summary: Optional[str] = None
    transient_prompt_used: bool = False
    execution_scope_label: Optional[str] = None
    variant_group_key: Optional[str] = None
    editor_snapshot: Optional[str] = None
    industry_type: str = "Generic"
    category_name: str
    domain: Optional[str] = None
    severity: str
    test_identifier: str
    workbook_row_id: int
    attack_type: str
    test_objective: str
    original_workbook_prompt: str
    actual_prompt_sequence: str
    actual_prompt_steps: list[str]
    prompt_sent: Optional[str] = None
    response_received: Optional[str] = None
    expected_behavior_snapshot: str
    original_result_guidance_snapshot: Optional[str] = None
    score_status: Optional[str] = None
    risk_level: Optional[str] = None
    score_value: Optional[int] = None
    score_reason: Optional[str] = None
    audit_reasoning: Optional[str] = None
    attack_detected: Optional[bool] = None
    attack_family: Optional[str] = None
    attack_subtype: Optional[str] = None
    attack_severity_potential: Optional[str] = None
    policy_domain: Optional[str] = None
    expected_behavior_profile: Optional[str] = None
    response_behavior_class: Optional[str] = None
    response_safety_label: Optional[str] = None
    response_safety_risk: Optional[str] = None
    attack_outcome: Optional[str] = None
    refusal_strength: Optional[str] = None
    refusal_style: Optional[str] = None
    boundary_clarity: Optional[str] = None
    safe_alternative_quality: Optional[str] = None
    scoring_version: Optional[str] = None
    prompt_attack_assessment: dict[str, Any] = Field(default_factory=dict)
    response_behavior_assessment: dict[str, Any] = Field(default_factory=dict)
    refusal_strength_assessment: dict[str, Any] = Field(default_factory=dict)
    scenario_verdict_assessment: dict[str, Any] = Field(default_factory=dict)
    attack_intent: Optional[str] = None
    outcome_safety: Optional[str] = None
    refusal_quality: Optional[str] = None
    matched_rules: list[str] = Field(default_factory=list)
    detected_entities: list[dict[str, Any]] = Field(default_factory=list)
    evidence_spans: list[dict[str, Any]] = Field(default_factory=list)
    context_references: dict[str, Any] = Field(default_factory=dict)
    policy_pack: Optional[str] = None
    confidence: Optional[float] = None
    interaction_log: list[dict[str, Any]] = Field(default_factory=list)
    execution_status: str
    attack_result_id: Optional[str] = None
    conversation_id: Optional[str] = None
    stability_group_id: Optional[int] = None
    stability_run_id: Optional[int] = None
    stability_run_no: Optional[int] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class AuditRunResponse(BaseModel):
    id: str
    job_id: str
    target_id: str
    target_registry_name: str
    target_type: str
    model_name: Optional[str] = None
    endpoint: Optional[str] = None
    supports_multi_turn: bool
    run_source: str = "audit_workstation"
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None
    suite_id: Optional[str] = None
    suite_name: Optional[str] = None
    comparison_group_id: Optional[str] = None
    comparison_label: Optional[str] = None
    comparison_mode: Optional[str] = None
    run_metadata: dict[str, Any] = Field(default_factory=dict)
    status: str
    selected_industries: list[str]
    selected_categories: list[str]
    selected_test_ids: list[int]
    selected_variant_ids: list[int]
    total_tests: int
    completed_tests: int
    pass_count: int
    warn_count: int
    fail_count: int
    progress_percent: float
    error_count: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: str
    error_message: Optional[str] = None
    results: list[AuditResultRow] = Field(default_factory=list)


class InteractiveAuditTurnResponse(BaseModel):
    assistant_turn_number: int
    prompt_sequence: str
    latest_user_prompt: Optional[str] = None
    response_text: str
    expected_behavior_text: str
    attack_detected: bool
    attack_family: Optional[str] = None
    attack_subtype: Optional[str] = None
    expected_behavior_profile: Optional[str] = None
    response_behavior_class: Optional[str] = None
    response_safety_label: Optional[str] = None
    response_safety_risk: Optional[str] = None
    refusal_strength: Optional[str] = None
    attack_outcome: Optional[str] = None
    compliance_verdict: str
    final_risk_level: str
    score: int
    short_reason: str
    full_reason: str
    scoring_version: str
    grounding_verdict: Optional[str] = None
    grounding_risk: Optional[str] = None
    grounding_reason: Optional[str] = None
    grounding_assessment: dict[str, Any] = Field(default_factory=dict)
    prompt_attack_assessment: dict[str, Any] = Field(default_factory=dict)
    response_behavior_assessment: dict[str, Any] = Field(default_factory=dict)
    refusal_strength_assessment: dict[str, Any] = Field(default_factory=dict)
    scenario_verdict_assessment: dict[str, Any] = Field(default_factory=dict)
    attack_intent: Optional[str] = None
    outcome_safety: Optional[str] = None
    refusal_quality: Optional[str] = None
    matched_rules: list[str] = Field(default_factory=list)
    detected_entities: list[dict[str, Any]] = Field(default_factory=list)
    evidence_spans: list[dict[str, Any]] = Field(default_factory=list)
    context_references: dict[str, Any] = Field(default_factory=dict)
    policy_pack: Optional[str] = None
    confidence: Optional[float] = None
    evidence_item_id: Optional[str] = None


class InteractiveAuditSessionSummary(BaseModel):
    total_assistant_turns: int
    pass_count: int
    warn_count: int
    fail_count: int
    pass_rate: float
    warn_rate: float
    fail_rate: float
    safe_rate: float
    attack_success_rate: float
    resistance_rate: float
    aggregate_verdict: str
    aggregate_risk_level: str
    stability_score: float
    variance_score: float
    summary_reasoning: str
    scoring_version: str


class InteractiveAuditConversationResponse(BaseModel):
    attack_result_id: str
    conversation_id: str
    structured_run_id: Optional[str] = None
    attack_type: Optional[str] = None
    target_registry_name: Optional[str] = None
    target_type: Optional[str] = None
    model_name: Optional[str] = None
    endpoint: Optional[str] = None
    linked_audit_context: dict[str, Any] = Field(default_factory=dict)
    turns: list[InteractiveAuditTurnResponse] = Field(default_factory=list)
    session_summary: InteractiveAuditSessionSummary


class DashboardTotals(BaseModel):
    run_count: int
    total_tests: int
    pass_count: int
    warn_count: int
    fail_count: int
    safe_count: int
    partial_count: int
    violation_count: int
    finding_count: int
    pass_rate: float
    critical_findings: int
    error_count: int


class ViolationsByCategory(BaseModel):
    category_name: str
    violations: int
    partials: int
    safe: int
    total: int


class RiskDistributionItem(BaseModel):
    risk: str
    count: int


class SeverityDistributionItem(BaseModel):
    severity: str
    count: int
    total_count: int


class HeatmapCell(BaseModel):
    category_name: str
    severity: str
    count: int
    total_count: int


class AuditDashboardResponse(BaseModel):
    totals: DashboardTotals
    violations_by_category: list[ViolationsByCategory]
    risk_distribution: list[RiskDistributionItem]
    severity_distribution: list[SeverityDistributionItem]
    heatmap: list[HeatmapCell]
    recent_runs: list[AuditRunResponse]


class HeatmapDashboardTotals(BaseModel):
    run_count: int
    total_tests: int
    pass_count: int
    warn_count: int
    fail_count: int
    pass_rate: float
    model_count: int
    target_count: int


class RunLabel(BaseModel):
    run_id: str
    label: str
    model_name: Optional[str] = None
    completed_at: str


class PassRateMatrixCell(BaseModel):
    category_name: str
    run_id: str
    total_count: int
    finding_count: int
    pass_rate: Optional[float] = None
    drilldown_supported: bool


class ActivityHeatmapCell(BaseModel):
    activity_date: str
    run_count: int
    total_tests: int
    finding_count: int
    failure_density: float
    single_run_id: Optional[str] = None
    drilldown_supported: bool
    drilldown_reason: Optional[str] = None


class ModelHeatmapCell(BaseModel):
    test_identifier: str
    attack_type: str
    category_name: str
    model_name: str
    pass_count: int
    warn_count: int
    fail_count: int
    result_count: int
    dominant_status: str
    drilldown_run_id: Optional[str] = None
    drilldown_supported: bool


class RiskScoreDistributionPoint(BaseModel):
    category_name: str
    score_bucket: int
    avg_score: float
    result_count: int
    finding_count: int
    failure_density: float


class HeatmapDashboardResponse(BaseModel):
    totals: HeatmapDashboardTotals
    category_severity_matrix: list[HeatmapCell]
    run_labels: list[RunLabel]
    category_run_pass_rate: list[PassRateMatrixCell]
    activity_heatmap: list[ActivityHeatmapCell]
    model_names: list[str]
    test_model_matrix: list[ModelHeatmapCell]
    risk_score_distribution: list[RiskScoreDistributionPoint]
    recent_runs: list[AuditRunResponse]


class TargetCapabilityResponse(BaseModel):
    id: int
    target_code: str
    display_name: str
    api_style: str
    modality: str
    supports_deterministic_seed: bool
    supports_temperature: bool
    supports_multi_run: bool
    best_for: str
    not_suitable_for: str
    example_scenarios: str
    provider_examples: str
    is_builtin: bool
    sort_order: int


class StabilitySummaryResponse(BaseModel):
    total_groups: int
    avg_stability_score: float
    avg_fail_rate: float
    worst_category: Optional[str] = None
    most_unstable_target: Optional[str] = None
    worst_case_fail_count: int


class StabilityCategoryRow(BaseModel):
    category_name: Optional[str] = None
    group_count: int
    avg_stability_score: Optional[float] = None
    avg_fail_rate: Optional[float] = None
    fail_groups: int = 0
    warn_groups: int = 0


class StabilityTargetRow(BaseModel):
    target_name: Optional[str] = None
    group_count: int
    avg_stability_score: Optional[float] = None
    avg_fail_rate: Optional[float] = None


class StabilityModeRow(BaseModel):
    mode_code: str
    group_count: int
    avg_stability_score: Optional[float] = None
    avg_fail_rate: Optional[float] = None


class StabilityGroupRow(BaseModel):
    id: int
    audit_session_id: str
    execution_profile_id: int
    prompt_source_type: str
    prompt_source_ref: Optional[str] = None
    benchmark_scenario_id: Optional[int] = None
    category_code: Optional[str] = None
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None
    severity_expected: Optional[str] = None
    expected_behavior_text: Optional[str] = None
    objective_text: Optional[str] = None
    run_count_actual: int
    aggregate_verdict: Optional[str] = None
    aggregate_risk_level: Optional[str] = None
    pass_rate: Optional[float] = None
    warn_rate: Optional[float] = None
    fail_rate: Optional[float] = None
    safe_rate: Optional[float] = None
    attack_success_rate: Optional[float] = None
    resistance_rate: Optional[float] = None
    variance_score: Optional[float] = None
    stability_score: Optional[float] = None
    worst_case_verdict: Optional[str] = None
    worst_case_risk_level: Optional[str] = None
    best_case_verdict: Optional[str] = None
    summary_reasoning: Optional[str] = None
    created_at: str
    mode_code: str
    model_target_type: Optional[str] = None
    model_target_name: Optional[str] = None
    provider_name: Optional[str] = None
    api_style: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    fixed_seed: bool
    base_seed: Optional[int] = None
    seed_strategy: Optional[str] = None
    max_tokens: Optional[int] = None
    run_count_requested: int
    variability_mode: bool
    target_registry_name: str
    model_name: Optional[str] = None
    endpoint: Optional[str] = None
    completed_at: Optional[str] = None
    session_created_at: str


class StabilityRunRow(BaseModel):
    id: int
    result_group_id: int
    run_no: int
    seed_used: Optional[int] = None
    temperature_used: Optional[float] = None
    top_p_used: Optional[float] = None
    top_k_used: Optional[int] = None
    request_payload_hash: Optional[str] = None
    context_hash: Optional[str] = None
    system_prompt_hash: Optional[str] = None
    prompt_text: Optional[str] = None
    normalized_prompt_text: Optional[str] = None
    raw_response_text: Optional[str] = None
    normalized_response_text: Optional[str] = None
    response_latency_ms: Optional[int] = None
    token_input_count: Optional[int] = None
    token_output_count: Optional[int] = None
    evaluator_safety_label: Optional[str] = None
    evaluator_safety_risk: Optional[str] = None
    evaluator_compliance_label: Optional[str] = None
    attack_family: Optional[str] = None
    attack_subtype: Optional[str] = None
    attack_severity_potential: Optional[str] = None
    policy_domain: Optional[str] = None
    expected_behavior_profile: Optional[str] = None
    response_behavior_class: Optional[str] = None
    attack_outcome: Optional[str] = None
    refusal_strength: Optional[str] = None
    refusal_style: Optional[str] = None
    boundary_clarity: Optional[str] = None
    safe_alternative_quality: Optional[str] = None
    evaluator_reasoning: Optional[str] = None
    scoring_version: Optional[str] = None
    prompt_attack_assessment: dict[str, Any] = Field(default_factory=dict)
    response_behavior_assessment: dict[str, Any] = Field(default_factory=dict)
    refusal_strength_assessment: dict[str, Any] = Field(default_factory=dict)
    scenario_verdict_assessment: dict[str, Any] = Field(default_factory=dict)
    is_worst_case: bool
    is_best_case: bool
    run_status: str
    created_at: str
    retrieval_traces: list[dict[str, Any]] = Field(default_factory=list)


class StabilityDashboardResponse(BaseModel):
    summary: StabilitySummaryResponse
    by_category: list[StabilityCategoryRow]
    by_target: list[StabilityTargetRow]
    by_mode: list[StabilityModeRow]
    groups: list[StabilityGroupRow]


class StabilityGroupDetailResponse(BaseModel):
    group: StabilityGroupRow
    runs: list[StabilityRunRow]


class RetrievalTraceResponse(BaseModel):
    id: int
    run_id: int
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    document_type: Optional[str] = None
    page_no: Optional[int] = None
    chunk_id: Optional[str] = None
    ocr_used: bool
    retrieved_text_excerpt: Optional[str] = None
    retrieval_rank: Optional[int] = None
    retrieval_score: Optional[float] = None
    source_uri: Optional[str] = None
    citation_label: Optional[str] = None


class CreateRetrievalTraceRequest(BaseModel):
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    document_type: Optional[str] = None
    page_no: Optional[int] = None
    chunk_id: Optional[str] = None
    ocr_used: bool = False
    retrieved_text_excerpt: Optional[str] = None
    retrieval_rank: Optional[int] = None
    retrieval_score: Optional[float] = None
    source_uri: Optional[str] = None
    citation_label: Optional[str] = None


class BenchmarkSourceResponse(BaseModel):
    id: int
    source_name: str
    source_type: str
    source_uri: Optional[str] = None
    benchmark_family: Optional[str] = None
    model_name: Optional[str] = None
    version: Optional[str] = None
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None
    scenario_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class BenchmarkScenarioResponse(BaseModel):
    id: int
    benchmark_source_id: int
    scenario_code: str
    title: str
    category_name: str
    subcategory_name: Optional[str] = None
    objective_text: Optional[str] = None
    prompt_text: Optional[str] = None
    expected_behavior_text: Optional[str] = None
    modality: str
    recommended_target_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    severity_hint: Optional[str] = None
    replay_supported: bool
    created_at: str
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    source_uri: Optional[str] = None
    benchmark_family: Optional[str] = None
    source_model_name: Optional[str] = None
    source_version: Optional[str] = None
    source_title: Optional[str] = None
    source_description: Optional[str] = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkMediaResponse(BaseModel):
    id: int
    benchmark_source_id: int
    scenario_id: Optional[int] = None
    media_type: str
    media_uri: str
    thumbnail_uri: Optional[str] = None
    caption: Optional[str] = None
    sort_order: int
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    benchmark_family: Optional[str] = None
    scenario_title: Optional[str] = None
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None
    objective_text: Optional[str] = None


class BenchmarkTaxonomyRow(BaseModel):
    category_name: str
    subcategory_name: Optional[str] = None
    scenario_count: int


class CreateBenchmarkSourceRequest(BaseModel):
    source: dict[str, Any]
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    media: list[dict[str, Any]] = Field(default_factory=list)


class FlipAttackImportRequest(BaseModel):
    payload: dict[str, Any]
    source_type: str = "public_json"


class BenchmarkReplayRequest(BaseModel):
    target_registry_name: str
    allow_text_target: bool = False
    execution_profile: Optional[AuditExecutionProfileRequest] = None


class BenchmarkCompareResponse(BaseModel):
    scenario: BenchmarkScenarioResponse
    public_model_result: dict[str, Any] = Field(default_factory=dict)
    client_target_results: list[AuditResultRow] = Field(default_factory=list)
    delta: str
    replay_supported: bool


class BenchmarkLibraryResponse(BaseModel):
    sources: list[BenchmarkSourceResponse]
    scenarios: list[BenchmarkScenarioResponse]
    media: list[BenchmarkMediaResponse]
    taxonomy: list[BenchmarkTaxonomyRow]


class AuditSpecSuiteResponse(BaseModel):
    suite_id: str
    name: str
    description: Optional[str] = None
    domain: str
    policy_id: Optional[str] = None
    target_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    severity: str = "MEDIUM"
    expected_behavior: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tests: list[dict[str, Any]] = Field(default_factory=list)
    format: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    test_count: Optional[int] = None


class AuditSpecImportRequest(BaseModel):
    content: str


class AuditSpecValidateResponse(BaseModel):
    format: str
    suite: AuditSpecSuiteResponse


class AuditSpecRunRequest(BaseModel):
    suite_id: str
    comparison_mode: str = "single_target"
    candidate_suite_id: Optional[str] = None
    target_ids: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    baseline_label: Optional[str] = None
    candidate_label: Optional[str] = None
    execution_profile: Optional[AuditExecutionProfileRequest] = None


class AuditSpecRunLaunchResponse(BaseModel):
    comparison_group_id: str
    comparison_mode: str
    runs: list[AuditRunResponse]


def _serialize_run(run: dict[str, Any], *, include_results: bool) -> dict[str, Any]:
    total_tests = int(run.get("total_tests") or 0)
    completed_tests = int(run.get("completed_tests") or 0)
    progress_percent = round((completed_tests / total_tests) * 100, 2) if total_tests else 0.0
    return {
        **run,
        "job_id": run["id"],
        "progress_percent": progress_percent,
        "results": run.get("results", []) if include_results else [],
    }


def _validate_prompt_source_mode(request: CreateAuditRunRequest) -> None:
    mode = (request.prompt_source_mode or "").strip().lower()
    if not mode:
        return
    if mode not in {"base", "adversarial", "both", "current_edit", "selected_variant", "base_and_variant", "all_variants"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported prompt_source_mode '{request.prompt_source_mode}'.")

    if mode == "current_edit":
        if request.selected_test_id_for_transient_run is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current edited prompt runs require a selected workbook test.")
        if not str(request.transient_prompt_sequence or "").strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current edited prompt runs require a non-empty transient prompt sequence.")
        return

    if mode == "selected_variant" and not request.variant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected saved variant runs require at least one saved variant.")

    if mode == "base_and_variant":
        if not request.test_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base + selected variant runs require at least one base workbook test.")
        if not request.variant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base + selected variant runs require at least one saved variant.")

    if mode == "adversarial" and not (request.test_ids or request.categories or request.domains or request.industries):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Adversarial runs require selected tests or workbook filters.")

    if mode == "both" and not (request.test_ids or request.categories or request.domains or request.industries):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base + adversarial runs require selected tests or workbook filters.")

    if mode == "all_variants" and not (request.test_ids or request.categories or request.domains or request.industries):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All active variants runs require selected base tests or category filters to expand variants.")


def _flatten_interactive_message(message: Any) -> str:
    parts: list[str] = []
    for piece in getattr(message, "pieces", []):
        converted_type = getattr(piece, "converted_value_data_type", None)
        converted = getattr(piece, "converted_value", None)
        original_type = getattr(piece, "original_value_data_type", None)
        original = getattr(piece, "original_value", None)
        if converted_type == "text" and converted:
            parts.append(str(converted))
        elif original_type == "text" and original:
            parts.append(str(original))
    return "\n".join(part for part in parts if part).strip()


def _interactive_prompt_sequence(history: list[tuple[str, str]]) -> str:
    formatted: list[str] = []
    prompt_index = 1
    for role, content in history:
        if not content:
            continue
        if role == "user":
            formatted.append(f"Prompt {prompt_index}: {content}")
            prompt_index += 1
        else:
            formatted.append(f"{role.title()} Context: {content}")
    return "\n".join(formatted)


def _interactive_target_registry_name(*, attack_result_id: str, attack: Any) -> str:
    target = getattr(attack, "target", None)
    target_type = getattr(target, "target_type", None) or "InteractiveAuditTarget"
    model_name = getattr(target, "model_name", None) or attack_result_id[:8]
    return f"interactive::{target_type}::{model_name}"


def _interactive_target_supports_grounding(*, attack: Any) -> bool:
    target = getattr(attack, "target", None)
    target_type = str(getattr(target, "target_type", "") or "").lower()
    return any(hint in target_type for hint in ("vectorstore", "retrieval", "rag", "filesearch"))


async def _build_interactive_audit_conversation(
    *,
    attack_result_id: str,
    conversation_id: Optional[str],
) -> InteractiveAuditConversationResponse:
    attack_service = get_attack_service()
    attack = await attack_service.get_attack_async(attack_result_id=attack_result_id)
    if not attack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Attack '{attack_result_id}' not found")

    effective_conversation_id = conversation_id or attack.conversation_id
    transcript = await attack_service.get_conversation_messages_async(
        attack_result_id=attack_result_id,
        conversation_id=effective_conversation_id,
    )
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{effective_conversation_id}' not found for attack '{attack_result_id}'",
        )

    linked_context = repository.get_audit_context_for_attack(attack_result_id, effective_conversation_id) or {}
    prompt_history: list[tuple[str, str]] = []
    conversation_history: list[dict[str, Any]] = []
    runs_for_aggregate: list[dict[str, Any]] = []
    turn_rows: list[InteractiveAuditTurnResponse] = []
    last_user_prompt: Optional[str] = None
    grounding_enabled = _interactive_target_supports_grounding(attack=attack)
    target_registry_name = _interactive_target_registry_name(attack_result_id=attack_result_id, attack=attack)

    for message in transcript.messages:
        role = str(getattr(message, "role", "")).lower()
        text = _flatten_interactive_message(message)
        if role in {"user", "system", "developer"}:
            prompt_history.append((role if role != "developer" else "system", text))
            conversation_history.append(
                {
                    "turn_id": str(getattr(message, "id", None) or getattr(message, "turn_number", len(conversation_history) + 1)),
                    "role": role if role != "developer" else "system",
                    "user_prompt": text if role == "user" else "",
                    "content": text,
                }
            )
            if role == "user" and text:
                last_user_prompt = text
            continue
        if role not in {"assistant", "simulated_assistant"} or not text:
            continue

        prompt_sequence = _interactive_prompt_sequence(prompt_history)
        retrieval_evidence = extract_retrieval_evidence_from_message(message)
        grounding_assessment = (
            evaluate_grounding(
                user_prompt=last_user_prompt or prompt_sequence,
                response_text=text,
                retrieval_evidence=retrieval_evidence,
            )
            if grounding_enabled or retrieval_evidence
            else {}
        )
        evaluation = evaluate_response(
            response_text=text,
            expected_behavior=linked_context.get("expected_behavior_snapshot") or "",
            category_name=linked_context.get("category_name") or "Interactive Audit",
            scoring_guidance=linked_context.get("original_result_guidance_snapshot") or "",
            prompt_sequence=prompt_sequence,
            # Evaluate each assistant turn against the prompt history seen so far.
            # Do not force the workbook attack label onto benign setup turns.
            attack_type="Interactive Audit",
            conversation_history=conversation_history,
            grounding_assessment=grounding_assessment,
        )
        expected_behavior_text = linked_context.get("expected_behavior_snapshot") or describe_expected_behavior_profile(
            str(evaluation.get("expected_behavior_profile") or ""),
            "",
        )
        assistant_turn_number = int(getattr(message, "turn_number", len(turn_rows) + 1))
        scoring_version = str(evaluation.get("scoring_version") or "v2")
        context_references = dict(evaluation.get("context_references") or {})
        evidence_item_id = _persist_interactive_audit_turn_evidence(
            attack_result_id=attack_result_id,
            conversation_id=effective_conversation_id,
            assistant_turn_number=assistant_turn_number,
            scoring_version=scoring_version,
            target_registry_name=target_registry_name,
            target_type=getattr(attack.target, "target_type", None),
            model_name=getattr(attack.target, "model_name", None),
            endpoint=getattr(attack.target, "endpoint", None),
            latest_user_prompt=last_user_prompt,
            prompt_sequence=prompt_sequence,
            response_text=text,
            expected_behavior_text=expected_behavior_text,
            evaluation=evaluation,
            conversation_context_window=conversation_history[-8:],
            grounding_assessment=grounding_assessment,
        )
        context_references["evidence_item_id"] = evidence_item_id
        context_references["normalized_evidence_id"] = evidence_item_id
        context_references["conversation_id"] = effective_conversation_id
        turn_rows.append(
            InteractiveAuditTurnResponse(
                assistant_turn_number=assistant_turn_number,
                prompt_sequence=prompt_sequence,
                latest_user_prompt=last_user_prompt,
                response_text=text,
                expected_behavior_text=expected_behavior_text,
                attack_detected=bool(evaluation.get("attack_detected")),
                attack_family=evaluation.get("attack_family"),
                attack_subtype=evaluation.get("attack_subtype"),
                expected_behavior_profile=evaluation.get("expected_behavior_profile"),
                response_behavior_class=evaluation.get("response_behavior_class"),
                response_safety_label=evaluation.get("response_safety_label"),
                response_safety_risk=evaluation.get("response_safety_risk"),
                refusal_strength=evaluation.get("refusal_strength"),
                attack_outcome=evaluation.get("attack_outcome"),
                compliance_verdict=str(evaluation["status"]),
                final_risk_level=str(evaluation["risk"]),
                score=int(evaluation["score"]),
                short_reason=str(evaluation["reason"]),
                full_reason=str(evaluation.get("audit_reasoning") or evaluation["reason"]),
                scoring_version=str(evaluation.get("scoring_version") or "v2"),
                grounding_verdict=grounding_assessment.get("grounding_verdict"),
                grounding_risk=grounding_assessment.get("grounding_risk"),
                grounding_reason=grounding_assessment.get("grounding_reason"),
                grounding_assessment=grounding_assessment,
                prompt_attack_assessment=dict(evaluation.get("prompt_attack_assessment") or {}),
                response_behavior_assessment=dict(evaluation.get("response_behavior_assessment") or {}),
                refusal_strength_assessment=dict(evaluation.get("refusal_strength_assessment") or {}),
                scenario_verdict_assessment=dict(evaluation.get("scenario_verdict_assessment") or {}),
                attack_intent=evaluation.get("attack_intent"),
                outcome_safety=evaluation.get("outcome_safety"),
                refusal_quality=evaluation.get("refusal_quality"),
                matched_rules=list(evaluation.get("matched_rules") or []),
                detected_entities=list(evaluation.get("detected_entities") or []),
                evidence_spans=list(evaluation.get("evidence_spans") or []),
                context_references=context_references,
                policy_pack=evaluation.get("policy_pack"),
                confidence=evaluation.get("confidence"),
                evidence_item_id=evidence_item_id,
            )
        )
        conversation_history.append(
            {
                "turn_id": str(getattr(message, "id", None) or getattr(message, "turn_number", len(conversation_history) + 1)),
                "role": "assistant",
                "assistant_response": text,
                "content": text,
            }
        )
        runs_for_aggregate.append(
            {
                "evaluator_compliance_label": str(evaluation["status"]).upper(),
                "evaluator_safety_label": str(evaluation.get("response_safety_label") or "WARN").upper(),
                "evaluator_safety_risk": str(evaluation.get("response_safety_risk") or evaluation["risk"]).upper(),
                "final_risk_level": str(evaluation["risk"]).upper(),
                "attack_outcome": str(evaluation.get("attack_outcome") or "NEEDS_REVIEW").upper(),
                "refusal_strength": str(evaluation.get("refusal_strength") or "NONE").upper(),
                "raw_response_text": text,
                "run_status": "COMPLETED",
                "run_no": int(getattr(message, "turn_number", len(runs_for_aggregate) + 1)),
            }
        )

    aggregate = aggregate_runs(runs_for_aggregate)
    structured_run_id: Optional[str] = None
    if turn_rows:
        structured_run_id = repository.save_interactive_audit_conversation(
            attack_result_id=attack_result_id,
            conversation_id=effective_conversation_id,
            target_info={
                "target_registry_name": target_registry_name,
                "target_type": getattr(attack.target, "target_type", None),
                "model_name": getattr(attack.target, "model_name", None),
                "endpoint": getattr(attack.target, "endpoint", None),
                "supports_multi_turn": True,
            },
            linked_context=linked_context,
            turns=[turn.model_dump() for turn in turn_rows],
            summary={
                "pass_count": sum(1 for row in turn_rows if row.compliance_verdict.upper() == "PASS"),
                "warn_count": sum(1 for row in turn_rows if row.compliance_verdict.upper() == "WARN"),
                "fail_count": sum(1 for row in turn_rows if row.compliance_verdict.upper() == "FAIL"),
            },
        )

    return InteractiveAuditConversationResponse(
        attack_result_id=attack_result_id,
        conversation_id=effective_conversation_id,
        structured_run_id=structured_run_id,
        attack_type=attack.attack_type,
        target_registry_name=target_registry_name,
        target_type=getattr(attack.target, "target_type", None),
        model_name=getattr(attack.target, "model_name", None),
        endpoint=getattr(attack.target, "endpoint", None),
        linked_audit_context=linked_context,
        turns=turn_rows,
        session_summary=InteractiveAuditSessionSummary(
            total_assistant_turns=len(turn_rows),
            pass_count=sum(1 for row in turn_rows if row.compliance_verdict.upper() == "PASS"),
            warn_count=sum(1 for row in turn_rows if row.compliance_verdict.upper() == "WARN"),
            fail_count=sum(1 for row in turn_rows if row.compliance_verdict.upper() == "FAIL"),
            pass_rate=float(aggregate["pass_rate"]),
            warn_rate=float(aggregate["warn_rate"]),
            fail_rate=float(aggregate["fail_rate"]),
            safe_rate=float(aggregate["safe_rate"]),
            attack_success_rate=float(aggregate["attack_success_rate"]),
            resistance_rate=float(aggregate["resistance_rate"]),
            aggregate_verdict=str(aggregate["aggregate_verdict"]),
            aggregate_risk_level=str(aggregate["aggregate_risk_level"]),
            stability_score=float(aggregate["stability_score"]),
            variance_score=float(aggregate["variance_score"]),
            summary_reasoning=str(aggregate["summary_reasoning"]),
            scoring_version="v2",
        ),
    )


def _build_saved_interactive_audit_conversation(run_id: str) -> InteractiveAuditConversationResponse:
    run = repository.get_run_detail(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit run '{run_id}' not found")

    interactive_results = [
        result for result in run.get("results", [])
        if str(result.get("prompt_source_type") or "").lower() == "interactive"
    ]
    if not interactive_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit run '{run_id}' does not contain saved Interactive Audit turns",
        )

    first_result = interactive_results[0]
    attack_result_id = str(first_result.get("attack_result_id") or run_id)
    conversation_id = str(first_result.get("conversation_id") or run_id)
    turn_rows: list[InteractiveAuditTurnResponse] = []
    runs_for_aggregate: list[dict[str, Any]] = []

    for index, result in enumerate(interactive_results, start=1):
        assistant_turn_number = int(result.get("display_order") or index)
        context_references = dict(result.get("context_references") or {})
        context_references.setdefault("structured_run_id", run_id)
        context_references.setdefault("conversation_id", conversation_id)
        evidence_item_id = (
            context_references.get("evidence_item_id")
            or context_references.get("normalized_evidence_id")
        )
        response_text = str(result.get("response_received") or "")
        compliance_verdict = str(result.get("score_status") or "NEEDS_REVIEW")
        final_risk_level = str(result.get("risk_level") or "MEDIUM")
        scoring_version = str(result.get("scoring_version") or "v2")
        turn_rows.append(
            InteractiveAuditTurnResponse(
                assistant_turn_number=assistant_turn_number,
                prompt_sequence=str(result.get("actual_prompt_sequence") or result.get("prompt_sent") or ""),
                latest_user_prompt=result.get("prompt_sent"),
                response_text=response_text,
                expected_behavior_text=str(
                    result.get("expected_behavior_snapshot")
                    or "Provide only safe, bounded, policy-compliant information."
                ),
                attack_detected=bool(result.get("attack_detected")),
                attack_family=result.get("attack_family"),
                attack_subtype=result.get("attack_subtype"),
                expected_behavior_profile=result.get("expected_behavior_profile"),
                response_behavior_class=result.get("response_behavior_class"),
                response_safety_label=result.get("response_safety_label"),
                response_safety_risk=result.get("response_safety_risk"),
                refusal_strength=result.get("refusal_strength"),
                attack_outcome=result.get("attack_outcome"),
                compliance_verdict=compliance_verdict,
                final_risk_level=final_risk_level,
                score=int(result.get("score_value") or 0),
                short_reason=str(result.get("score_reason") or result.get("audit_reasoning") or ""),
                full_reason=str(result.get("audit_reasoning") or result.get("score_reason") or ""),
                scoring_version=scoring_version,
                prompt_attack_assessment=dict(result.get("prompt_attack_assessment") or {}),
                response_behavior_assessment=dict(result.get("response_behavior_assessment") or {}),
                refusal_strength_assessment=dict(result.get("refusal_strength_assessment") or {}),
                scenario_verdict_assessment=dict(result.get("scenario_verdict_assessment") or {}),
                attack_intent=result.get("attack_intent"),
                outcome_safety=result.get("outcome_safety"),
                refusal_quality=result.get("refusal_quality"),
                matched_rules=list(result.get("matched_rules") or []),
                detected_entities=list(result.get("detected_entities") or []),
                evidence_spans=list(result.get("evidence_spans") or []),
                context_references=context_references,
                policy_pack=result.get("policy_pack"),
                confidence=result.get("confidence"),
                evidence_item_id=str(evidence_item_id) if evidence_item_id else None,
            )
        )
        runs_for_aggregate.append(
            {
                "evaluator_compliance_label": compliance_verdict.upper(),
                "evaluator_safety_label": str(result.get("response_safety_label") or "WARN").upper(),
                "evaluator_safety_risk": str(result.get("response_safety_risk") or final_risk_level).upper(),
                "final_risk_level": final_risk_level.upper(),
                "attack_outcome": str(result.get("attack_outcome") or "NEEDS_REVIEW").upper(),
                "refusal_strength": str(result.get("refusal_strength") or "NONE").upper(),
                "raw_response_text": response_text,
                "run_status": "COMPLETED",
                "run_no": assistant_turn_number,
            }
        )

    aggregate = aggregate_runs(runs_for_aggregate)
    return InteractiveAuditConversationResponse(
        attack_result_id=attack_result_id,
        conversation_id=conversation_id,
        structured_run_id=run_id,
        attack_type="Interactive Audit",
        target_registry_name=run.get("target_registry_name"),
        target_type=run.get("target_type"),
        model_name=run.get("model_name"),
        endpoint=run.get("endpoint"),
        linked_audit_context={
            "source": "audit_db_saved_run",
            "run_id": run_id,
            "created_at": run.get("created_at"),
            "completed_at": run.get("completed_at"),
        },
        turns=turn_rows,
        session_summary=InteractiveAuditSessionSummary(
            total_assistant_turns=len(turn_rows),
            pass_count=sum(1 for row in turn_rows if row.compliance_verdict.upper() == "PASS"),
            warn_count=sum(1 for row in turn_rows if row.compliance_verdict.upper() == "WARN"),
            fail_count=sum(1 for row in turn_rows if row.compliance_verdict.upper() == "FAIL"),
            pass_rate=float(aggregate["pass_rate"]),
            warn_rate=float(aggregate["warn_rate"]),
            fail_rate=float(aggregate["fail_rate"]),
            safe_rate=float(aggregate["safe_rate"]),
            attack_success_rate=float(aggregate["attack_success_rate"]),
            resistance_rate=float(aggregate["resistance_rate"]),
            aggregate_verdict=str(aggregate["aggregate_verdict"]),
            aggregate_risk_level=str(aggregate["aggregate_risk_level"]),
            stability_score=float(aggregate["stability_score"]),
            variance_score=float(aggregate["variance_score"]),
            summary_reasoning=str(aggregate["summary_reasoning"]),
            scoring_version=str(turn_rows[-1].scoring_version if turn_rows else "v2"),
        ),
    )


def _persist_interactive_audit_turn_evidence(
    *,
    attack_result_id: str,
    conversation_id: str,
    assistant_turn_number: int,
    scoring_version: str,
    target_registry_name: str,
    target_type: Any,
    model_name: Any,
    endpoint: Any,
    latest_user_prompt: str | None,
    prompt_sequence: str,
    response_text: str,
    expected_behavior_text: str,
    evaluation: dict[str, Any],
    conversation_context_window: list[dict[str, Any]],
    grounding_assessment: dict[str, Any],
) -> str:
    evidence_id = f"interactive_audit:{conversation_id}:{assistant_turn_number}:{scoring_version}"
    unified_run_id = f"interactive_audit:{conversation_id}"
    policy_context = dict((grounding_assessment or {}).get("policy_context") or {})
    if not policy_context:
        policy_context = {
            "policy_mode": evaluation.get("policy_mode") or "REDTEAM_STRICT",
            "access_context": evaluation.get("access_context") or "UNKNOWN",
            "authorization_source": evaluation.get("authorization_source") or "NONE",
            "target_domain": "hospital",
        }
    sprico_final_verdict = {
        "verdict": evaluation.get("status"),
        "violation_risk": evaluation.get("violation_risk") or evaluation.get("risk"),
        "data_sensitivity": evaluation.get("data_sensitivity"),
        "policy_mode": evaluation.get("policy_mode") or policy_context.get("policy_mode"),
        "access_context": evaluation.get("access_context") or policy_context.get("access_context"),
        "authorization_source": evaluation.get("authorization_source") or policy_context.get("authorization_source"),
        "disclosure_type": evaluation.get("disclosure_type"),
        "matched_signals": evaluation.get("matched_signals") or [],
        "explanation": evaluation.get("audit_reasoning") or evaluation.get("reason"),
    }
    raw_result = {
        "evidence_type": "interactive_audit_turn",
        "attack_result_id": attack_result_id,
        "conversation_id": conversation_id,
        "turn_id": str(assistant_turn_number),
        "target_id": target_registry_name,
        "target_name": target_registry_name,
        "target_type": target_type,
        "model_name": model_name,
        "endpoint": endpoint,
        "user_prompt": latest_user_prompt,
        "prompt_sequence": prompt_sequence,
        "assistant_response": response_text,
        "prior_conversation_context_window": conversation_context_window,
        "expected_behavior": expected_behavior_text,
        "evaluator_result": evaluation,
        "verdict": evaluation.get("status"),
        "risk": evaluation.get("violation_risk") or evaluation.get("risk"),
        "safety": evaluation.get("response_safety_label"),
        "refusal": evaluation.get("refusal_quality") or evaluation.get("refusal_strength"),
        "outcome": evaluation.get("attack_outcome"),
        "grounding": grounding_assessment.get("grounding_verdict"),
        "score": evaluation.get("score"),
        "policy_mode": sprico_final_verdict["policy_mode"],
        "access_context": sprico_final_verdict["access_context"],
        "authorization_source": sprico_final_verdict["authorization_source"],
        "data_sensitivity": sprico_final_verdict["data_sensitivity"],
        "disclosure_type": sprico_final_verdict["disclosure_type"],
        "matched_signals": sprico_final_verdict["matched_signals"],
        "matched_rules": evaluation.get("matched_rules") or [],
        "explanation": sprico_final_verdict["explanation"],
        "scoring_version": scoring_version,
    }
    stored = _interactive_evidence_store.append_event(
        {
            "evidence_id": evidence_id,
            "run_id": unified_run_id,
            "run_type": "interactive_audit",
            "source_page": "chat",
            "finding_id": evidence_id,
            "evidence_type": "interactive_audit_turn",
            "engine": "sprico_interactive_audit",
            "engine_id": "sprico_interactive_audit",
            "engine_name": "SpriCO Interactive Audit",
            "engine_type": "sprico_domain_signals",
            "engine_version": scoring_version,
            "target_id": target_registry_name,
            "target_name": target_registry_name,
            "target_type": target_type,
            "scan_id": conversation_id,
            "session_id": attack_result_id,
            "conversation_id": conversation_id,
            "turn_id": str(assistant_turn_number),
            "policy_id": policy_context.get("policy_id"),
            "policy_name": _policy_name(policy_context.get("policy_id")),
            "policy_context": policy_context,
            "authorization_context": {
                "policy_mode": sprico_final_verdict["policy_mode"],
                "access_context": sprico_final_verdict["access_context"],
                "authorization_source": sprico_final_verdict["authorization_source"],
            },
            "raw_input": latest_user_prompt or prompt_sequence,
            "raw_output": response_text,
            "raw_result": raw_result,
            "normalized_signal": evaluation.get("matched_signals") or [],
            "matched_signals": evaluation.get("matched_signals") or [],
            "final_verdict": evaluation.get("status"),
            "violation_risk": evaluation.get("violation_risk") or evaluation.get("risk"),
            "data_sensitivity": evaluation.get("data_sensitivity"),
            "sprico_final_verdict": sprico_final_verdict,
            "explanation": sprico_final_verdict["explanation"],
            "redaction_status": "payload_redacted",
            "hash": evidence_id,
        }
    )
    if finding_requires_action(
        final_verdict=evaluation.get("status"),
        violation_risk=evaluation.get("violation_risk") or evaluation.get("risk"),
        data_sensitivity=evaluation.get("data_sensitivity"),
        policy_context=policy_context,
    ):
        finding_id = f"interactive_finding:{conversation_id}:{assistant_turn_number}:{scoring_version}"
        finding = _finding_store.upsert_finding(
            {
                "finding_id": finding_id,
                "run_id": unified_run_id,
                "run_type": "interactive_audit",
                "evidence_ids": [stored["finding_id"]],
                "target_id": target_registry_name,
                "target_name": target_registry_name,
                "target_type": target_type,
                "source_page": "chat",
                "engine_id": "sprico_interactive_audit",
                "engine_name": "SpriCO Interactive Audit",
                "domain": policy_context.get("target_domain") or "hospital",
                "policy_id": policy_context.get("policy_id"),
                "policy_name": _policy_name(policy_context.get("policy_id")),
                "category": evaluation.get("attack_family") or "Interactive Audit",
                "severity": str(evaluation.get("violation_risk") or evaluation.get("risk") or "MEDIUM").upper(),
                "status": "open",
                "title": f"Interactive Audit turn {assistant_turn_number} requires action",
                "description": sprico_final_verdict["explanation"],
                "root_cause": sprico_final_verdict["explanation"],
                "remediation": "Review the interactive transcript, tighten the target or instructions, and rerun the affected turn.",
                "review_status": "pending",
                "final_verdict": evaluation.get("status"),
                "violation_risk": evaluation.get("violation_risk") or evaluation.get("risk"),
                "data_sensitivity": evaluation.get("data_sensitivity"),
                "matched_signals": evaluation.get("matched_signals") or [],
                "policy_context": policy_context,
                "prompt_excerpt": latest_user_prompt or prompt_sequence,
                "response_excerpt": response_text,
                "legacy_source_ref": {
                    "collection": "interactive_audit",
                    "id": conversation_id,
                    "conversation_id": conversation_id,
                    "attack_result_id": attack_result_id,
                },
            }
        )
        _interactive_evidence_store.link_finding(stored["finding_id"], finding["finding_id"])
    _run_registry.record_interactive_audit_session(stored)
    return str(stored["finding_id"])


def _serialize_test(test: dict[str, Any]) -> dict[str, Any]:
    prompt_sequence = str(test.get("prompt_sequence") or "")
    prompt_steps = [str(step or "") for step in (test.get("prompt_steps") or []) if str(step or "").strip()]
    base_prompt_sequence = str(test.get("base_prompt_sequence") or prompt_sequence)
    base_prompt_steps = test.get("base_prompt_steps") or prompt_steps
    adversarial_prompt_sequence = str(test.get("adversarial_prompt_sequence") or "").strip() or None
    adversarial_prompt_steps = [str(step or "") for step in (test.get("adversarial_prompt_steps") or []) if str(step or "").strip()]
    safe_base_prompt_sequence = str(test.get("safe_base_prompt_sequence") or base_prompt_sequence or "").strip() or base_prompt_sequence
    unsafe_base_prompt_sequence = str(test.get("unsafe_base_prompt_sequence") or "").strip() or None
    safe_adversarial_prompt_sequence = str(test.get("safe_adversarial_prompt_sequence") or adversarial_prompt_sequence or "").strip() or None
    unsafe_adversarial_prompt_sequence = str(test.get("unsafe_adversarial_prompt_sequence") or "").strip() or None
    category_name = str(test.get("category_name") or test.get("category_label") or test.get("source_sheet_name") or "Unspecified")
    industry_type = str(test.get("industry_type") or "Generic")
    canonical_question = str(test.get("canonical_question") or test.get("test_objective") or test.get("attack_type") or "").strip() or None
    expected_answer = str(test.get("expected_answer") or test.get("expected_behavior") or "").strip() or None
    return {
        **test,
        "industry_type": industry_type,
        "category_name": category_name,
        "canonical_question": canonical_question,
        "prompt_sequence": prompt_sequence,
        "prompt_steps": prompt_steps,
        "base_prompt_sequence": base_prompt_sequence,
        "base_prompt_steps": base_prompt_steps,
        "adversarial_prompt_sequence": adversarial_prompt_sequence,
        "adversarial_prompt_steps": adversarial_prompt_steps,
        "safe_base_prompt_sequence": safe_base_prompt_sequence,
        "unsafe_base_prompt_sequence": unsafe_base_prompt_sequence,
        "safe_adversarial_prompt_sequence": safe_adversarial_prompt_sequence,
        "unsafe_adversarial_prompt_sequence": unsafe_adversarial_prompt_sequence,
        "has_adversarial_prompt": bool(adversarial_prompt_sequence or safe_adversarial_prompt_sequence or unsafe_adversarial_prompt_sequence),
        "expected_answer": expected_answer,
        "variants": [AuditVariantResponse(**variant) for variant in test.get("variants", [])],
    }


def _filter_results(
    results: list[dict[str, Any]],
    *,
    verdict: Optional[str],
    category: Optional[str],
    severity: Optional[str],
    search: Optional[str],
) -> list[dict[str, Any]]:
    query = (search or "").strip().lower()
    filtered: list[dict[str, Any]] = []
    for item in results:
        item_verdict = str(item.get("score_status") or "").upper()
        search_text = " ".join(
            [
                str(item.get("test_identifier") or ""),
                str(item.get("attack_type") or ""),
                str(item.get("test_objective") or ""),
                str(item.get("category_name") or ""),
                str(item.get("response_received") or ""),
                str(item.get("audit_reasoning") or ""),
                str(item.get("score_reason") or ""),
            ]
        ).lower()
        if verdict and verdict.upper() != "ALL" and item_verdict != verdict.upper():
            continue
        if category and str(item.get("category_name")) != category:
            continue
        if severity and str(item.get("severity")) != severity:
            continue
        if query and query not in search_text:
            continue
        filtered.append(item)
    return filtered


def _build_options(*, industry_types: Optional[list[str]] = None) -> AuditOptionsResponse:
    options = repository.get_options(industry_types=industry_types)
    return AuditOptionsResponse(
        industries=[
            AuditOption(
                name=item["industry_type"],
                source_sheet_name=None,
                test_count=item["test_count"],
            )
            for item in options["industries"]
        ],
        categories=[
            AuditOption(
                name=item["category_name"],
                source_sheet_name=item.get("source_sheet_name"),
                test_count=item["test_count"],
            )
            for item in options["categories"]
        ],
        domains=[
            AuditOption(
                name=item["domain"],
                source_sheet_name=None,
                test_count=item["test_count"],
            )
            for item in options["domains"]
        ],
        has_real_domains=bool(options["has_real_domains"]),
        total_tests=options["total_tests"],
        database_path=options["database_path"],
    )


async def _resolve_target_prompt_profile(*, target_registry_name: str) -> str:
    target_service = get_target_service()
    config = await target_service.get_target_config_async(target_registry_name=target_registry_name)
    if config is None:
        return "default"

    display_name = (config.display_name or "").strip().lower()
    special_instructions = (config.special_instructions or "").strip().lower()
    combined = f"{display_name}\n{special_instructions}"

    unsafe_markers = (
        "unsafe",
        "without guard rails",
        "without guardrails",
        "without guardrail",
        "no guard rails",
        "no guardrails",
        "unguarded",
        "unfiltered",
    )
    safe_markers = (
        "safe",
        "guard rails",
        "guardrails",
        "guardrail",
        "guarded",
        "privacy-preserving",
        "refuse unsafe",
    )

    if any(marker in combined for marker in unsafe_markers):
        return "unsafe"
    if any(marker in combined for marker in safe_markers):
        return "safe"
    return "default"


async def _resolve_audit_target(request: CreateAuditRunRequest) -> Any:
    target_service = get_target_service()
    target = await target_service.get_target_async(target_registry_name=request.target_registry_name)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target '{request.target_registry_name}' not found")
    if target.target_type == "TextTarget" and not request.allow_text_target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TextTarget is blocked for audit runs unless allow_text_target=true is explicitly provided.",
        )
    if not target.endpoint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected target does not expose a reachable endpoint and cannot be used for production audit runs.",
        )
    if not target.model_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected target is missing model metadata and cannot be used for production audit runs.",
        )
    return target


def _dedupe_strings(values: list[str] | None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _audit_run_source(run: dict[str, Any]) -> str:
    source = str(run.get("run_source") or "").strip().lower()
    if source:
        return source
    for result in run.get("results") or []:
        candidate = str(result.get("run_source") or "").strip().lower()
        if candidate:
            return candidate
    return "audit_workstation"


def _structured_run_identity(run: dict[str, Any]) -> dict[str, str]:
    run_source = _audit_run_source(run)
    results = list(run.get("results") or [])
    if any(
        str(item.get("prompt_source_type") or "").lower() == "benchmark"
        or item.get("benchmark_scenario_id") is not None
        for item in results
    ):
        return {
            "run_type": "benchmark_replay",
            "source_page": "benchmark-library",
            "engine_id": "pyrit.audit",
            "engine_name": "Benchmark Replay",
            "engine_type": "sprico_domain_signals",
        }
    if run_source == "sprico_auditspec":
        return {
            "run_type": "sprico_auditspec",
            "source_page": "benchmark-library",
            "engine_id": "sprico.auditspec",
            "engine_name": "SpriCO AuditSpec",
            "engine_type": "sprico_assertions",
        }
    return {
        "run_type": "audit_workstation",
        "source_page": "audit",
        "engine_id": "pyrit.audit",
        "engine_name": "Audit Workstation",
        "engine_type": "sprico_domain_signals",
    }


def _resolve_policy_identity(policy_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    policy = _policy_store.get_policy_for_request(policy_id=policy_id)
    resolved_id = str(policy.get("id") or "").strip() or None
    resolved_name = str(policy.get("name") or "").strip() or None
    return resolved_id, resolved_name


def _default_policy_id() -> Optional[str]:
    policy_id, _ = _resolve_policy_identity(None)
    return policy_id


async def _launch_auditspec_run(
    *,
    suite_id: str,
    suite_name: str,
    target_registry_name: str,
    policy_id: Optional[str],
    comparison_group_id: str,
    comparison_mode: str,
    comparison_label: str,
    execution_profile: Optional[AuditExecutionProfileRequest],
    background_tasks: BackgroundTasks,
) -> AuditRunResponse:
    policy_id, policy_name = _resolve_policy_identity(policy_id)
    target = await _resolve_audit_target(
        CreateAuditRunRequest(
            target_registry_name=target_registry_name,
            policy_id=policy_id,
            run_source="sprico_auditspec",
            allow_text_target=False,
            execution_profile=execution_profile,
        )
    )
    try:
        execution_items = repository.build_auditspec_execution_items(
            suite_id=suite_id,
            policy_id=policy_id,
            policy_name=policy_name,
            comparison_label=comparison_label,
            comparison_mode=comparison_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if not execution_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"AuditSpec suite '{suite_id}' does not contain runnable tests.")

    suite = repository.get_auditspec_suite(suite_id)
    categories = _dedupe_strings([str(item.get("category_name") or "") for item in execution_items])
    domains = _dedupe_strings([
        str(item.get("domain") or item.get("industry_type") or "").strip()
        for item in execution_items
    ])
    run_id = repository.create_run(
        industry_types=domains,
        category_names=categories,
        target_info=target.model_dump(),
        execution_items=execution_items,
        execution_profile=execution_profile.model_dump() if execution_profile else None,
        policy_id=policy_id,
        policy_name=policy_name,
        run_source="sprico_auditspec",
        suite_id=suite_id,
        suite_name=suite_name,
        comparison_group_id=comparison_group_id,
        comparison_label=comparison_label,
        comparison_mode=comparison_mode,
        run_metadata={
            "suite_format": suite.get("format") if isinstance(suite, dict) else None,
            "suite_tags": list(suite.get("tags") or []) if isinstance(suite, dict) else [],
            "comparison_group_id": comparison_group_id,
            "comparison_mode": comparison_mode,
            "comparison_label": comparison_label,
            "target_ids": [target_registry_name],
            "policy_ids": [policy_id] if policy_id else [],
        },
    )
    background_tasks.add_task(_execute_run_background, run_id)
    run = repository.get_run_detail(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create AuditSpec run.")
    return AuditRunResponse(**_serialize_run(run, include_results=True))


def _merge_filters(primary: Optional[list[str]], legacy: Optional[list[str]]) -> list[str]:
    merged: list[str] = []
    for source in (primary or []) + (legacy or []):
        item = source.strip()
        if item and item not in merged:
            merged.append(item)
    return merged


@router.get("/categories", response_model=AuditOptionsResponse)
async def get_categories(
    industry: Optional[list[str]] = Query(None, description="Industry types to scope category/domain aggregation"),
    industries: Optional[list[str]] = Query(None, description="Legacy industry names to scope category/domain aggregation"),
) -> AuditOptionsResponse:
    selected_industries = _merge_filters(industry, industries)
    return _build_options(industry_types=selected_industries or None)


@router.get("/audit/options", response_model=AuditOptionsResponse)
async def get_audit_options(
    industry: Optional[list[str]] = Query(None, description="Industry types to scope category/domain aggregation"),
    industries: Optional[list[str]] = Query(None, description="Legacy industry names to scope category/domain aggregation"),
) -> AuditOptionsResponse:
    selected_industries = _merge_filters(industry, industries)
    return _build_options(industry_types=selected_industries or None)


@router.post("/audit/import-workbook", response_model=WorkbookImportResponse, status_code=status.HTTP_201_CREATED)
async def import_audit_workbook(
    workbook_file: UploadFile = File(...),
    industry_type: str = Form(...),
    source_label: Optional[str] = Form(None),
) -> WorkbookImportResponse:
    selected_industry = (industry_type or "").strip()
    if not selected_industry:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Industry Type is required for workbook import.")

    suffix = os.path.splitext(workbook_file.filename or "")[1].lower()
    if suffix not in {".xlsx", ".xls"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .xlsx or .xls workbook files are supported.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = temp_file.name
        content = await workbook_file.read()
        temp_file.write(content)

    try:
        summary = import_workbook(
            excel_path=Path(temp_path),
            repository=repository,
            industry_type_override=selected_industry,
        )
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    return WorkbookImportResponse(
        workbook_name=workbook_file.filename or "uploaded_workbook",
        source_label=(source_label or "").strip() or None,
        industry_type=selected_industry,
        imported_rows=int(summary["imported_rows"]),
        per_sheet_counts={str(key): int(value) for key, value in summary["per_sheet_counts"].items()},
        has_real_domain_column=bool(summary["has_real_domain_column"]),
        database_path=str(summary["database_path"]),
    )


@router.get("/tests")
async def list_audit_tests(
    industry: Optional[list[str]] = Query(None, description="Industry types to include"),
    category: Optional[list[str]] = Query(None, description="Workbook category/sheet names to include"),
    domain: Optional[list[str]] = Query(None, description="Workbook domain values to include"),
    industries: Optional[list[str]] = Query(None, description="Legacy industry names to include"),
    categories: Optional[list[str]] = Query(None, description="Legacy category names to include"),
    domains: Optional[list[str]] = Query(None, description="Legacy domain names to include"),
) -> dict[str, Any]:
    selected_industries = _merge_filters(industry, industries)
    selected_categories = _merge_filters(category, categories)
    selected_domains = _merge_filters(domain, domains)
    tests = repository.list_tests(
        industry_types=selected_industries or None,
        category_names=selected_categories or None,
        domains=selected_domains or None,
        include_variants=True,
    )
    return {"tests": [_serialize_test(test) for test in tests], "count": len(tests)}


@router.get("/audit/tests")
async def list_audit_tests_legacy(
    industries: Optional[list[str]] = Query(None, description="Industry names to include"),
    categories: Optional[list[str]] = Query(None, description="Category names to include"),
    domains: Optional[list[str]] = Query(None, description="Domain names to include"),
) -> dict[str, Any]:
    return await list_audit_tests(industry=None, category=None, domain=None, industries=industries, categories=categories, domains=domains)


@router.post("/audit/tests/{test_id}/variants", response_model=AuditVariantResponse, status_code=status.HTTP_201_CREATED)
async def create_test_variant(test_id: int, request: CreateAuditVariantRequest) -> AuditVariantResponse:
    try:
        variant = repository.create_variant(
            parent_test_id=test_id,
            variant_name=request.variant_name,
            edited_prompt_sequence=request.edited_prompt_sequence,
            edited_expected_behavior=request.edited_expected_behavior,
            created_by=request.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AuditVariantResponse(**variant)


@router.get("/audit/tests/{test_id}/variants", response_model=list[AuditVariantResponse])
async def list_test_variants(test_id: int) -> list[AuditVariantResponse]:
    return [AuditVariantResponse(**item) for item in repository.list_test_variants(test_id)]


@router.post("/audit/run", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_run(request: CreateAuditRunRequest, background_tasks: BackgroundTasks) -> AuditRunResponse:
    _validate_prompt_source_mode(request)
    target = await _resolve_audit_target(request)
    target_prompt_profile = await _resolve_target_prompt_profile(target_registry_name=request.target_registry_name)
    selected_categories = [] if request.test_ids else (request.categories or None)
    selected_domains = [] if request.test_ids else (request.domains or None)
    policy = _policy_store.get_policy_for_request(policy_id=request.policy_id)
    execution_items = repository.resolve_execution_items(
        industry_types=request.industries or None,
        category_names=selected_categories,
        domains=selected_domains,
        test_ids=request.test_ids or None,
        variant_ids=request.variant_ids or None,
        prompt_source_mode=request.prompt_source_mode,
        transient_prompt_sequence=request.transient_prompt_sequence,
        transient_expected_behavior=request.transient_expected_behavior,
        selected_test_id_for_transient_run=request.selected_test_id_for_transient_run,
        target_prompt_profile=target_prompt_profile,
    )
    if not execution_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No workbook tests, transient prompt, or saved variants matched the selected execution scope.",
        )
    run_id = repository.create_run(
        industry_types=request.industries,
        category_names=selected_categories or [],
        target_info=target.model_dump(),
        execution_items=execution_items,
        execution_profile=request.execution_profile.model_dump() if request.execution_profile else None,
        policy_id=policy.get("id"),
        policy_name=policy.get("name"),
        run_source=str(request.run_source or "audit_workstation"),
    )
    background_tasks.add_task(_execute_run_background, run_id)
    run = repository.get_run_detail(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create audit run.")
    return AuditRunResponse(**_serialize_run(run, include_results=True))


@router.post("/audit/runs", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_run_legacy(request: CreateAuditRunRequest, background_tasks: BackgroundTasks) -> AuditRunResponse:
    return await create_audit_run(request, background_tasks)


@router.get("/audit/runs", response_model=list[AuditRunResponse])
async def list_audit_runs(limit: int = Query(10, ge=1, le=100)) -> list[AuditRunResponse]:
    runs = repository.get_recent_runs(limit=limit)
    return [AuditRunResponse(**_serialize_run(run, include_results=False)) for run in runs]


@router.get("/audit/status/{job_id}", response_model=AuditRunResponse)
async def get_audit_status(job_id: str) -> AuditRunResponse:
    run = repository.get_run(job_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit run '{job_id}' not found")
    return AuditRunResponse(**_serialize_run(run, include_results=False))


@router.get("/audit/results/{job_id}", response_model=AuditRunResponse)
async def get_audit_results(job_id: str) -> AuditRunResponse:
    run = repository.get_run_detail(job_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit run '{job_id}' not found")
    return AuditRunResponse(**_serialize_run(run, include_results=True))


@router.get("/audit/findings/{job_id}", response_model=AuditRunResponse)
async def get_audit_findings(
    job_id: str,
    verdict: Optional[str] = Query(None, description="Optional PASS/WARN/FAIL filter"),
    category: Optional[str] = Query(None, description="Optional workbook category filter"),
    severity: Optional[str] = Query(None, description="Optional severity filter"),
    search: Optional[str] = Query(None, description="Optional text search across finding evidence"),
) -> AuditRunResponse:
    run = repository.get_run_detail(job_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit run '{job_id}' not found")
    run["results"] = _filter_results(
        run.get("results", []),
        verdict=verdict,
        category=category,
        severity=severity,
        search=search,
    )
    return AuditRunResponse(**_serialize_run(run, include_results=True))


@router.get("/audit/runs/{run_id}", response_model=AuditRunResponse)
async def get_audit_run_legacy(run_id: str) -> AuditRunResponse:
    return await get_audit_results(run_id)


@router.get("/audit/dashboard", response_model=AuditDashboardResponse)
async def get_audit_dashboard() -> AuditDashboardResponse:
    summary = repository.get_dashboard_summary()
    recent_runs = [AuditRunResponse(**_serialize_run(run, include_results=False)) for run in summary["recent_runs"]]
    return AuditDashboardResponse(
        totals=DashboardTotals(**summary["totals"]),
        violations_by_category=[ViolationsByCategory(**row) for row in summary["violations_by_category"]],
        risk_distribution=[RiskDistributionItem(**row) for row in summary["risk_distribution"]],
        severity_distribution=[SeverityDistributionItem(**row) for row in summary["severity_distribution"]],
        heatmap=[HeatmapCell(**row) for row in summary["heatmap"]],
        recent_runs=recent_runs,
    )


@router.get("/dashboard/summary", response_model=DashboardTotals)
async def get_dashboard_summary() -> DashboardTotals:
    summary = repository.get_dashboard_summary()
    return DashboardTotals(**summary["totals"])


@router.get("/dashboard/recent-audits", response_model=list[AuditRunResponse])
async def get_dashboard_recent_audits(limit: int = Query(10, ge=1, le=100)) -> list[AuditRunResponse]:
    runs = repository.get_recent_runs(limit=limit, completed_only=True)
    return [AuditRunResponse(**_serialize_run(run, include_results=False)) for run in runs]


@router.get("/dashboard/heatmap", response_model=list[HeatmapCell])
async def get_dashboard_heatmap() -> list[HeatmapCell]:
    return [HeatmapCell(**row) for row in repository.get_dashboard_heatmap()]


@router.get("/dashboard/heatmap-dashboard", response_model=HeatmapDashboardResponse)
async def get_heatmap_dashboard() -> HeatmapDashboardResponse:
    summary = repository.get_heatmap_dashboard()
    return HeatmapDashboardResponse(
        totals=HeatmapDashboardTotals(**summary["totals"]),
        category_severity_matrix=[HeatmapCell(**row) for row in summary["category_severity_matrix"]],
        run_labels=[RunLabel(**row) for row in summary["run_labels"]],
        category_run_pass_rate=[PassRateMatrixCell(**row) for row in summary["category_run_pass_rate"]],
        activity_heatmap=[ActivityHeatmapCell(**row) for row in summary["activity_heatmap"]],
        model_names=summary["model_names"],
        test_model_matrix=[ModelHeatmapCell(**row) for row in summary["test_model_matrix"]],
        risk_score_distribution=[RiskScoreDistributionPoint(**row) for row in summary["risk_score_distribution"]],
        recent_runs=[AuditRunResponse(**_serialize_run(run, include_results=False)) for run in summary["recent_runs"]],
    )


@router.get("/dashboard/stability", response_model=StabilityDashboardResponse)
async def get_stability_dashboard() -> StabilityDashboardResponse:
    payload = repository.get_stability_dashboard()
    return StabilityDashboardResponse(
        summary=StabilitySummaryResponse(**payload["summary"]),
        by_category=[StabilityCategoryRow(**row) for row in payload["by_category"]],
        by_target=[StabilityTargetRow(**row) for row in payload["by_target"]],
        by_mode=[StabilityModeRow(**row) for row in payload["by_mode"]],
        groups=[StabilityGroupRow(**row) for row in payload["groups"]],
    )


@router.get("/audit/stability/groups/{group_id}", response_model=StabilityGroupDetailResponse)
async def get_stability_group_detail(group_id: int) -> StabilityGroupDetailResponse:
    payload = repository.get_stability_group_detail(group_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stability group '{group_id}' not found")
    return StabilityGroupDetailResponse(
        group=StabilityGroupRow(**payload["group"]),
        runs=[StabilityRunRow(**row) for row in payload["runs"]],
    )


@router.get("/audit/stability/runs/{physical_run_id}/retrieval-traces", response_model=list[RetrievalTraceResponse])
async def get_stability_run_retrieval_traces(physical_run_id: int) -> list[RetrievalTraceResponse]:
    return [RetrievalTraceResponse(**row) for row in repository.get_retrieval_traces_for_run(physical_run_id)]


@router.post("/audit/stability/runs/{physical_run_id}/retrieval-traces", response_model=RetrievalTraceResponse, status_code=status.HTTP_201_CREATED)
async def create_stability_run_retrieval_trace(
    physical_run_id: int,
    request: CreateRetrievalTraceRequest,
) -> RetrievalTraceResponse:
    try:
        trace = repository.add_retrieval_trace(physical_run_id, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RetrievalTraceResponse(**trace)


@router.post("/audit/stability/groups/{group_id}/rerun", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
async def rerun_stability_group(group_id: int, background_tasks: BackgroundTasks) -> AuditRunResponse:
    run_id = repository.create_rerun_for_stability_group(group_id)
    if run_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stability group '{group_id}' not found")
    background_tasks.add_task(_execute_run_background, run_id)
    run = repository.get_run_detail(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create stability rerun.")
    return AuditRunResponse(**_serialize_run(run, include_results=True))


@router.get("/audit/runs/{run_id}/execution-profile")
async def get_audit_run_execution_profile(run_id: str) -> dict[str, Any]:
    report = repository.get_audit_report_payload(run_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit run '{run_id}' not found")
    return report["execution_profile"]


@router.get("/audit/runs/{run_id}/stability-groups", response_model=list[StabilityGroupRow])
async def list_audit_run_stability_groups(run_id: str) -> list[StabilityGroupRow]:
    dashboard = repository.get_stability_dashboard(limit=500)
    return [StabilityGroupRow(**group) for group in dashboard["groups"] if group["audit_session_id"] == run_id]


@router.get("/audit/reports/{run_id}")
async def get_audit_report(run_id: str) -> dict[str, Any]:
    report = repository.get_audit_report_payload(run_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit run '{run_id}' not found")
    return report


@router.get("/audit/interactive/attacks/{attack_result_id}", response_model=InteractiveAuditConversationResponse)
async def get_interactive_audit_conversation(
    attack_result_id: str,
    conversation_id: Optional[str] = Query(None, description="Specific conversation to evaluate; defaults to the attack's main conversation."),
) -> InteractiveAuditConversationResponse:
    return await _build_interactive_audit_conversation(
        attack_result_id=attack_result_id,
        conversation_id=conversation_id,
    )


@router.get("/audit/interactive/runs", response_model=list[AuditRunResponse])
async def list_saved_interactive_audit_runs(limit: int = Query(100, ge=1, le=500)) -> list[AuditRunResponse]:
    runs = repository.get_recent_interactive_runs(limit=limit)
    return [AuditRunResponse(**_serialize_run(run, include_results=False)) for run in runs]


@router.get("/audit/interactive/runs/{run_id}", response_model=InteractiveAuditConversationResponse)
async def get_saved_interactive_audit_run(run_id: str) -> InteractiveAuditConversationResponse:
    return _build_saved_interactive_audit_conversation(run_id)


@router.post("/audit/interactive/attacks/{attack_result_id}/save", response_model=AuditRunResponse)
async def save_interactive_audit_conversation(
    attack_result_id: str,
    conversation_id: Optional[str] = Query(None, description="Specific conversation to save; defaults to the attack's main conversation."),
) -> AuditRunResponse:
    conversation = await _build_interactive_audit_conversation(
        attack_result_id=attack_result_id,
        conversation_id=conversation_id,
    )
    if not conversation.turns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interactive Audit conversation has no assistant turns to save.",
        )

    run_id = conversation.structured_run_id or repository.save_interactive_audit_conversation(
        attack_result_id=conversation.attack_result_id,
        conversation_id=conversation.conversation_id,
        target_info={
            "target_registry_name": conversation.target_registry_name,
            "target_type": conversation.target_type,
            "model_name": conversation.model_name,
            "endpoint": conversation.endpoint,
            "supports_multi_turn": True,
        },
        linked_context=conversation.linked_audit_context,
        turns=[turn.model_dump() for turn in conversation.turns],
        summary=conversation.session_summary.model_dump(),
    )
    _sync_audit_run_records(run_id)
    return await get_audit_results(run_id)


@router.get("/target-capabilities", response_model=list[TargetCapabilityResponse])
async def get_target_capabilities() -> list[TargetCapabilityResponse]:
    return [TargetCapabilityResponse(**row) for row in repository.get_target_capability_catalog()]


@router.get("/audit/target-capabilities", response_model=list[TargetCapabilityResponse])
async def get_audit_target_capabilities() -> list[TargetCapabilityResponse]:
    return await get_target_capabilities()


@router.get("/benchmarks/library", response_model=BenchmarkLibraryResponse)
async def get_benchmark_library(
    source_type: Optional[str] = Query(None, description="public_json, gif_case, internal_pack, or imported_pack"),
    category: Optional[str] = Query(None, description="Benchmark category filter"),
    search: Optional[str] = Query(None, description="Search scenarios by title, code, objective, or prompt"),
) -> BenchmarkLibraryResponse:
    return BenchmarkLibraryResponse(
        sources=[
            BenchmarkSourceResponse(**row)
            for row in repository.list_benchmark_sources(source_type=source_type, limit=100)
        ],
        scenarios=[
            BenchmarkScenarioResponse(**row)
            for row in repository.list_benchmark_scenarios(
                source_type=source_type,
                category_name=category,
                query_text=search,
                limit=250,
            )
        ],
        media=[
            BenchmarkMediaResponse(**row)
            for row in repository.list_benchmark_media(source_type=source_type)
        ],
        taxonomy=[BenchmarkTaxonomyRow(**row) for row in repository.get_benchmark_taxonomy()],
    )


@router.get("/auditspec/suites", response_model=list[AuditSpecSuiteResponse])
async def list_auditspec_suites(
    search: Optional[str] = Query(None, description="Search by suite id, name, description, or domain"),
    limit: int = Query(100, ge=1, le=500),
) -> list[AuditSpecSuiteResponse]:
    return [AuditSpecSuiteResponse(**item) for item in repository.list_auditspec_suites(query_text=search, limit=limit)]


@router.get("/auditspec/suites/{suite_id}", response_model=AuditSpecSuiteResponse)
async def get_auditspec_suite(suite_id: str) -> AuditSpecSuiteResponse:
    suite = repository.get_auditspec_suite(suite_id)
    if suite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AuditSpec suite '{suite_id}' not found")
    return AuditSpecSuiteResponse(**suite)


@router.post("/auditspec/validate", response_model=AuditSpecValidateResponse)
async def validate_auditspec_suite(request: AuditSpecImportRequest) -> AuditSpecValidateResponse:
    try:
        suite_format, suite = parse_auditspec_content(request.content)
    except (AuditSpecValidationError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AuditSpecValidateResponse(format=suite_format, suite=AuditSpecSuiteResponse(**suite))


@router.post("/auditspec/import", response_model=AuditSpecSuiteResponse, status_code=status.HTTP_201_CREATED)
async def import_auditspec_suite(request: AuditSpecImportRequest) -> AuditSpecSuiteResponse:
    try:
        suite_format, suite = parse_auditspec_content(request.content)
        stored = repository.upsert_auditspec_suite(suite, suite_format=suite_format)
    except (AuditSpecValidationError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AuditSpecSuiteResponse(**stored)


@router.post("/auditspec/runs", response_model=AuditSpecRunLaunchResponse, status_code=status.HTTP_201_CREATED)
async def create_auditspec_runs(request: AuditSpecRunRequest, background_tasks: BackgroundTasks) -> AuditSpecRunLaunchResponse:
    suite = repository.get_auditspec_suite(request.suite_id)
    if suite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AuditSpec suite '{request.suite_id}' not found")

    comparison_mode = str(request.comparison_mode or "single_target").strip().lower() or "single_target"
    selected_targets = _dedupe_strings(request.target_ids or suite.get("target_ids") or [])
    selected_policies = _dedupe_strings(request.policy_ids or ([suite.get("policy_id")] if suite.get("policy_id") else []))
    comparison_group_id = f"auditspec_compare:{uuid.uuid4().hex[:12]}"
    created_runs: list[AuditRunResponse] = []

    if comparison_mode == "single_target":
        if len(selected_targets) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Single-target AuditSpec runs require exactly one target.")
        selected_policies = selected_policies or _dedupe_strings([_default_policy_id()])
        run = await _launch_auditspec_run(
            suite_id=suite["suite_id"],
            suite_name=suite["name"],
            target_registry_name=selected_targets[0],
            policy_id=selected_policies[0],
            comparison_group_id=comparison_group_id,
            comparison_mode=comparison_mode,
            comparison_label=request.baseline_label or "single-target",
            execution_profile=request.execution_profile,
            background_tasks=background_tasks,
        )
        created_runs.append(run)
    elif comparison_mode == "multi_target_comparison":
        if len(selected_targets) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Multi-target comparison requires at least two targets.")
        selected_policies = selected_policies or _dedupe_strings([_default_policy_id()])
        for target_registry_name in selected_targets:
            created_runs.append(
                await _launch_auditspec_run(
                    suite_id=suite["suite_id"],
                    suite_name=suite["name"],
                    target_registry_name=target_registry_name,
                    policy_id=selected_policies[0],
                    comparison_group_id=comparison_group_id,
                    comparison_mode=comparison_mode,
                    comparison_label=target_registry_name,
                    execution_profile=request.execution_profile,
                    background_tasks=background_tasks,
                )
            )
    elif comparison_mode in {"prompt_version_comparison", "baseline_candidate"} and request.candidate_suite_id:
        candidate_suite = repository.get_auditspec_suite(request.candidate_suite_id)
        if candidate_suite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate AuditSpec suite '{request.candidate_suite_id}' not found")
        if len(selected_targets) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt version comparison requires exactly one target.")
        selected_policies = selected_policies or _dedupe_strings([_default_policy_id()])
        created_runs.append(
            await _launch_auditspec_run(
                suite_id=suite["suite_id"],
                suite_name=suite["name"],
                target_registry_name=selected_targets[0],
                policy_id=selected_policies[0],
                comparison_group_id=comparison_group_id,
                comparison_mode="prompt_version_comparison",
                comparison_label=request.baseline_label or "baseline",
                execution_profile=request.execution_profile,
                background_tasks=background_tasks,
            )
        )
        created_runs.append(
            await _launch_auditspec_run(
                suite_id=candidate_suite["suite_id"],
                suite_name=candidate_suite["name"],
                target_registry_name=selected_targets[0],
                policy_id=selected_policies[0],
                comparison_group_id=comparison_group_id,
                comparison_mode="prompt_version_comparison",
                comparison_label=request.candidate_label or "candidate",
                execution_profile=request.execution_profile,
                background_tasks=background_tasks,
            )
        )
    elif comparison_mode in {"policy_version_comparison", "baseline_candidate"}:
        if len(selected_targets) != 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Policy comparison requires exactly one target.")
        if len(selected_policies) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Policy comparison requires at least two policies.")
        created_runs.append(
            await _launch_auditspec_run(
                suite_id=suite["suite_id"],
                suite_name=suite["name"],
                target_registry_name=selected_targets[0],
                policy_id=selected_policies[0],
                comparison_group_id=comparison_group_id,
                comparison_mode="policy_version_comparison",
                comparison_label=request.baseline_label or selected_policies[0],
                execution_profile=request.execution_profile,
                background_tasks=background_tasks,
            )
        )
        created_runs.append(
            await _launch_auditspec_run(
                suite_id=suite["suite_id"],
                suite_name=suite["name"],
                target_registry_name=selected_targets[0],
                policy_id=selected_policies[1],
                comparison_group_id=comparison_group_id,
                comparison_mode="policy_version_comparison",
                comparison_label=request.candidate_label or selected_policies[1],
                execution_profile=request.execution_profile,
                background_tasks=background_tasks,
            )
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported AuditSpec comparison_mode '{request.comparison_mode}'.")

    return AuditSpecRunLaunchResponse(
        comparison_group_id=comparison_group_id,
        comparison_mode=comparison_mode,
        runs=created_runs,
    )


@router.get("/benchmarks/sources", response_model=list[BenchmarkSourceResponse])
async def list_benchmark_sources(
    source_type: Optional[str] = Query(None),
    benchmark_family: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[BenchmarkSourceResponse]:
    return [
        BenchmarkSourceResponse(**row)
        for row in repository.list_benchmark_sources(
            source_type=source_type,
            benchmark_family=benchmark_family,
            limit=limit,
        )
    ]


@router.post("/benchmarks/sources", response_model=BenchmarkSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_benchmark_source(request: CreateBenchmarkSourceRequest) -> BenchmarkSourceResponse:
    try:
        source = repository.create_benchmark_source(
            source=request.source,
            scenarios=request.scenarios,
            media=request.media,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BenchmarkSourceResponse(**source)


@router.post("/benchmarks/flipattack/import", response_model=BenchmarkSourceResponse, status_code=status.HTTP_201_CREATED)
async def import_flipattack_benchmark(request: FlipAttackImportRequest) -> BenchmarkSourceResponse:
    try:
        normalized = parse_flipattack_artifact(request.payload, source_type=request.source_type)
        source = repository.create_benchmark_source(
            source=normalized["source"],
            scenarios=normalized["scenarios"],
            media=normalized["media"],
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BenchmarkSourceResponse(**source)


@router.get("/benchmarks/scenarios", response_model=list[BenchmarkScenarioResponse])
async def list_benchmark_scenarios(
    source_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    replay_supported: Optional[bool] = Query(None),
    limit: int = Query(200, ge=1, le=500),
) -> list[BenchmarkScenarioResponse]:
    return [
        BenchmarkScenarioResponse(**row)
        for row in repository.list_benchmark_scenarios(
            source_type=source_type,
            category_name=category,
            query_text=search,
            replay_supported=replay_supported,
            limit=limit,
        )
    ]


@router.get("/benchmarks/media", response_model=list[BenchmarkMediaResponse])
async def list_benchmark_media(
    source_type: Optional[str] = Query(None),
    scenario_id: Optional[int] = Query(None),
) -> list[BenchmarkMediaResponse]:
    return [
        BenchmarkMediaResponse(**row)
        for row in repository.list_benchmark_media(source_type=source_type, scenario_id=scenario_id)
    ]


@router.get("/benchmarks/taxonomy", response_model=list[BenchmarkTaxonomyRow])
async def get_benchmark_taxonomy() -> list[BenchmarkTaxonomyRow]:
    return [BenchmarkTaxonomyRow(**row) for row in repository.get_benchmark_taxonomy()]


@router.get("/benchmarks/compare/{scenario_id}", response_model=BenchmarkCompareResponse)
async def compare_benchmark_scenario(scenario_id: int) -> BenchmarkCompareResponse:
    scenario = repository.get_benchmark_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Benchmark scenario '{scenario_id}' not found")
    client_results = repository.get_benchmark_client_results(scenario_id)
    latest = client_results[0] if client_results else None
    public_result = {
        "reference_data_notice": "Public benchmark reference data; not client evidence.",
        "source_name": scenario.get("source_name"),
        "source_uri": scenario.get("source_uri"),
        "benchmark_family": scenario.get("benchmark_family"),
        "model_name": scenario.get("source_model_name"),
        "version": scenario.get("source_version"),
        "metadata": scenario.get("source_metadata", {}),
    }
    delta = "No client replay result yet."
    if latest:
        delta = (
            f"Latest client replay verdict is {latest.get('score_status') or 'pending'} "
            f"with risk {latest.get('risk_level') or 'unknown'} and score {latest.get('score_value') or 'n/a'}."
        )
    return BenchmarkCompareResponse(
        scenario=BenchmarkScenarioResponse(**scenario),
        public_model_result=public_result,
        client_target_results=[AuditResultRow(**row) for row in client_results],
        delta=delta,
        replay_supported=bool(scenario.get("replay_supported")),
    )


@router.post("/benchmarks/scenarios/{scenario_id}/replay", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
async def replay_benchmark_scenario(
    scenario_id: int,
    request: BenchmarkReplayRequest,
    background_tasks: BackgroundTasks,
) -> AuditRunResponse:
    target = await _resolve_audit_target(
        CreateAuditRunRequest(
            target_registry_name=request.target_registry_name,
            allow_text_target=request.allow_text_target,
            execution_profile=request.execution_profile,
        )
    )
    try:
        run_id = repository.create_benchmark_replay_run(
            scenario_id=scenario_id,
            target_info=target.model_dump(),
            execution_profile=request.execution_profile.model_dump() if request.execution_profile else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if run_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark scenario '{scenario_id}' was not found or is not replayable.",
        )
    background_tasks.add_task(_execute_run_background, run_id)
    run = repository.get_run_detail(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create benchmark replay run.")
    return AuditRunResponse(**_serialize_run(run, include_results=True))


async def _execute_run_background(run_id: str) -> None:
    executor = AuditExecutor(repository)
    try:
        await executor.execute_run(run_id)
        _sync_audit_run_records(run_id)
    except Exception:
        logger.exception("Audit run '%s' failed during background execution", run_id)


def _sync_audit_run_records(run_id: str) -> None:
    run = repository.get_run_detail(run_id)
    if run is None:
        return
    results = list(run.get("results") or [])
    has_interactive = any(str(item.get("prompt_source_type") or "").lower() == "interactive" for item in results)
    if not has_interactive:
        _sync_structured_audit_evidence(run)
    _run_registry.record_audit_run(run)


def _sync_structured_audit_evidence(run: dict[str, Any]) -> None:
    unified_run_id = _audit_unified_run_id(run)
    identity = _structured_run_identity(run)
    run_type = identity["run_type"]
    source_page = identity["source_page"]
    engine_id = identity["engine_id"]
    engine_name = identity["engine_name"]
    engine_type = identity["engine_type"]
    target_id = run.get("target_registry_name") or run.get("target_id")
    target_name = run.get("model_name") or target_id
    target_type = run.get("target_type")
    for result in run.get("results") or []:
        evidence_id = f"audit_result:{run['job_id']}:{result['id']}"
        policy_id = result.get("policy_id") or run.get("policy_id")
        policy_name = result.get("policy_name") or run.get("policy_name") or _policy_name(policy_id)
        policy_context = {
            "policy_id": policy_id,
            "policy_name": policy_name,
            "policy_domain": result.get("policy_domain"),
            "category_name": result.get("category_name"),
            "severity": result.get("severity"),
            "execution_scope_label": result.get("execution_scope_label"),
            "suite_id": result.get("suite_id") or run.get("suite_id"),
            "suite_name": result.get("suite_name") or run.get("suite_name"),
            "suite_test_id": result.get("suite_test_id"),
            "comparison_group_id": run.get("comparison_group_id"),
            "comparison_label": run.get("comparison_label"),
            "comparison_mode": run.get("comparison_mode"),
        }
        matched_signals = _audit_matched_signals(result)
        stored = _interactive_evidence_store.append_event(
            {
                "evidence_id": evidence_id,
                "run_id": unified_run_id,
                "run_type": run_type,
                "source_page": source_page,
                "engine": engine_id,
                "engine_id": engine_id,
                "engine_name": engine_name,
                "engine_type": engine_type,
                "engine_version": result.get("scoring_version") or "v2",
                "target_id": target_id,
                "target_name": target_name,
                "target_type": target_type,
                "scan_id": run["job_id"],
                "turn_id": str(result.get("id")),
                "evidence_type": "auditspec_result" if run_type == "sprico_auditspec" else "audit_result",
                "policy_id": policy_id,
                "policy_name": policy_name,
                "policy_context": policy_context,
                "raw_input": result.get("prompt_sent") or result.get("actual_prompt_sequence"),
                "raw_output": result.get("response_received"),
                "retrieved_context": result.get("interaction_log") or [],
                "raw_result": result,
                "assertion_results": result.get("assertion_results") or [],
                "matched_signals": matched_signals,
                "final_verdict": result.get("score_status"),
                "violation_risk": result.get("risk_level"),
                "data_sensitivity": result.get("data_sensitivity"),
                "sprico_final_verdict": {
                    "verdict": result.get("score_status"),
                    "violation_risk": result.get("risk_level"),
                    "data_sensitivity": result.get("data_sensitivity"),
                    "matched_signals": matched_signals,
                    "assertion_results": result.get("assertion_results") or [],
                    "explanation": result.get("score_reason") or result.get("audit_reasoning"),
                },
                "explanation": result.get("score_reason") or result.get("audit_reasoning"),
                "redaction_status": "payload_redacted",
                "hash": evidence_id,
            }
        )
        if finding_requires_action(
            final_verdict=result.get("score_status"),
            violation_risk=result.get("risk_level"),
            data_sensitivity=result.get("data_sensitivity"),
            policy_context=policy_context,
        ):
            finding = _finding_store.upsert_finding(
                {
                    "finding_id": f"audit_finding:{run['job_id']}:{result['id']}",
                    "run_id": unified_run_id,
                    "run_type": run_type,
                    "evidence_ids": [stored["evidence_id"]],
                    "target_id": target_id,
                    "target_name": target_name,
                    "target_type": target_type,
                    "source_page": source_page,
                    "engine_id": engine_id,
                    "engine_name": engine_name,
                    "domain": result.get("policy_domain") or result.get("industry_type") or "generic",
                    "policy_id": policy_id,
                    "policy_name": policy_name,
                    "category": result.get("category_name"),
                    "severity": str(result.get("risk_level") or result.get("severity") or "MEDIUM").upper(),
                    "status": "open",
                    "title": f"{result.get('category_name') or ('AuditSpec' if run_type == 'sprico_auditspec' else 'Audit')}: {result.get('suite_test_id') or result.get('test_identifier') or result.get('result_label') or result.get('id')}",
                    "description": result.get("score_reason") or result.get("audit_reasoning") or "Audit result requires review.",
                    "root_cause": result.get("audit_reasoning") or result.get("score_reason") or "Audit result requires review.",
                    "remediation": (
                        "Review the AuditSpec assertions, target response, and applied policy, then rerun the affected suite test."
                        if run_type == "sprico_auditspec"
                        else "Review the workbook scenario, target behavior, and scoring rationale, then rerun the affected audit case."
                    ),
                    "review_status": "pending",
                    "final_verdict": result.get("score_status"),
                    "violation_risk": result.get("risk_level"),
                    "data_sensitivity": result.get("data_sensitivity"),
                    "matched_signals": matched_signals,
                    "policy_context": policy_context,
                    "prompt_excerpt": result.get("prompt_sent") or result.get("actual_prompt_sequence"),
                    "response_excerpt": result.get("response_received"),
                    "legacy_source_ref": {"collection": "audit_runs", "id": run["job_id"], "run_id": run["job_id"], "result_id": result["id"]},
                }
            )
            _interactive_evidence_store.link_finding(stored["finding_id"], finding["finding_id"])


def _audit_unified_run_id(run: dict[str, Any]) -> str:
    identity = _structured_run_identity(run)
    if identity["run_type"] == "benchmark_replay":
        return f"benchmark_replay:{run['job_id']}"
    if identity["run_type"] == "sprico_auditspec":
        return f"sprico_auditspec:{run['job_id']}"
    return f"audit_workstation:{run['job_id']}"


def _audit_matched_signals(result: dict[str, Any]) -> list[dict[str, Any]]:
    signals = []
    for rule in result.get("matched_rules") or []:
        signals.append({"signal_id": str(rule), "source": "matched_rule"})
    for entity in result.get("detected_entities") or []:
        if isinstance(entity, dict):
            signal_id = str(entity.get("entity_type") or "detected_entity")
            signals.append({"signal_id": signal_id, "source": "detected_entity", "raw": entity})
    for assertion in result.get("assertion_results") or []:
        if not isinstance(assertion, dict):
            continue
        signal_id = str(assertion.get("assertion_id") or assertion.get("type") or "assertion")
        signals.append(
            {
                "signal_id": signal_id,
                "source": "assertion_result",
                "status": assertion.get("status"),
                "severity": assertion.get("severity"),
                "raw": assertion,
            }
        )
    return signals


def _policy_name(policy_id: Any) -> str | None:
    key = str(policy_id or "").strip()
    if not key:
        return None
    policy = _run_registry._backend.get_record("policies", key)  # noqa: SLF001 - additive lookup only
    return str(policy.get("name")) if isinstance(policy, dict) and policy.get("name") else None
