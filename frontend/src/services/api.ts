import axios from 'axios'
import { toApiError } from './errors'
import type {
  TargetInstance,
  TargetConfigView,
  TargetListResponse,
  CreateTargetRequest,
  UpdateTargetConfigRequest,
  CreateAttackRequest,
  CreateAttackResponse,
  AttackSummary,
  AttackListResponse,
  ConversationMessagesResponse,
  AddMessageRequest,
  AddMessageResponse,
  AttackConversationsResponse,
  CreateConversationRequest,
  CreateConversationResponse,
  ChangeMainConversationResponse,
  InteractiveAuditConversation,
  AuditOptionsResponse,
  AuditTest,
  AuditVariant,
  CreateAuditRunRequest,
  CreateAuditVariantRequest,
  AuditRun,
  AuditDashboardResponse,
  HeatmapDashboardResponse,
  StabilityDashboardResponse,
  StabilityGroupDetailResponse,
  RetrievalTrace,
  TargetCapability,
  BenchmarkLibraryResponse,
  BenchmarkSource,
  BenchmarkScenario,
  BenchmarkMedia,
  BenchmarkTaxonomyRow,
  BenchmarkCompareResponse,
  BenchmarkReplayRequest,
  CreateBenchmarkSourceRequest,
  FlipAttackImportRequest,
  AuditReportPayload,
  CreateRetrievalTraceRequest,
  WorkbookImportResponse,
  GarakScanRequest,
  GarakScanReport,
  GarakScanReportsResponse,
  GarakScannerReportSummary,
  GarakScanResult,
  GarakStatus,
  JudgeStatus,
  ShieldCheckRequest,
  ShieldCheckResponse,
  SpriCOProject,
  SpriCOPolicy,
  SpriCOEvidenceItem,
  SpriCOCondition,
  CreateConditionRequest,
  OpenSourceComponent,
  ExternalEngineMatrix,
  RedObjective,
  RedScan,
  StorageStatus,
  ActivityHistoryResponse,
  VersionInfo,
} from '../types'

export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 5 * 60 * 1000, // 5 minutes – video generation can take a while
})

// ---------------------------------------------------------------------------
// Request interceptor: attach X-Request-ID for log correlation
// ---------------------------------------------------------------------------

/** Generate a UUID v4, falling back to Math.random for HTTP dev environments. */
function generateRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback for environments without crypto.randomUUID
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

apiClient.interceptors.request.use((config) => {
  config.headers.set('X-Request-ID', generateRequestId())
  return config
})

// ---------------------------------------------------------------------------
// Response interceptor: log errors with request context
// ---------------------------------------------------------------------------

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const apiError = toApiError(error)
    const method = error?.config?.method?.toUpperCase() ?? '?'
    const url = error?.config?.url ?? '?'
    const requestId = error?.config?.headers?.['X-Request-ID'] ?? ''

    if (apiError.status === 404 && url === '/judge/status') {
      return Promise.reject(error)
    }
    if (apiError.status === 404 && url === '/scans/garak/reports') {
      return Promise.reject(error)
    }

    console.error(
      `[API] ${method} ${url} failed | status=${apiError.status ?? 'N/A'} | ` +
        `requestId=${requestId} | ${apiError.detail}`
    )

    return Promise.reject(error)
  }
)

export { apiClient }

function asTrimmedString(value: unknown, fallback = ''): string {
  if (typeof value === 'string') return value
  if (value == null) return fallback
  return String(value)
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map(item => asTrimmedString(item))
    .filter(item => item.trim().length > 0)
}

function normalizeAuditTest(test: AuditTest): AuditTest {
  const promptSequence = asTrimmedString((test as any).prompt_sequence)
  const promptSteps = normalizeStringArray((test as any).prompt_steps)
  const basePromptSequence = asTrimmedString((test as any).base_prompt_sequence, promptSequence)
  const basePromptSteps = normalizeStringArray((test as any).base_prompt_steps)
  const adversarialPromptSequenceRaw = asTrimmedString((test as any).adversarial_prompt_sequence)
  const adversarialPromptSequence = adversarialPromptSequenceRaw.trim() ? adversarialPromptSequenceRaw : null
  const adversarialPromptSteps = normalizeStringArray((test as any).adversarial_prompt_steps)
  const industryType = asTrimmedString((test as any).industry_type, 'Generic').trim() || 'Generic'
  const categoryName = asTrimmedString((test as any).category_name || (test as any).source_sheet_name, 'Unspecified').trim() || 'Unspecified'
  const canonicalQuestion = asTrimmedString((test as any).canonical_question)
  const safeBasePromptSequence = asTrimmedString((test as any).safe_base_prompt_sequence, basePromptSequence)
  const unsafeBasePromptSequenceRaw = asTrimmedString((test as any).unsafe_base_prompt_sequence)
  const safeAdversarialPromptSequenceRaw = asTrimmedString((test as any).safe_adversarial_prompt_sequence, adversarialPromptSequence ?? '')
  const unsafeAdversarialPromptSequenceRaw = asTrimmedString((test as any).unsafe_adversarial_prompt_sequence)
  const expectedAnswer = asTrimmedString((test as any).expected_answer, (test as any).expected_behavior)
  const hasAdversarialPrompt = Boolean(
    adversarialPromptSequence ||
    safeAdversarialPromptSequenceRaw.trim() ||
    unsafeAdversarialPromptSequenceRaw.trim()
  )

  return {
    ...test,
    industry_type: industryType,
    category_name: categoryName,
    canonical_question: canonicalQuestion.trim() ? canonicalQuestion : null,
    prompt_sequence: promptSequence,
    prompt_steps: promptSteps,
    base_prompt_sequence: basePromptSequence,
    base_prompt_steps: basePromptSteps.length ? basePromptSteps : promptSteps,
    adversarial_prompt_sequence: adversarialPromptSequence,
    adversarial_prompt_steps: adversarialPromptSteps,
    safe_base_prompt_sequence: safeBasePromptSequence,
    unsafe_base_prompt_sequence: unsafeBasePromptSequenceRaw.trim() ? unsafeBasePromptSequenceRaw : null,
    safe_adversarial_prompt_sequence: safeAdversarialPromptSequenceRaw.trim() ? safeAdversarialPromptSequenceRaw : null,
    unsafe_adversarial_prompt_sequence: unsafeAdversarialPromptSequenceRaw.trim() ? unsafeAdversarialPromptSequenceRaw : null,
    has_adversarial_prompt: hasAdversarialPrompt,
    expected_answer: expectedAnswer.trim() ? expectedAnswer : null,
  }
}

export const healthApi = {
  checkHealth: async () => {
    const response = await apiClient.get('/health')
    return response.data
  },
}

export const versionApi = {
  getVersion: async (): Promise<VersionInfo> => {
    const response = await apiClient.get('/version')
    return response.data
  },
}

export const targetsApi = {
  listTargets: async (limit = 50, cursor?: string): Promise<TargetListResponse> => {
    const params: Record<string, string | number> = { limit }
    if (cursor) params.cursor = cursor
    const response = await apiClient.get('/targets', { params })
    return response.data
  },

  getTarget: async (targetRegistryName: string): Promise<TargetInstance> => {
    const response = await apiClient.get(`/targets/${encodeURIComponent(targetRegistryName)}`)
    return response.data
  },

  getTargetConfig: async (targetRegistryName: string): Promise<TargetConfigView> => {
    const response = await apiClient.get(`/targets/${encodeURIComponent(targetRegistryName)}/config`)
    return response.data
  },

  updateTargetConfig: async (targetRegistryName: string, request: UpdateTargetConfigRequest): Promise<TargetConfigView> => {
    const response = await apiClient.patch(`/targets/${encodeURIComponent(targetRegistryName)}/config`, request)
    return response.data
  },

  createTarget: async (request: CreateTargetRequest): Promise<TargetInstance> => {
    const response = await apiClient.post('/targets', request)
    return response.data
  },

  getActiveTarget: async (): Promise<TargetInstance> => {
    const response = await apiClient.get('/targets/active')
    return response.data
  },

  activateTarget: async (targetRegistryName: string): Promise<TargetInstance> => {
    const response = await apiClient.post(`/targets/${encodeURIComponent(targetRegistryName)}/activate`)
    return response.data
  },

  archiveTarget: async (targetRegistryName: string, reason?: string): Promise<TargetInstance> => {
    const response = await apiClient.post(`/targets/${encodeURIComponent(targetRegistryName)}/archive`, { reason: reason ?? null })
    return response.data
  },
}

export const attacksApi = {
  createAttack: async (request: CreateAttackRequest): Promise<CreateAttackResponse> => {
    const response = await apiClient.post('/attacks', request)
    return response.data
  },

  getAttack: async (attackResultId: string): Promise<AttackSummary> => {
    const response = await apiClient.get(`/attacks/${encodeURIComponent(attackResultId)}`)
    return response.data
  },

  getMessages: async (attackResultId: string, conversationId: string): Promise<ConversationMessagesResponse> => {
    const response = await apiClient.get(
      `/attacks/${encodeURIComponent(attackResultId)}/messages`,
      { params: { conversation_id: conversationId } }
    )
    return response.data
  },

  addMessage: async (attackResultId: string, request: AddMessageRequest): Promise<AddMessageResponse> => {
    const response = await apiClient.post(
      `/attacks/${encodeURIComponent(attackResultId)}/messages`,
      request
    )
    return response.data
  },

  getConversations: async (attackResultId: string): Promise<AttackConversationsResponse> => {
    const response = await apiClient.get(
      `/attacks/${encodeURIComponent(attackResultId)}/conversations`
    )
    return response.data
  },

  createConversation: async (
    attackResultId: string,
    request: CreateConversationRequest
  ): Promise<CreateConversationResponse> => {
    const response = await apiClient.post(
      `/attacks/${encodeURIComponent(attackResultId)}/conversations`,
      request
    )
    return response.data
  },

  changeMainConversation: async (
    attackResultId: string,
    conversationId: string
  ): Promise<ChangeMainConversationResponse> => {
    const response = await apiClient.post(
      `/attacks/${encodeURIComponent(attackResultId)}/update-main-conversation`,
      { conversation_id: conversationId }
    )
    return response.data
  },

  listAttacks: async (params?: {
    limit?: number
    cursor?: string
    attack_type?: string
    converter_types?: string[]
    outcome?: string
    label?: string[]
    min_turns?: number
    max_turns?: number
  }): Promise<AttackListResponse> => {
    const response = await apiClient.get('/attacks', {
      params,
      paramsSerializer: {
        indexes: null, // serialize arrays as ?key=val1&key=val2
      },
    })
    return response.data
  },

  getAttackOptions: async (): Promise<{ attack_types: string[] }> => {
    const response = await apiClient.get('/attacks/attack-options')
    return response.data
  },

  getConverterOptions: async (): Promise<{ converter_types: string[] }> => {
    const response = await apiClient.get('/attacks/converter-options')
    return response.data
  },
}

export const labelsApi = {
  getLabels: async (source: string = 'attacks'): Promise<{ source: string; labels: Record<string, string[]> }> => {
    const response = await apiClient.get('/labels', { params: { source } })
    return response.data
  },
}

export const scoringApi = {
  scoreResponse: async (responseText: string, attackId?: string): Promise<any> => {
    const response = await apiClient.post('/score', {
      response_text: responseText,
      attack_id: attackId,
    })
    return response.data
  },
}

function summarizeGarakReports(reports: GarakScanReport[]): GarakScannerReportSummary {
  return {
    scanner_runs_total: reports.length,
    scanner_runs_by_status: counterRows(reports, report => asTrimmedString(report.status, 'unknown'), 'status'),
    scanner_runs_by_target: counterRows(reports, report => asTrimmedString(report.target_name ?? report.target_id, 'unknown'), 'target'),
    scanner_runs_by_profile: counterRows(reports, report => asTrimmedString(report.scan_profile, 'unknown'), 'profile'),
    scanner_runs_with_findings: reports.filter(report => numberValue(report.findings_count) > 0).length,
    scanner_runs_with_no_findings: reports.filter(report => asTrimmedString(report.status).toLowerCase() === 'completed_no_findings').length,
    scanner_runs_timeout: reports.filter(report => asTrimmedString(report.status).toLowerCase() === 'timeout').length,
    scanner_runs_failed: reports.filter(report => ['failed', 'unavailable', 'incompatible_target', 'parsing_failed', 'validation_failed', 'not_evaluated'].includes(asTrimmedString(report.status).toLowerCase())).length,
    high_critical_scanner_findings: reports.filter(report => {
      const risk = asTrimmedString(report.violation_risk ?? report.risk).toUpperCase()
      if (risk === 'HIGH' || risk === 'CRITICAL') return true
      return (report.findings ?? []).some(item => {
        const finding = item as Record<string, unknown>
        const severity = asTrimmedString(finding.severity).toUpperCase()
        return severity === 'HIGH' || severity === 'CRITICAL'
      })
    }).length,
    scanner_findings_by_severity: severityCounterRows(reports.flatMap(report => (report.findings ?? []) as Array<Record<string, unknown>>)),
    scanner_evidence_count: reports.reduce((total, report) => total + numberValue(report.evidence_count), 0),
    artifacts_stored: reports.reduce((total, report) => total + numberValue(report.artifact_count ?? report.artifacts?.length), 0),
  }
}

function counterRows<K extends 'status' | 'target' | 'profile'>(
  reports: GarakScanReport[],
  selector: (report: GarakScanReport) => string,
  key: K
): Array<Record<K, string> & { count: number }> {
  const counts = new Map<string, number>()
  reports.forEach(report => {
    const value = selector(report) || 'unknown'
    counts.set(value, (counts.get(value) ?? 0) + 1)
  })
  return Array.from(counts.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([value, count]) => ({ [key]: value, count } as Record<K, string> & { count: number }))
}

function numberValue(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function severityCounterRows(findings: Array<Record<string, unknown>>): Array<{ severity: string; count: number }> {
  const counts = new Map<string, number>()
  findings.forEach(finding => {
    const value = asTrimmedString(finding.severity ?? finding.violation_risk ?? finding.risk, 'UNKNOWN')
    counts.set(value, (counts.get(value) ?? 0) + 1)
  })
  return Array.from(counts.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([severity, count]) => ({ severity, count }))
}

export const garakApi = {
  getStatus: async (): Promise<GarakStatus> => {
    const response = await apiClient.get('/garak/status')
    return response.data
  },

  getPlugins: async (): Promise<Record<string, unknown>> => {
    const response = await apiClient.get('/integrations/garak/plugins')
    return response.data
  },

  getCompatibility: async (): Promise<Record<string, unknown>> => {
    const response = await apiClient.get('/integrations/garak/compatibility')
    return response.data
  },

  createScan: async (request: GarakScanRequest): Promise<GarakScanResult> => {
    const response = await apiClient.post('/scans/garak', request)
    return response.data
  },

  listScans: async (): Promise<GarakScanResult[]> => {
    const response = await apiClient.get('/scans/garak')
    return response.data
  },

  listReports: async (): Promise<GarakScanReportsResponse> => {
    try {
      const response = await apiClient.get('/scans/garak/reports')
      return response.data
    } catch (err) {
      const apiError = toApiError(err)
      if (apiError.status !== 404) {
        throw err
      }
      const fallback = await apiClient.get('/scans/garak')
      const reports = Array.isArray(fallback.data) ? fallback.data as GarakScanReport[] : []
      return {
        reports,
        summary: summarizeGarakReports(reports),
      }
    }
  },

  getReport: async (scanId: string): Promise<GarakScanReport> => {
    const response = await apiClient.get(`/scans/garak/reports/${encodeURIComponent(scanId)}`)
    return response.data
  },

  getReportSummary: async (): Promise<GarakScannerReportSummary> => {
    const response = await apiClient.get('/scans/garak/reports/summary')
    return response.data
  },

  getScan: async (scanId: string): Promise<GarakScanResult> => {
    const response = await apiClient.get(`/scans/garak/${encodeURIComponent(scanId)}`)
    return response.data
  },

  getFindings: async (scanId: string): Promise<Record<string, unknown>> => {
    const response = await apiClient.get(`/scans/garak/${encodeURIComponent(scanId)}/findings`)
    return response.data
  },

  getArtifacts: async (scanId: string): Promise<Record<string, unknown>> => {
    const response = await apiClient.get(`/scans/garak/${encodeURIComponent(scanId)}/artifacts`)
    return response.data
  },
}

export const judgeApi = {
  getStatus: async (): Promise<JudgeStatus> => {
    const response = await apiClient.get('/judge/status')
    return response.data
  },
}

export const shieldApi = {
  check: async (request: ShieldCheckRequest): Promise<ShieldCheckResponse> => {
    const response = await apiClient.post('/shield/check', request)
    return response.data
  },
}

export const spricoProjectsApi = {
  list: async (): Promise<SpriCOProject[]> => {
    const response = await apiClient.get('/projects')
    return response.data
  },

  create: async (request: Partial<SpriCOProject> & { name: string }): Promise<SpriCOProject> => {
    const response = await apiClient.post('/projects', request)
    return response.data
  },

  update: async (projectId: string, patch: Partial<SpriCOProject>): Promise<SpriCOProject> => {
    const response = await apiClient.patch(`/projects/${encodeURIComponent(projectId)}`, patch)
    return response.data
  },
}

export const spricoPoliciesApi = {
  list: async (): Promise<SpriCOPolicy[]> => {
    const response = await apiClient.get('/policies')
    return response.data
  },

  create: async (request: Partial<SpriCOPolicy> & { name: string }): Promise<SpriCOPolicy> => {
    const response = await apiClient.post('/policies', request)
    return response.data
  },

  update: async (policyId: string, patch: Partial<SpriCOPolicy>): Promise<SpriCOPolicy> => {
    const response = await apiClient.patch(`/policies/${encodeURIComponent(policyId)}`, patch)
    return response.data
  },

  simulate: async (policyId: string, messages: Array<{ role: string; content: string }>, metadata?: Record<string, unknown>): Promise<ShieldCheckResponse> => {
    const response = await apiClient.post(`/policies/${encodeURIComponent(policyId)}/simulate`, { messages, metadata: metadata ?? {} })
    return response.data
  },

  auditHistory: async (policyId: string): Promise<{ policy_id: string; audit_history: Array<Record<string, unknown>> }> => {
    const response = await apiClient.get(`/policies/${encodeURIComponent(policyId)}/audit-history`)
    return response.data
  },

  versions: async (policyId: string): Promise<{ policy_id: string; versions: Array<Record<string, unknown>> }> => {
    const response = await apiClient.get(`/policies/${encodeURIComponent(policyId)}/versions`)
    return response.data
  },
}

export const spricoRedApi = {
  objectives: async (): Promise<RedObjective[]> => {
    const response = await apiClient.get('/red/objectives')
    return response.data
  },

  listScans: async (): Promise<RedScan[]> => {
    const response = await apiClient.get('/red/scans')
    return response.data
  },

  createScan: async (request: {
    target_id: string
    objective_ids?: string[]
    policy_id?: string
    engine?: string
    max_turns?: number
    max_objectives?: number
    converters?: string[]
    scorers?: string[]
    recon_context?: Record<string, unknown>
    policy_context?: Record<string, unknown>
    permission_attestation?: boolean
  }): Promise<RedScan> => {
    const response = await apiClient.post('/red/scans', request)
    return response.data
  },

  getScan: async (scanId: string): Promise<RedScan> => {
    const response = await apiClient.get(`/red/scans/${encodeURIComponent(scanId)}`)
    return response.data
  },

  compare: async (scanId: string, otherScanId: string): Promise<Record<string, unknown>> => {
    const response = await apiClient.post(`/red/scans/${encodeURIComponent(scanId)}/compare`, { scan_id: otherScanId })
    return response.data
  },
}

export const spricoEvidenceApi = {
  list: async (params?: {
    limit?: number
    scan_id?: string
    engine?: string
    engine_type?: string
    policy_id?: string
    risk?: string
    final_verdict?: string
    evidence_id?: string
  }): Promise<SpriCOEvidenceItem[]> => {
    const response = await apiClient.get('/evidence', { params })
    return response.data
  },
}

export const legalApi = {
  listOpenSourceComponents: async (): Promise<OpenSourceComponent[]> => {
    const response = await apiClient.get('/legal/open-source-components')
    return response.data
  },

  getOpenSourceComponent: async (componentId: string): Promise<OpenSourceComponent> => {
    const response = await apiClient.get(`/legal/open-source-components/${encodeURIComponent(componentId)}`)
    return response.data
  },
}

export const externalEnginesApi = {
  getMatrix: async (): Promise<ExternalEngineMatrix> => {
    const response = await apiClient.get('/external-engines')
    return response.data
  },
}

export const storageApi = {
  getStatus: async (): Promise<StorageStatus> => {
    const response = await apiClient.get('/storage/status')
    return response.data
  },
}

export const activityApi = {
  getHistory: async (limit = 5): Promise<ActivityHistoryResponse> => {
    const response = await apiClient.get('/activity/history', { params: { limit } })
    return response.data
  },
}

export const spricoConditionsApi = {
  types: async (): Promise<{ allowed_condition_types: string[]; final_verdict_authority: string; code_execution_allowed: boolean }> => {
    const response = await apiClient.get('/conditions/types')
    return response.data
  },

  list: async (): Promise<SpriCOCondition[]> => {
    const response = await apiClient.get('/conditions')
    return response.data
  },

  create: async (request: CreateConditionRequest): Promise<SpriCOCondition> => {
    const response = await apiClient.post('/conditions', request)
    return response.data
  },

  simulate: async (conditionId: string, request: { text: string; policy_context?: Record<string, unknown>; actor?: string }): Promise<Record<string, unknown>> => {
    const response = await apiClient.post(`/conditions/${encodeURIComponent(conditionId)}/simulate`, request)
    return response.data
  },

  addTest: async (conditionId: string, request: { name: string; input_text: string; expected_match: boolean; policy_context?: Record<string, unknown>; actor?: string }): Promise<SpriCOCondition> => {
    const response = await apiClient.post(`/conditions/${encodeURIComponent(conditionId)}/tests`, request)
    return response.data
  },

  approve: async (conditionId: string, request: { approver: string; notes?: string }): Promise<SpriCOCondition> => {
    const response = await apiClient.post(`/conditions/${encodeURIComponent(conditionId)}/approve`, request)
    return response.data
  },

  activate: async (conditionId: string, request: { actor?: string }): Promise<SpriCOCondition> => {
    const response = await apiClient.post(`/conditions/${encodeURIComponent(conditionId)}/activate`, request)
    return response.data
  },

  retire: async (conditionId: string, request: { actor?: string; reason?: string }): Promise<SpriCOCondition> => {
    const response = await apiClient.post(`/conditions/${encodeURIComponent(conditionId)}/retire`, request)
    return response.data
  },

  rollback: async (conditionId: string, request: { actor?: string; rollback_target: string }): Promise<SpriCOCondition> => {
    const response = await apiClient.post(`/conditions/${encodeURIComponent(conditionId)}/rollback`, request)
    return response.data
  },

  versions: async (conditionId: string): Promise<{ condition_id: string; versions: Array<Record<string, unknown>> }> => {
    const response = await apiClient.get(`/conditions/${encodeURIComponent(conditionId)}/versions`)
    return response.data
  },

  auditHistory: async (conditionId: string): Promise<{ condition_id: string; audit_history: Array<Record<string, unknown>> }> => {
    const response = await apiClient.get(`/conditions/${encodeURIComponent(conditionId)}/audit-history`)
    return response.data
  },
}

export const auditApi = {
  getOptions: async (params?: { industries?: string[] }): Promise<AuditOptionsResponse> => {
    const response = await apiClient.get('/categories', {
      params: {
        industry: params?.industries,
      },
      paramsSerializer: {
        indexes: null,
      },
    })
    const data = response.data ?? {}
    const normalizeOption = (item: any) => ({
      name: asTrimmedString(item?.name, 'Unspecified').trim() || 'Unspecified',
      source_sheet_name: item?.source_sheet_name == null ? null : asTrimmedString(item.source_sheet_name),
      test_count: Number(item?.test_count ?? 0),
    })
    return {
      industries: Array.isArray(data.industries) ? data.industries.map(normalizeOption) : [],
      categories: Array.isArray(data.categories) ? data.categories.map(normalizeOption) : [],
      domains: Array.isArray(data.domains) ? data.domains.map(normalizeOption) : [],
      has_real_domains: Boolean(data.has_real_domains),
      total_tests: Number(data.total_tests ?? 0),
      database_path: asTrimmedString(data.database_path),
    }
  },

  listTests: async (params?: { industries?: string[]; categories?: string[]; domains?: string[] }): Promise<{ tests: AuditTest[]; count: number }> => {
    const requestParams: Record<string, string[] | undefined> = {
      industry: params?.industries,
      category: params?.categories,
      domain: params?.domains,
    }
    const response = await apiClient.get('/tests', {
      params: requestParams,
      paramsSerializer: {
        indexes: null,
      },
    })
    return {
      ...response.data,
      tests: Array.isArray(response.data?.tests) ? response.data.tests.map((item: AuditTest) => normalizeAuditTest(item)) : [],
      count: Number(response.data?.count ?? 0),
    }
  },

  importWorkbook: async (request: { file: File; industryType: string; sourceLabel?: string | null }): Promise<WorkbookImportResponse> => {
    const formData = new FormData()
    formData.append('workbook_file', request.file)
    formData.append('industry_type', request.industryType)
    if (request.sourceLabel?.trim()) {
      formData.append('source_label', request.sourceLabel.trim())
    }
    const response = await apiClient.post('/audit/import-workbook', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  createRun: async (request: CreateAuditRunRequest): Promise<AuditRun> => {
    const response = await apiClient.post('/audit/run', request)
    return response.data
  },

  createVariant: async (testId: number, request: CreateAuditVariantRequest): Promise<AuditVariant> => {
    const response = await apiClient.post(`/audit/tests/${testId}/variants`, request)
    return response.data
  },

  getStatus: async (runId: string): Promise<AuditRun> => {
    const response = await apiClient.get(`/audit/status/${runId}`)
    return response.data
  },

  getResults: async (runId: string): Promise<AuditRun> => {
    const response = await apiClient.get(`/audit/results/${runId}`)
    return response.data
  },

  getInteractiveAudit: async (attackResultId: string, conversationId?: string): Promise<InteractiveAuditConversation> => {
    const response = await apiClient.get(`/audit/interactive/attacks/${encodeURIComponent(attackResultId)}`, {
      params: conversationId ? { conversation_id: conversationId } : undefined,
    })
    return response.data
  },

  listInteractiveRuns: async (limit = 100): Promise<AuditRun[]> => {
    const response = await apiClient.get('/audit/interactive/runs', { params: { limit } })
    return response.data
  },

  getInteractiveAuditRun: async (runId: string): Promise<InteractiveAuditConversation> => {
    const response = await apiClient.get(`/audit/interactive/runs/${encodeURIComponent(runId)}`)
    return response.data
  },

  saveInteractiveAudit: async (attackResultId: string, conversationId?: string): Promise<AuditRun> => {
    const response = await apiClient.post(`/audit/interactive/attacks/${encodeURIComponent(attackResultId)}/save`, null, {
      params: conversationId ? { conversation_id: conversationId } : undefined,
    })
    return response.data
  },

  getFindings: async (runId: string, params?: { verdict?: string; category?: string; severity?: string; search?: string }): Promise<AuditRun> => {
    const response = await apiClient.get(`/audit/findings/${runId}`, { params })
    return response.data
  },

  listRuns: async (limit = 10): Promise<AuditRun[]> => {
    const response = await apiClient.get('/audit/runs', { params: { limit } })
    return response.data
  },

  getDashboard: async (): Promise<AuditDashboardResponse> => {
    const response = await apiClient.get('/audit/dashboard')
    return response.data
  },

  getDashboardHeatmap: async () => {
    const response = await apiClient.get('/dashboard/heatmap')
    return response.data
  },

  getHeatmapDashboard: async (): Promise<HeatmapDashboardResponse> => {
    const response = await apiClient.get('/dashboard/heatmap-dashboard')
    return response.data
  },

  getStabilityDashboard: async (): Promise<StabilityDashboardResponse> => {
    const response = await apiClient.get('/dashboard/stability')
    return response.data
  },

  getStabilityGroup: async (groupId: number): Promise<StabilityGroupDetailResponse> => {
    const response = await apiClient.get(`/audit/stability/groups/${groupId}`)
    return response.data
  },

  getTargetCapabilities: async (): Promise<TargetCapability[]> => {
    const response = await apiClient.get('/target-capabilities')
    return response.data
  },

  getRetrievalTraces: async (physicalRunId: number): Promise<RetrievalTrace[]> => {
    const response = await apiClient.get(`/audit/stability/runs/${physicalRunId}/retrieval-traces`)
    return response.data
  },

  createRetrievalTrace: async (physicalRunId: number, request: CreateRetrievalTraceRequest): Promise<RetrievalTrace> => {
    const response = await apiClient.post(`/audit/stability/runs/${physicalRunId}/retrieval-traces`, request)
    return response.data
  },

  rerunStabilityGroup: async (groupId: number): Promise<AuditRun> => {
    const response = await apiClient.post(`/audit/stability/groups/${groupId}/rerun`)
    return response.data
  },

  getAuditReport: async (runId: string): Promise<AuditReportPayload> => {
    const response = await apiClient.get(`/audit/reports/${runId}`)
    return response.data
  },

  getBenchmarkLibrary: async (params?: { source_type?: string; category?: string; search?: string }): Promise<BenchmarkLibraryResponse> => {
    const response = await apiClient.get('/benchmarks/library', { params })
    return response.data
  },

  listBenchmarkSources: async (params?: { source_type?: string; benchmark_family?: string; limit?: number }): Promise<BenchmarkSource[]> => {
    const response = await apiClient.get('/benchmarks/sources', { params })
    return response.data
  },

  createBenchmarkSource: async (request: CreateBenchmarkSourceRequest): Promise<BenchmarkSource> => {
    const response = await apiClient.post('/benchmarks/sources', request)
    return response.data
  },

  importFlipAttackBenchmark: async (request: FlipAttackImportRequest): Promise<BenchmarkSource> => {
    const response = await apiClient.post('/benchmarks/flipattack/import', request)
    return response.data
  },

  listBenchmarkScenarios: async (params?: { source_type?: string; category?: string; search?: string; replay_supported?: boolean; limit?: number }): Promise<BenchmarkScenario[]> => {
    const response = await apiClient.get('/benchmarks/scenarios', { params })
    return response.data
  },

  listBenchmarkMedia: async (params?: { source_type?: string; scenario_id?: number }): Promise<BenchmarkMedia[]> => {
    const response = await apiClient.get('/benchmarks/media', { params })
    return response.data
  },

  getBenchmarkTaxonomy: async (): Promise<BenchmarkTaxonomyRow[]> => {
    const response = await apiClient.get('/benchmarks/taxonomy')
    return response.data
  },

  compareBenchmarkScenario: async (scenarioId: number): Promise<BenchmarkCompareResponse> => {
    const response = await apiClient.get(`/benchmarks/compare/${scenarioId}`)
    return response.data
  },

  replayBenchmarkScenario: async (scenarioId: number, request: BenchmarkReplayRequest): Promise<AuditRun> => {
    const response = await apiClient.post(`/benchmarks/scenarios/${scenarioId}/replay`, request)
    return response.data
  },
}
