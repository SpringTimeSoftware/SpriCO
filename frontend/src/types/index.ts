// ============================================================================
// Frontend UI Types
// ============================================================================

export interface MessageAttachment {
  type: 'image' | 'audio' | 'video' | 'file'
  name: string
  url: string
  mimeType: string
  size: number
  file?: File
  /** Backend piece ID — preserved so remix/copy can trace back to the original piece */
  pieceId?: string
  /** Backend prompt_metadata — preserved so video_id etc. carry over on remix/copy */
  metadata?: Record<string, unknown>
}

export interface RetrievalEvidenceItem {
  source?: string
  toolType?: string
  fileId?: string | null
  fileName?: string | null
  snippet?: string | null
  citation?: string | null
  retrievalRank?: number | null
  retrievalScore?: number | null
  raw?: Record<string, unknown> | null
}

export interface Message {
  role: 'user' | 'assistant' | 'simulated_assistant' | 'system'
  content: string
  timestamp: string
  turnNumber?: number
  attachments?: MessageAttachment[]
  retrievalEvidence?: RetrievalEvidenceItem[]
  /** If the backend returned an error for this message */
  error?: MessageError
  /** True while waiting for the backend response */
  isLoading?: boolean
  /** Reasoning summaries from model thinking (e.g. OpenAI reasoning tokens) */
  reasoningSummaries?: string[]
  /**
   * Original text content before conversion. Only set when it differs
   * from `content` (which holds the converted value).
   */
  originalContent?: string
  /** Original media attachments before conversion (when different from converted). */
  originalAttachments?: MessageAttachment[]
}

export interface MessageError {
  type: string // e.g. 'blocked', 'processing', 'empty', 'unknown'
  description?: string
}

// ============================================================================
// Backend DTO Types (mirror pyrit/backend/models)
// ============================================================================

export interface PaginationInfo {
  limit: number
  has_more: boolean
  next_cursor?: string | null
  prev_cursor?: string | null
}

// --- Targets ---

export interface TargetInstance {
  target_registry_name: string
  display_name?: string | null
  target_type: string
  endpoint?: string | null
  model_name?: string | null
  temperature?: number | null
  top_p?: number | null
  max_requests_per_minute?: number | null
  supports_multi_turn?: boolean
  target_specific_params?: Record<string, unknown> | null
  is_active?: boolean
  created_at?: string | null
  persistence_scope?: string | null
  credential_strategy?: string | null
  is_archived?: boolean
  archived_at?: string | null
}

export interface TargetListResponse {
  items: TargetInstance[]
  pagination: PaginationInfo
}

export interface CreateTargetRequest {
  type: string
  display_name?: string
  params: Record<string, unknown>
}

export interface TargetConfigView {
  target_registry_name: string
  display_name: string
  target_type: string
  endpoint?: string | null
  model_name?: string | null
  retrieval_store_id?: string | null
  retrieval_mode?: string | null
  masked_api_key?: string | null
  special_instructions?: string | null
  provider_settings: Record<string, unknown>
  runtime_summary?: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
  archived_at?: string | null
  archive_reason?: string | null
}

export interface UpdateTargetConfigRequest {
  display_name?: string
  special_instructions?: string
}

// --- Attacks ---

export interface TargetInfo {
  target_type: string
  endpoint?: string | null
  model_name?: string | null
}

export interface AttackSummary {
  attack_result_id: string
  conversation_id: string
  attack_type: string
  attack_specific_params?: Record<string, unknown> | null
  target?: TargetInfo | null
  converters: string[]
  outcome?: 'undetermined' | 'success' | 'failure' | null
  last_message_preview?: string | null
  message_count: number
  related_conversation_ids: string[]
  labels: Record<string, string>
  created_at: string
  updated_at: string
}

export interface CreateAttackRequest {
  target_registry_name: string
  name?: string
  labels?: Record<string, string>
  source_conversation_id?: string
  cutoff_index?: number
}

export interface CreateAttackResponse {
  attack_result_id: string
  conversation_id: string
  created_at: string
}

// --- Messages ---

export interface BackendScore {
  score_id: string
  scorer_type: string
  score_type: string
  score_value: string
  score_category?: string[] | null
  score_rationale?: string | null
  scored_at: string
}

export interface BackendMessagePiece {
  piece_id: string
  original_value_data_type: string
  converted_value_data_type: string
  original_value?: string | null
  original_value_mime_type?: string | null
  converted_value: string
  converted_value_mime_type?: string | null
  original_filename?: string | null
  converted_filename?: string | null
  prompt_metadata?: Record<string, unknown> | null
  scores: BackendScore[]
  response_error: string // 'none' | 'blocked' | 'processing' | 'empty' | 'unknown'
  response_error_description?: string | null
}

export interface BackendMessage {
  turn_number: number
  role: string
  pieces: BackendMessagePiece[]
  created_at: string
}

export interface ConversationMessagesResponse {
  conversation_id: string
  messages: BackendMessage[]
}

export interface MessagePieceRequest {
  data_type: string // 'text' | 'image_path' | 'audio_path' | 'video_path' | 'binary_path'
  original_value: string
  converted_value?: string
  mime_type?: string
  original_prompt_id?: string
  prompt_metadata?: Record<string, unknown>
}

export interface AddMessageRequest {
  role: string
  pieces: MessagePieceRequest[]
  send: boolean
  target_registry_name?: string
  converter_ids?: string[]
  target_conversation_id: string
  labels?: Record<string, string>
}

export interface AddMessageResponse {
  attack: AttackSummary
  messages: ConversationMessagesResponse
}

export interface AttackListResponse {
  items: AttackSummary[]
  pagination: PaginationInfo
}

// --- Conversations ---

export interface ConversationSummary {
  conversation_id: string
  message_count: number
  last_message_preview?: string | null
  created_at?: string | null
}

export interface AttackConversationsResponse {
  attack_result_id: string
  main_conversation_id: string
  conversations: ConversationSummary[]
}


export interface CreateConversationRequest {
  source_conversation_id?: string
  cutoff_index?: number
}

export interface CreateConversationResponse {
  conversation_id: string
  created_at: string
}

export interface ChangeMainConversationResponse {
  attack_result_id: string
  conversation_id: string
}

export interface InteractiveAuditTurn {
  assistant_turn_number: number
  prompt_sequence: string
  latest_user_prompt?: string | null
  response_text: string
  expected_behavior_text: string
  attack_detected: boolean
  attack_family?: string | null
  attack_subtype?: string | null
  expected_behavior_profile?: string | null
  response_behavior_class?: string | null
  response_safety_label?: string | null
  response_safety_risk?: string | null
  refusal_strength?: string | null
  attack_outcome?: string | null
  compliance_verdict: string
  final_risk_level: string
  score: number
  short_reason: string
  full_reason: string
  scoring_version: string
  grounding_verdict?: string | null
  grounding_risk?: string | null
  grounding_reason?: string | null
  grounding_assessment?: Record<string, unknown>
  prompt_attack_assessment: Record<string, unknown>
  response_behavior_assessment: Record<string, unknown>
  refusal_strength_assessment: Record<string, unknown>
  scenario_verdict_assessment: Record<string, unknown>
  attack_intent?: string | null
  outcome_safety?: string | null
  refusal_quality?: string | null
  matched_rules?: string[]
  detected_entities?: Array<Record<string, unknown>>
  evidence_spans?: Array<Record<string, unknown>>
  context_references?: Record<string, unknown>
  policy_pack?: string | null
  confidence?: number | null
  evidence_item_id?: string | null
}

export interface InteractiveAuditSessionSummary {
  total_assistant_turns: number
  pass_count: number
  warn_count: number
  fail_count: number
  pass_rate: number
  warn_rate: number
  fail_rate: number
  safe_rate: number
  attack_success_rate: number
  resistance_rate: number
  aggregate_verdict: string
  aggregate_risk_level: string
  stability_score: number
  variance_score: number
  summary_reasoning: string
  scoring_version: string
}

export interface InteractiveAuditConversation {
  attack_result_id: string
  conversation_id: string
  structured_run_id?: string | null
  attack_type?: string | null
  target_registry_name?: string | null
  target_type?: string | null
  model_name?: string | null
  endpoint?: string | null
  linked_audit_context: Record<string, unknown>
  turns: InteractiveAuditTurn[]
  session_summary: InteractiveAuditSessionSummary
}

// --- Audit ---

export interface AuditOption {
  name: string
  test_count: number
}

export interface AuditOptionsResponse {
  industries: AuditOption[]
  categories: AuditOption[]
  domains: AuditOption[]
  has_real_domains: boolean
  total_tests: number
  database_path: string
}

export interface AuditVariant {
  id: number
  parent_test_id: number
  variant_name: string
  edited_prompt_sequence: string
  edited_prompt_steps: string[]
  edited_expected_behavior?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
  test_label: string
}

export interface AuditTest {
  id: number
  test_identifier: string
  workbook_row_id: number
  industry_type: string
  category_name: string
  source_sheet_name: string
  name: string
  domain?: string | null
  attack_type: string
  test_objective: string
  canonical_question?: string | null
  prompt_sequence: string
  prompt_steps: string[]
  base_prompt_sequence: string
  base_prompt_steps: string[]
  adversarial_prompt_sequence?: string | null
  adversarial_prompt_steps: string[]
  safe_base_prompt_sequence?: string | null
  unsafe_base_prompt_sequence?: string | null
  safe_adversarial_prompt_sequence?: string | null
  unsafe_adversarial_prompt_sequence?: string | null
  has_adversarial_prompt: boolean
  expected_behavior: string
  expected_answer?: string | null
  original_result_guidance?: string | null
  severity: string
  source_origin: string
  test_label: string
  supporting_documents?: Record<string, unknown> | null
  variants: AuditVariant[]
}

export type AuditPromptSourceMode = 'base' | 'adversarial' | 'both' | 'current_edit' | 'selected_variant' | 'base_and_variant' | 'all_variants'

export interface CreateAuditRunRequest {
  industries?: string[]
  categories: string[]
  domains: string[]
  test_ids: number[]
  variant_ids: number[]
  prompt_source_mode?: AuditPromptSourceMode | null
  transient_prompt_sequence?: string | null
  transient_expected_behavior?: string | null
  selected_test_id_for_transient_run?: number | null
  target_registry_name: string
  policy_id?: string | null
  run_source?: string | null
  allow_text_target?: boolean
  execution_profile?: AuditExecutionProfileRequest
}

export interface AuditExecutionProfileRequest {
  mode_code: 'COMPLIANCE' | 'ROBUSTNESS' | 'ADVANCED'
  provider_name?: string | null
  api_style?: string | null
  temperature?: number | null
  top_p?: number | null
  top_k?: number | null
  fixed_seed: boolean
  base_seed?: number | null
  seed_strategy?: 'FIXED' | 'PER_RUN_RANDOM' | 'SEQUENTIAL' | null
  max_tokens?: number | null
  run_count_requested: number
  variability_mode: boolean
  created_by?: string | null
}

export interface WorkbookImportResponse {
  workbook_name: string
  source_label?: string | null
  industry_type: string
  imported_rows: number
  per_sheet_counts: Record<string, number>
  has_real_domain_column: boolean
  database_path: string
}

export interface CreateAuditVariantRequest {
  variant_name: string
  edited_prompt_sequence: string
  edited_expected_behavior?: string | null
  created_by?: string | null
}

export interface AuditResultRow {
  id: number
  test_id: number
  variant_id?: number | null
  display_order: number
  result_label: string
  variant_name?: string | null
  prompt_source_type?: string | null
  prompt_source_label?: string | null
  prompt_variant?: string | null
  run_source?: string | null
  policy_id?: string | null
  policy_name?: string | null
  suite_id?: string | null
  suite_test_id?: string | null
  suite_name?: string | null
  assertion_results?: Array<Record<string, unknown>>
  assertion_summary?: string | null
  transient_prompt_used?: boolean | null
  execution_scope_label?: string | null
  variant_group_key?: string | null
  editor_snapshot?: string | null
  industry_type: string
  category_name: string
  domain?: string | null
  severity: string
  test_identifier: string
  workbook_row_id: number
  attack_type: string
  test_objective: string
  original_workbook_prompt: string
  actual_prompt_sequence: string
  actual_prompt_steps: string[]
  prompt_sent?: string | null
  response_received?: string | null
  expected_behavior_snapshot: string
  original_result_guidance_snapshot?: string | null
  score_status?: string | null
  risk_level?: string | null
  score_value?: number | null
  score_reason?: string | null
  audit_reasoning?: string | null
  attack_detected?: boolean | null
  attack_family?: string | null
  attack_subtype?: string | null
  attack_severity_potential?: string | null
  policy_domain?: string | null
  expected_behavior_profile?: string | null
  response_behavior_class?: string | null
  response_safety_label?: string | null
  response_safety_risk?: string | null
  attack_outcome?: string | null
  refusal_strength?: string | null
  refusal_style?: string | null
  boundary_clarity?: string | null
  safe_alternative_quality?: string | null
  scoring_version?: string | null
  prompt_attack_assessment?: Record<string, unknown>
  response_behavior_assessment?: Record<string, unknown>
  refusal_strength_assessment?: Record<string, unknown>
  scenario_verdict_assessment?: Record<string, unknown>
  attack_intent?: string | null
  outcome_safety?: string | null
  refusal_quality?: string | null
  matched_rules?: string[]
  detected_entities?: Array<Record<string, unknown>>
  evidence_spans?: Array<Record<string, unknown>>
  context_references?: Record<string, unknown>
  policy_pack?: string | null
  confidence?: number | null
  interaction_log: Array<Record<string, unknown>>
  execution_status: 'pending' | 'running' | 'completed' | 'error'
  attack_result_id?: string | null
  conversation_id?: string | null
  stability_group_id?: number | null
  stability_run_id?: number | null
  stability_run_no?: number | null
  created_at: string
  started_at?: string | null
  completed_at?: string | null
}

export interface AuditRun {
  id: string
  job_id: string
  target_id: string
  target_registry_name: string
  target_type: string
  model_name?: string | null
  endpoint?: string | null
  supports_multi_turn: boolean
  run_source?: string | null
  policy_id?: string | null
  policy_name?: string | null
  suite_id?: string | null
  suite_name?: string | null
  comparison_group_id?: string | null
  comparison_label?: string | null
  comparison_mode?: string | null
  run_metadata?: Record<string, unknown>
  status: string
  selected_industries: string[]
  selected_categories: string[]
  selected_test_ids: number[]
  selected_variant_ids: number[]
  total_tests: number
  completed_tests: number
  pass_count: number
  warn_count: number
  fail_count: number
  progress_percent: number
  error_count: number
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  updated_at: string
  error_message?: string | null
  results: AuditResultRow[]
}

export interface AuditSpecSuite {
  suite_id: string
  name: string
  description?: string | null
  domain: string
  policy_id?: string | null
  target_ids: string[]
  tags: string[]
  assertions: Array<Record<string, unknown>>
  severity: string
  expected_behavior?: string | null
  metadata: Record<string, unknown>
  tests: Array<Record<string, unknown>>
  format?: string | null
  created_at?: string | null
  updated_at?: string | null
  test_count?: number | null
}

export interface AuditSpecValidateResponse {
  format: string
  suite: AuditSpecSuite
}

export interface AuditSpecRunRequest {
  suite_id: string
  comparison_mode: 'single_target' | 'multi_target_comparison' | 'prompt_version_comparison' | 'policy_version_comparison' | 'baseline_candidate'
  candidate_suite_id?: string | null
  target_ids: string[]
  policy_ids: string[]
  baseline_label?: string | null
  candidate_label?: string | null
  execution_profile?: AuditExecutionProfileRequest
}

export interface AuditSpecRunLaunchResponse {
  comparison_group_id: string
  comparison_mode: string
  runs: AuditRun[]
}

export interface PromptfooStatus {
  available: boolean
  version?: string | null
  node_version?: string | null
  install_hint?: string | null
  supported_modes: string[]
  final_verdict_capable: boolean
  error?: string | null
  advanced?: {
    executable_path?: string | null
    command?: string[] | null
    python_executable?: string | null
    node_version?: string | null
    stdout?: string | null
    stderr?: string | null
    returncode?: number | null
  }
}

export interface PromptfooPluginOption {
  id: string
  label: string
  default_selected?: boolean
}

export interface PromptfooPluginGroup {
  id: string
  label: string
  description: string
  plugins: PromptfooPluginOption[]
}

export interface PromptfooStrategyOption {
  id: string
  label: string
  description: string
  cost: string
  recommended: boolean
  default_selected?: boolean
}

export interface PromptfooCatalog {
  plugin_groups: PromptfooPluginGroup[]
  strategies: PromptfooStrategyOption[]
  supported_modes: string[]
  final_verdict_capable: boolean
  promptfoo_is_optional: boolean
}

export interface PromptfooRuntimeRequest {
  target_ids: string[]
  policy_ids: string[]
  domain: string
  plugin_group_id: string
  plugin_ids: string[]
  strategy_ids: string[]
  suite_id?: string | null
  purpose?: string | null
  num_tests_per_plugin: number
  max_concurrency: number
  use_remote_generation?: boolean
}

export interface PromptfooRuntimeLaunchRun {
  scan_id: string
  run_id: string
  target_id: string
  target_name: string
  policy_id: string
  policy_name?: string | null
  suite_id?: string | null
  suite_name?: string | null
  comparison_group_id: string
  comparison_mode: string
  comparison_label: string
  status: string
}

export interface PromptfooRuntimeLaunchResponse {
  comparison_group_id: string
  comparison_mode: string
  runs: PromptfooRuntimeLaunchRun[]
}

export interface AuditDashboardTotals {
  run_count: number
  total_tests: number
  pass_count: number
  warn_count: number
  fail_count: number
  safe_count: number
  partial_count: number
  violation_count: number
  finding_count: number
  pass_rate: number
  critical_findings: number
  error_count: number
}

export interface ViolationsByCategory {
  category_name: string
  violations: number
  partials: number
  safe: number
  total: number
}

export interface RiskDistributionItem {
  risk: string
  count: number
}

export interface SeverityDistributionItem {
  severity: string
  count: number
  total_count: number
}

export interface HeatmapCell {
  category_name: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  count: number
  total_count: number
}

export interface AuditDashboardResponse {
  totals: AuditDashboardTotals
  violations_by_category: ViolationsByCategory[]
  risk_distribution: RiskDistributionItem[]
  severity_distribution: SeverityDistributionItem[]
  heatmap: HeatmapCell[]
  recent_runs: AuditRun[]
}

export interface HeatmapDashboardTotals {
  run_count: number
  total_tests: number
  pass_count: number
  warn_count: number
  fail_count: number
  pass_rate: number
  model_count: number
  target_count: number
}

export interface RunLabel {
  run_id: string
  label: string
  model_name?: string | null
  completed_at: string
}

export interface PassRateMatrixCell {
  category_name: string
  run_id: string
  total_count: number
  finding_count: number
  pass_rate?: number | null
  drilldown_supported: boolean
}

export interface ActivityHeatmapCell {
  activity_date: string
  run_count: number
  total_tests: number
  finding_count: number
  failure_density: number
  single_run_id?: string | null
  drilldown_supported: boolean
  drilldown_reason?: string | null
}

export interface ModelHeatmapCell {
  test_identifier: string
  attack_type: string
  category_name: string
  model_name: string
  pass_count: number
  warn_count: number
  fail_count: number
  result_count: number
  dominant_status: 'PASS' | 'WARN' | 'FAIL'
  drilldown_run_id?: string | null
  drilldown_supported: boolean
}

export interface RiskScoreDistributionPoint {
  category_name: string
  score_bucket: number
  avg_score: number
  result_count: number
  finding_count: number
  failure_density: number
}

export interface HeatmapDashboardResponse {
  totals: HeatmapDashboardTotals
  category_severity_matrix: HeatmapCell[]
  run_labels: RunLabel[]
  category_run_pass_rate: PassRateMatrixCell[]
  activity_heatmap: ActivityHeatmapCell[]
  model_names: string[]
  test_model_matrix: ModelHeatmapCell[]
  risk_score_distribution: RiskScoreDistributionPoint[]
  recent_runs: AuditRun[]
}

export interface TargetCapability {
  id: number
  target_code: string
  display_name: string
  api_style: string
  modality: string
  supports_deterministic_seed: boolean
  supports_temperature: boolean
  supports_multi_run: boolean
  best_for: string
  not_suitable_for: string
  example_scenarios: string
  provider_examples: string
  is_builtin: boolean
  sort_order: number
}

export interface StabilitySummary {
  total_groups: number
  avg_stability_score: number
  avg_fail_rate: number
  worst_category?: string | null
  most_unstable_target?: string | null
  worst_case_fail_count: number
}

export interface StabilityCategoryRow {
  category_name?: string | null
  group_count: number
  avg_stability_score?: number | null
  avg_fail_rate?: number | null
  fail_groups: number
  warn_groups: number
}

export interface StabilityTargetRow {
  target_name?: string | null
  group_count: number
  avg_stability_score?: number | null
  avg_fail_rate?: number | null
}

export interface StabilityModeRow {
  mode_code: string
  group_count: number
  avg_stability_score?: number | null
  avg_fail_rate?: number | null
}

export interface StabilityGroupRow {
  id: number
  audit_session_id: string
  execution_profile_id: number
  prompt_source_type: string
  prompt_source_ref?: string | null
  benchmark_scenario_id?: number | null
  category_code?: string | null
  category_name?: string | null
  subcategory_name?: string | null
  severity_expected?: string | null
  expected_behavior_text?: string | null
  objective_text?: string | null
  run_count_actual: number
  aggregate_verdict?: string | null
  aggregate_risk_level?: string | null
  pass_rate?: number | null
  warn_rate?: number | null
  fail_rate?: number | null
  safe_rate?: number | null
  attack_success_rate?: number | null
  resistance_rate?: number | null
  variance_score?: number | null
  stability_score?: number | null
  worst_case_verdict?: string | null
  worst_case_risk_level?: string | null
  best_case_verdict?: string | null
  summary_reasoning?: string | null
  created_at: string
  mode_code: string
  model_target_type?: string | null
  model_target_name?: string | null
  provider_name?: string | null
  api_style?: string | null
  temperature?: number | null
  top_p?: number | null
  top_k?: number | null
  fixed_seed: boolean
  base_seed?: number | null
  seed_strategy?: string | null
  max_tokens?: number | null
  run_count_requested: number
  variability_mode: boolean
  target_registry_name: string
  model_name?: string | null
  endpoint?: string | null
  completed_at?: string | null
  session_created_at: string
}

export interface StabilityRunRow {
  id: number
  result_group_id: number
  run_no: number
  seed_used?: number | null
  temperature_used?: number | null
  top_p_used?: number | null
  top_k_used?: number | null
  prompt_text?: string | null
  raw_response_text?: string | null
  evaluator_safety_label?: string | null
  evaluator_safety_risk?: string | null
  evaluator_compliance_label?: string | null
  attack_family?: string | null
  attack_subtype?: string | null
  attack_severity_potential?: string | null
  policy_domain?: string | null
  expected_behavior_profile?: string | null
  response_behavior_class?: string | null
  attack_outcome?: string | null
  refusal_strength?: string | null
  refusal_style?: string | null
  boundary_clarity?: string | null
  safe_alternative_quality?: string | null
  evaluator_reasoning?: string | null
  scoring_version?: string | null
  prompt_attack_assessment?: Record<string, unknown>
  response_behavior_assessment?: Record<string, unknown>
  refusal_strength_assessment?: Record<string, unknown>
  scenario_verdict_assessment?: Record<string, unknown>
  is_worst_case: boolean
  is_best_case: boolean
  run_status: string
  created_at: string
  retrieval_traces: Array<Record<string, unknown>>
}

export interface RetrievalTrace {
  id: number
  run_id: number
  document_id?: string | null
  document_name?: string | null
  document_type?: string | null
  page_no?: number | null
  chunk_id?: string | null
  ocr_used: boolean
  retrieved_text_excerpt?: string | null
  retrieval_rank?: number | null
  retrieval_score?: number | null
  source_uri?: string | null
  citation_label?: string | null
}

export interface CreateRetrievalTraceRequest {
  document_id?: string | null
  document_name?: string | null
  document_type?: string | null
  page_no?: number | null
  chunk_id?: string | null
  ocr_used?: boolean
  retrieved_text_excerpt?: string | null
  retrieval_rank?: number | null
  retrieval_score?: number | null
  source_uri?: string | null
  citation_label?: string | null
}

export interface StabilityDashboardResponse {
  summary: StabilitySummary
  by_category: StabilityCategoryRow[]
  by_target: StabilityTargetRow[]
  by_mode: StabilityModeRow[]
  groups: StabilityGroupRow[]
}

export interface StabilityGroupDetailResponse {
  group: StabilityGroupRow
  runs: StabilityRunRow[]
}

export interface BenchmarkSource {
  id: number
  source_name: string
  source_type: 'public_json' | 'gif_case' | 'internal_pack' | 'imported_pack' | string
  source_uri?: string | null
  benchmark_family?: string | null
  model_name?: string | null
  version?: string | null
  category_name?: string | null
  subcategory_name?: string | null
  scenario_id?: string | null
  title: string
  description?: string | null
  metadata: Record<string, unknown>
  created_at: string
}

export interface BenchmarkScenario {
  id: number
  benchmark_source_id: number
  scenario_code: string
  title: string
  category_name: string
  subcategory_name?: string | null
  objective_text?: string | null
  prompt_text?: string | null
  expected_behavior_text?: string | null
  modality: string
  recommended_target_types: string[]
  tags: string[]
  severity_hint?: string | null
  replay_supported: boolean
  created_at: string
  source_name?: string | null
  source_type?: string | null
  source_uri?: string | null
  benchmark_family?: string | null
  source_model_name?: string | null
  source_version?: string | null
  source_title?: string | null
  source_description?: string | null
  source_metadata: Record<string, unknown>
}

export interface BenchmarkMedia {
  id: number
  benchmark_source_id: number
  scenario_id?: number | null
  media_type: 'gif' | 'image' | 'video' | string
  media_uri: string
  thumbnail_uri?: string | null
  caption?: string | null
  sort_order: number
  source_name?: string | null
  source_type?: string | null
  benchmark_family?: string | null
  scenario_title?: string | null
  category_name?: string | null
  subcategory_name?: string | null
  objective_text?: string | null
}

export interface BenchmarkTaxonomyRow {
  category_name: string
  subcategory_name?: string | null
  scenario_count: number
}

export interface BenchmarkLibraryResponse {
  sources: BenchmarkSource[]
  scenarios: BenchmarkScenario[]
  media: BenchmarkMedia[]
  taxonomy: BenchmarkTaxonomyRow[]
}

export interface CreateBenchmarkSourceRequest {
  source: Record<string, unknown>
  scenarios: Array<Record<string, unknown>>
  media: Array<Record<string, unknown>>
}

export interface FlipAttackImportRequest {
  payload: Record<string, unknown>
  source_type?: string
}

export interface BenchmarkReplayRequest {
  target_registry_name: string
  allow_text_target?: boolean
  execution_profile?: AuditExecutionProfileRequest
}

export interface BenchmarkCompareResponse {
  scenario: BenchmarkScenario
  public_model_result: Record<string, unknown>
  client_target_results: AuditResultRow[]
  delta: string
  replay_supported: boolean
}

export interface AuditReportPayload {
  run: AuditRun
  execution_profile: Record<string, unknown>
  summary: Record<string, unknown>
  result_groups: Array<Record<string, unknown>>
}

// --- SpriCO garak / Shield / Policy / Red ---

export interface GarakStatus {
  available: boolean
  version?: string | null
  python?: string | null
  executable?: string | null
  import_error?: string | null
  cli_error?: string | null
  install_hint?: string | null
  import_path?: string | null
  install_mode?: string | null
  error?: string | null
  advanced?: {
    python_executable?: string | null
    python_version?: string | null
    import_error?: string | null
    cli_error?: string | null
    import_path?: string | null
    install_mode?: string | null
  }
}

export interface GarakScanRequest {
  target_id: string
  policy_id: string
  scan_profile: string
  vulnerability_categories: string[]
  max_attempts?: number
  cross_domain_override?: boolean
  generator?: { type: string; name: string; options?: Record<string, unknown> }
  probes?: string[]
  detectors?: string[]
  extended_detectors?: boolean
  buffs?: string[]
  generations?: number
  seed?: number | null
  parallel_requests?: number
  parallel_attempts?: number
  timeout_seconds?: number
  budget?: Record<string, unknown>
  permission_attestation: boolean
  judge_settings?: {
    enabled: boolean
    provider: 'openai' | string
    mode: 'disabled' | 'redacted' | 'raw' | string
    judge_only_ambiguous?: boolean
  }
  policy_context?: Record<string, unknown>
}

export interface JudgeProviderStatus {
  id: string
  label: string
  configured: boolean
  enabled?: boolean
  enabled_by_default: boolean
  final_verdict_capable: boolean
  supports_redaction: boolean
  allowed_modes: string[]
  blocked_for_domains_by_default: string[]
  configure_hint?: string
}

export interface JudgeStatus {
  enabled: boolean
  configured: boolean
  providers: JudgeProviderStatus[]
  final_verdict_authority: string
}

export interface GarakScanResult {
  scan_id: string
  run_id?: string | null
  status: string
  target_id?: string | null
  target_name?: string | null
  target_type?: string | null
  policy_id?: string | null
  scan_profile?: string | null
  vulnerability_categories?: string[]
  started_at?: string | null
  finished_at?: string | null
  evaluation_status?: 'evaluated' | 'not_evaluated' | string | null
  failure_reason?: string | null
  evidence_count?: number
  findings_count?: number
  final_verdict?: string | null
  risk?: string | null
  profile_resolution?: Record<string, unknown>
  garak: GarakStatus
  raw_findings: Array<Record<string, unknown>>
  scanner_evidence?: Array<Record<string, unknown>>
  signals: Array<Record<string, unknown>>
  findings: Array<Record<string, unknown>>
  sprico_final_verdict?: Record<string, unknown>
  aggregate: Record<string, unknown>
  artifacts: Array<Record<string, unknown>>
  config?: Record<string, unknown>
}

export interface GarakSkippedProbeDetail {
  name: string
  reason: string
}

export interface GarakScanReport extends GarakScanResult {
  policy_name?: string | null
  resolved_probes_count?: number
  resolved_probes?: string[]
  skipped_probes_count?: number
  skipped_probes?: string[]
  skipped_probe_details?: GarakSkippedProbeDetail[]
  detectors_count?: number
  detectors?: string[]
  buffs_count?: number
  buffs?: string[]
  default_generations?: number | null
  timeout_seconds?: number | null
  artifact_count?: number
  final_sprico_verdict?: string | null
  violation_risk?: string | null
  data_sensitivity?: string | null
  duration_seconds?: number | null
  finding_ids?: string[]
  artifact_summary?: Array<{ label: string; status: string; detail?: string }>
}

export interface GarakScanReportsResponse {
  reports: GarakScanReport[]
  summary: GarakScannerReportSummary
}

export interface GarakScannerReportSummary {
  scanner_runs_total: number
  scanner_runs_by_status: Array<{ status: string; count: number }>
  scanner_runs_by_target: Array<{ target: string; count: number }>
  scanner_runs_by_profile: Array<{ profile: string; count: number }>
  scanner_runs_with_findings: number
  scanner_runs_with_no_findings: number
  scanner_runs_timeout?: number
  scanner_runs_failed?: number
  high_critical_scanner_findings: number
  scanner_findings_by_severity?: Array<{ severity: string; count: number }>
  scanner_evidence_count: number
  artifacts_stored: number
}

export interface StorageStatus {
  storage_backend: string
  sprico_sqlite_path: string
  pyrit_memory_path: string
  audit_db_path: string
  target_config_store_path: string
  policy_project_condition_store_path: string
  garak_artifacts_path: string
  uploaded_artifacts_path: string
  record_counts: Record<string, number>
}

export interface VersionInfo {
  version: string
  source?: string | null
  commit?: string | null
  commit_hash?: string | null
  modified?: boolean | null
  build_timestamp?: string | null
  backend_startup_timestamp?: string | null
  display: string
  database_info?: string | null
  default_labels?: Record<string, string> | null
}

export interface ActivityHistoryItem {
  id: string
  title: string
  subtitle?: string
  status?: string
  created_at?: string
}

export interface ActivityHistoryCategory {
  key: string
  title: string
  description: string
  count: number
  navigation_view: string
  items: ActivityHistoryItem[]
}

export interface ActivityHistoryResponse {
  generated_at: string
  scope_note: string
  categories: ActivityHistoryCategory[]
}

export interface SpriCORunRecord {
  id: string
  run_id: string
  run_type: string
  source_page: string
  target_id?: string | null
  target_name?: string | null
  target_type?: string | null
  domain?: string | null
  policy_id?: string | null
  policy_name?: string | null
  engine_id?: string | null
  engine_name?: string | null
  engine_version?: string | null
  status?: string | null
  evaluation_status?: string | null
  started_at?: string | null
  finished_at?: string | null
  duration_seconds?: number | null
  evidence_count: number
  findings_count: number
  final_verdict?: string | null
  violation_risk?: string | null
  coverage_summary: Record<string, unknown>
  artifact_count: number
  created_by?: string | null
  metadata: Record<string, unknown>
  legacy_source_ref: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
}

export interface SpriCORunSummaryBucket {
  label: string
  count: number
}

export interface SpriCORunSummary {
  generated_at: string
  total_runs: number
  by_run_type: SpriCORunSummaryBucket[]
  by_source_page: SpriCORunSummaryBucket[]
  by_status: SpriCORunSummaryBucket[]
  by_final_verdict: SpriCORunSummaryBucket[]
  coverage: {
    no_finding_runs: number
    runs_with_findings: number
    not_evaluated_runs: number
    evidence_total: number
    findings_total: number
    artifact_total: number
    targets_covered: number
  }
  recent_runs: SpriCORunRecord[]
}

export interface SpriCOFinding {
  id: string
  finding_id: string
  run_id?: string | null
  run_type?: string | null
  evidence_ids: string[]
  target_id?: string | null
  target_name?: string | null
  target_type?: string | null
  source_page: string
  engine_id?: string | null
  engine_name?: string | null
  domain?: string | null
  policy_id?: string | null
  policy_name?: string | null
  category?: string | null
  severity: string
  status: string
  title: string
  description: string
  root_cause?: string | null
  remediation?: string | null
  owner?: string | null
  review_status: string
  created_at: string
  updated_at: string
  final_verdict?: string | null
  violation_risk?: string | null
  data_sensitivity?: string | null
  matched_signals: Array<Record<string, unknown>>
  policy_context: Record<string, unknown>
  prompt_excerpt?: string | null
  response_excerpt?: string | null
  legacy_source_ref: Record<string, unknown>
  [key: string]: unknown
}

export interface ShieldCheckRequest {
  messages: Array<{ role: string; content: string }>
  project_id?: string | null
  target_id?: string | null
  policy_id?: string | null
  metadata?: Record<string, unknown>
  payload?: boolean
  breakdown?: boolean
  dev_info?: boolean
}

export interface ShieldCheckResponse {
  flagged: boolean
  decision: 'allow' | 'warn' | 'block' | 'mask' | 'escalate'
  verdict: 'PASS' | 'WARN' | 'FAIL' | 'NEEDS_REVIEW'
  violation_risk: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  data_sensitivity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  matched_signals: Array<Record<string, unknown>>
  payload: Array<Record<string, unknown>>
  breakdown: Array<Record<string, unknown>>
  metadata: Record<string, unknown>
  dev_info: Record<string, unknown>
}

export interface SpriCOProject {
  id: string
  name: string
  description?: string | null
  application_id?: string | null
  environment: string
  target_ids: string[]
  policy_id: string
  metadata_tags: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface SpriCOPolicy {
  id: string
  name: string
  version: string
  mode: string
  sensitivity: string
  target_domain?: string
  enabled_guardrails: Record<string, boolean>
  apply_to: string[]
  custom_detectors: Array<Record<string, unknown>>
  allowed_domains: string[]
  deny_domains: string[]
  allow_list: Array<Record<string, unknown>>
  deny_list: Array<Record<string, unknown>>
  retention: Record<string, unknown>
  redaction: Record<string, unknown>
  audit_history: Array<Record<string, unknown>>
}

export interface SpriCOEvidenceItem {
  id?: string
  evidence_id?: string
  finding_id: string
  created_at: string
  timestamp?: string | null
  run_id?: string | null
  run_type?: string | null
  source_page?: string | null
  engine: string
  engine_id?: string | null
  engine_name?: string | null
  engine_type?: string | null
  source_type?: string | null
  engine_version?: string | null
  license_id?: string | null
  source_url?: string | null
  source_file?: string | null
  target_id?: string | null
  target_name?: string | null
  target_type?: string | null
  scan_id?: string | null
  session_id?: string | null
  conversation_id?: string | null
  turn_id?: string | null
  evidence_type?: string | null
  project_id?: string | null
  policy_id?: string | null
  policy_name?: string | null
  policy_context: Record<string, unknown>
  authorization_context?: Record<string, unknown>
  raw_input?: string | null
  raw_output?: string | null
  retrieved_context?: Array<Record<string, unknown>>
  tool_calls?: Array<Record<string, unknown>>
  raw_result?: Record<string, unknown>
  raw_engine_result: Record<string, unknown>
  scanner_result?: Record<string, unknown> | null
  artifact_refs?: Array<Record<string, unknown> | string>
  scanner_artifact_refs?: Array<Record<string, unknown> | string>
  assertion_results?: Array<Record<string, unknown>>
  normalized_signal?: Array<Record<string, unknown>>
  normalized_signals?: Array<Record<string, unknown>>
  matched_signals: Array<Record<string, unknown>>
  matched_conditions?: string[]
  final_verdict?: string | null
  violation_risk?: string | null
  data_sensitivity?: string | null
  sprico_final_verdict?: Record<string, unknown>
  reviewer_override?: string | null
  redaction_status?: string | null
  hash?: string | null
  linked_finding_ids?: string[]
}

export interface RedObjective {
  id: string
  category: string
  name: string
  description: string
  expected_harmful_output: string
  required_detectors: string[]
  default_policy_mode: string
  default_strategies: string[]
  standards_mappings: string[]
  severity_default: string
}

export interface RedScan {
  id: string
  run_id?: string | null
  target_id?: string | null
  recon_context: Record<string, unknown>
  objective_ids: string[]
  policy_id?: string | null
  engine?: string | null
  max_turns?: number
  max_objectives?: number
  converters?: string[]
  scorers?: string[]
  status: string
  error_message?: string | null
  results: Array<Record<string, unknown>>
  findings?: Array<Record<string, unknown>>
  risk: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface OpenSourceComponent {
  id: 'garak' | 'deepteam' | 'promptfoo' | string
  name: string
  license_id: string
  license_name: string
  upstream_url: string
  local_use: string
  version: string
  source_notice: string
  license_file: string
  source_file: string
  version_file: string
  license_url: string
  source_url: string
  version_url: string
}

export interface ExternalEngineEntry {
  id: string
  name: string
  engine_type: 'attack' | 'evidence' | string
  available: boolean
  optional: boolean
  metadata_only?: boolean
  enabled_by_default?: boolean
  final_verdict_capable: boolean
  can_generate_attacks?: boolean
  can_generate_evidence?: boolean
  can_produce_final_verdict?: boolean
  license_id?: string | null
  source_url?: string | null
  source_file?: string | null
  license_component_id?: string | null
  installed_version?: string | null
  install_hint?: string | null
}

export interface ExternalEngineMatrix {
  message: string
  attack_engines: ExternalEngineEntry[]
  evidence_engines: ExternalEngineEntry[]
  optional_judge_models: Array<Record<string, unknown>>
  domain_policy_pack_required: boolean
  final_verdict_authority: Record<string, unknown>
  regulated_domain_lock: Record<string, unknown>
  garak_status: GarakStatus
  legal_components: Record<string, OpenSourceComponent>
}

export interface SpriCOCondition {
  condition_id: string
  id: string
  name: string
  description?: string | null
  version: string
  status: string
  activation_state: string
  condition_type: string
  parameters: Record<string, unknown>
  author: string
  approver?: string | null
  domain: string
  policy_modes: string[]
  data_sensitivity: string
  violation_risk: string
  requires_authorization: boolean
  requires_minimum_necessary: boolean
  test_cases: Array<Record<string, unknown>>
  simulation_result?: Record<string, unknown> | null
  activation_timestamp?: string | null
  rollback_target?: string | null
  version_frozen: boolean
  audit_history: Array<Record<string, unknown>>
  created_at: string
  updated_at: string
}

export interface CreateConditionRequest {
  condition_id?: string
  name: string
  description?: string
  condition_type: string
  parameters: Record<string, unknown>
  author: string
  domain: string
  policy_modes: string[]
  data_sensitivity: string
  violation_risk: string
  requires_authorization?: boolean
  requires_minimum_necessary?: boolean
  rollback_target?: string
}
