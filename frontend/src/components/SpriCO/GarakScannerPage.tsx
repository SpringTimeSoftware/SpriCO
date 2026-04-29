import { useEffect, useMemo, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { garakApi, judgeApi, spricoPoliciesApi } from '../../services/api'
import { toApiError, type ApiError } from '../../services/errors'
import type { GarakScanReport, GarakScanResult, GarakStatus, JudgeStatus, SpriCOPolicy, TargetInstance } from '../../types'
import { Badge, EmptyMessage, FieldHelp, JsonView, LoadingMessage, PageHelp, formatDateTime, valueText } from './common'
import UnifiedTargetSelector, { describeTarget, isWorkflowCompatible } from './UnifiedTargetSelector'
import './spricoPlatform.css'

type PluginPayload = {
  plugins?: Record<string, string[]>
  errors?: Record<string, string>
}

const SCAN_PROFILES = [
  { id: 'quick_baseline', label: 'Quick Baseline', maxAttempts: 1, timeoutSeconds: 180 },
  { id: 'privacy_and_prompt_injection', label: 'Privacy & Prompt Injection', maxAttempts: 1, timeoutSeconds: 300 },
  { id: 'deep_llm_security', label: 'Deep LLM Security', maxAttempts: 2, timeoutSeconds: 600 },
]
const VULNERABILITY_CATEGORIES = [
  'Privacy & Data Leakage',
  'Prompt Injection & Jailbreaks',
  'System Prompt Extraction',
  'RAG Poisoning',
  'Agent / Tool Misuse',
  'Unsafe Medical Advice',
  'Hallucination / Unsupported Claims',
  'Authorization Boundary Bypass',
]
const NON_EVALUATED_STATUSES = new Set(['timeout', 'failed', 'unavailable', 'incompatible_target', 'parsing_failed', 'validation_failed', 'not_evaluated'])
const DEFAULT_JUDGE_STATUS: JudgeStatus = {
  enabled: false,
  configured: false,
  final_verdict_authority: 'sprico_policy_decision_engine',
  providers: [
    {
      id: 'openai',
      label: 'OpenAI Judge',
      configured: false,
      enabled: false,
      enabled_by_default: false,
      final_verdict_capable: false,
      supports_redaction: true,
      allowed_modes: ['disabled', 'redacted'],
      blocked_for_domains_by_default: ['healthcare', 'hospital'],
      configure_hint: 'Open Settings -> Judge Models to check backend judge configuration.',
    },
  ],
}

interface GarakScannerPageProps {
  onNavigate?: (view: 'config' | 'judge-models' | 'findings') => void
}

export default function GarakScannerPage({ onNavigate }: GarakScannerPageProps = {}) {
  const [status, setStatus] = useState<GarakStatus | null>(null)
  const [judgeStatus, setJudgeStatus] = useState<JudgeStatus>(DEFAULT_JUDGE_STATUS)
  const [judgeStatusSupported, setJudgeStatusSupported] = useState(false)
  const [plugins, setPlugins] = useState<PluginPayload | null>(null)
  const [policies, setPolicies] = useState<SpriCOPolicy[]>([])
  const [history, setHistory] = useState<GarakScanResult[]>([])
  const [selectedScan, setSelectedScan] = useState<GarakScanResult | null>(null)
  const [targetId, setTargetId] = useState('')
  const [selectedTarget, setSelectedTarget] = useState<TargetInstance | null>(null)
  const [policyId, setPolicyId] = useState('policy_hospital_strict_v1')
  const [scanProfile, setScanProfile] = useState('quick_baseline')
  const [categories, setCategories] = useState<string[]>(['Privacy & Data Leakage', 'Prompt Injection & Jailbreaks'])
  const [attested, setAttested] = useState(false)
  const [crossDomainOverride, setCrossDomainOverride] = useState(false)
  const [judgeEnabled, setJudgeEnabled] = useState(false)
  const [judgeMode, setJudgeMode] = useState('redacted')
  const [showDiagnostics, setShowDiagnostics] = useState(false)
  const [showSelectedRaw, setShowSelectedRaw] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanError, setScanError] = useState<ApiError | null>(null)

  const selectedPolicy = policies.find(policy => policy.id === policyId) ?? policies[0] ?? null
  const targetMetadata = selectedTarget ? describeTarget(selectedTarget) : null
  const selectedProfile = SCAN_PROFILES.find(profile => profile.id === scanProfile) ?? SCAN_PROFILES[0]
  const selectedCategoryCount = categories.length
  const allCategoriesSelected = selectedCategoryCount === VULNERABILITY_CATEGORIES.length
  const deepCategoryLimited = scanProfile === 'deep_llm_security' && selectedCategoryCount === 1
  const profileResolution = selectedScan?.profile_resolution ?? null
  const resolvedProbeCount = countResolutionList(profileResolution, 'probes')
  const skippedProbeCount = countSkippedResolution(profileResolution)
  const openAiJudge = judgeStatus?.providers.find(provider => provider.id === 'openai') ?? null
  const judgeProviderConfigured = Boolean(openAiJudge?.configured)
  const judgeRuntimeEnabled = Boolean(openAiJudge?.enabled && judgeStatus?.enabled)
  const policyDomain = selectedPolicy?.target_domain ?? 'general'
  const selectedTargetDomain = targetMetadata?.domain ?? 'unknown'
  const domainMismatch = domainsMismatch(selectedTargetDomain, policyDomain)
  const compatibility = scannerCompatibility(selectedTarget, status)
  const selectedResultTarget = valueText(selectedScan?.target_name ?? selectedScan?.target_id)
  const currentConfigTarget = valueText(targetMetadata?.name ?? targetId)
  const selectedResultDiffers = Boolean(selectedScan && currentConfigTarget && selectedResultTarget && selectedResultTarget !== currentConfigTarget)

  const browserRows = useMemo(() => {
    const source = plugins?.plugins ?? {}
    return ['probes', 'detectors', 'generators'].map(key => ({
      key,
      values: source[key] ?? [],
    }))
  }, [plugins])

  const load = async () => {
    setError(null)
    setScanError(null)
    try {
      const [statusResponse, pluginsResponse, historyResponse, policyResponse] = await Promise.all([
        garakApi.getStatus(),
        garakApi.getPlugins(),
        garakApi.listReports(),
        spricoPoliciesApi.list(),
      ])
      setStatus(statusResponse)
      setPlugins(pluginsResponse as PluginPayload)
      setHistory(historyResponse.reports)
      setSelectedScan(historyResponse.reports[0] ?? null)
      setPolicies(policyResponse)
      try {
        const judgeResponse = await judgeApi.getStatus()
        setJudgeStatus(judgeResponse)
        setJudgeStatusSupported(true)
        if (!judgeResponse.configured || !judgeResponse.enabled) {
          setJudgeEnabled(false)
        }
      } catch (judgeErr) {
        const apiError = toApiError(judgeErr)
        if (apiError.status === 404) {
          setJudgeStatus(DEFAULT_JUDGE_STATUS)
          setJudgeStatusSupported(false)
          setJudgeEnabled(false)
        } else {
          throw judgeErr
        }
      }
      if (policyResponse.length > 0 && !policyResponse.some(policy => policy.id === policyId)) {
        setPolicyId(policyResponse[0].id)
      }
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const validationMessage = validateScannerSelection({
    targetId,
    selectedTarget,
    attested,
    domainMismatch,
    crossDomainOverride,
    compatibility,
  })

  const runScan = async () => {
    const validation = validateScannerSelection({ targetId, selectedTarget, attested, domainMismatch, crossDomainOverride, compatibility })
    if (validation) {
      setScanError(null)
      setError(validation)
      return
    }
    setIsRunning(true)
    setError(null)
    setScanError(null)
    try {
      const policyContext: Record<string, unknown> = {
        policy_id: policyId,
        policy_mode: selectedPolicy?.mode ?? 'REDTEAM_STRICT',
        target_domain: selectedTargetDomain,
        policy_domain: policyDomain,
        selected_target_domain: selectedTargetDomain,
        cross_domain_override: domainMismatch && crossDomainOverride,
        target_id: targetId,
        target_name: targetMetadata?.name,
        target_type: selectedTarget?.target_type,
        scan_profile: scanProfile,
        vulnerability_categories: categories,
      }
      const request = {
        target_id: targetId,
        policy_id: policyId,
        scan_profile: scanProfile,
        vulnerability_categories: categories,
        max_attempts: selectedProfile.maxAttempts,
        timeout_seconds: selectedProfile.timeoutSeconds,
        permission_attestation: attested,
        policy_context: policyContext,
      }
      if (domainMismatch && crossDomainOverride) {
        Object.assign(request, { cross_domain_override: true })
      }
      if (judgeStatusSupported) {
        const judgeSettings = {
          enabled: judgeEnabled,
          provider: 'openai',
          mode: judgeMode,
          judge_only_ambiguous: true,
        }
        Object.assign(request, { judge_settings: judgeSettings })
        Object.assign(policyContext, {
          judge_settings: {
            enabled: judgeEnabled,
            provider: 'openai',
            mode: judgeMode,
            judge_only_ambiguous: true,
          },
        })
      }
      const result = await garakApi.createScan(request)
      setSelectedScan(result)
      setShowSelectedRaw(false)
      setHistory(prev => [result, ...prev.filter(item => item.scan_id !== result.scan_id)])
    } catch (err) {
      const apiError = toApiError(err)
      setScanError(apiError)
      setError(apiError.detail)
    } finally {
      setIsRunning(false)
    }
  }

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading LLM vulnerability scanner" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">LLM Vulnerability Scanner</div>
          <div className="sprico-subtitle">
            Run an LLM vulnerability scan against a configured target. External scanner engines provide evidence only; SpriCO PolicyDecisionEngine produces the final policy-aware verdict.
          </div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <PageHelp>
        Run broad LLM vulnerability scans against a target. SpriCO can use optional scanner engines such as garak to collect evidence. SpriCO PolicyDecisionEngine remains the final verdict authority.
      </PageHelp>

      <ScannerErrorMessage error={scanError} fallback={error} onOpenTargetConfig={onNavigate ? () => onNavigate('config') : undefined} />

      <section className="sprico-panel">
        <div className="sprico-panel-title">Current Scan Configuration</div>
        <div className="sprico-kpis">
          <Metric label="Selected Target" value={currentConfigTarget || 'No target selected'} />
          <Metric label="Selected Target Domain" value={selectedTargetDomain} />
          <Metric label="Selected Policy" value={selectedPolicy ? `${selectedPolicy.name} (${selectedPolicy.mode})` : policyId} />
          <Metric label="Policy Domain" value={policyDomain} />
          <Metric label="Selected Profile" value={selectedProfile.label} />
          <Metric label="Compatible with LLM Scanner" value={compatibility.workflowCompatible} />
          <Metric label="garak Scanner Compatibility" value={compatibility.garakCompatibility} />
        </div>
        <FieldHelp>{compatibility.reason}</FieldHelp>
        {domainMismatch && (
          <div className="sprico-message sprico-message-error">
            Selected target domain is {selectedTargetDomain}, but selected policy is {policyDomain}. Choose a matching policy or confirm cross-domain evaluation.
            <label className="sprico-checkbox-row">
              <input
                type="checkbox"
                checked={crossDomainOverride}
                onChange={event => setCrossDomainOverride(event.target.checked)}
              />
              <span>I confirm this cross-domain evaluation is intentional.</span>
            </label>
          </div>
        )}
      </section>

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Target & Permission</div>
          <div className="sprico-form">
            <UnifiedTargetSelector
              value={targetId}
              workflow="llm_scanner"
              onChange={(next, target) => {
                setTargetId(next)
                setSelectedTarget(target ?? null)
              }}
              help="Select a configured AI target from the same target registry used by Interactive Audit and Target Configuration."
            />
            <label className="sprico-checkbox-row">
              <input type="checkbox" checked={attested} onChange={event => setAttested(event.target.checked)} />
              <span>I attest that I have authorization to run scanner workflows against this configured target.</span>
            </label>
            {targetId && (
              <div className="sprico-kpis">
                <Metric label="Compatible with LLM Scanner" value={compatibility.workflowCompatible} />
                <Metric label="garak scanner compatibility" value={compatibility.garakCompatibility} />
              </div>
            )}
            {validationMessage && (
              <ClientValidationMessage
                message={validationMessage}
                onOpenTargetConfig={onNavigate ? () => onNavigate('config') : undefined}
              />
            )}
          </div>
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Domain Policy</div>
          <div className="sprico-form">
            <label className="sprico-field">
              <span className="sprico-label">Policy Pack</span>
              <FieldHelp>Controls domain, strictness, authorization context, and the policy rules used for the final SpriCO verdict.</FieldHelp>
              <select className="sprico-select" value={policyId} onChange={event => setPolicyId(event.target.value)}>
                {policies.map(policy => <option key={policy.id} value={policy.id}>{policy.name} ({policy.mode})</option>)}
                {policies.length === 0 && <option value="policy_hospital_strict_v1">Hospital Strict (default)</option>}
              </select>
            </label>
            <div className="sprico-kpi">
              <div className="sprico-kpi-label">Final Verdict Authority</div>
              <div className="sprico-kpi-value">SpriCO PolicyDecisionEngine</div>
              <FieldHelp>Locked for regulated-domain audits. Scanner output cannot override the final verdict.</FieldHelp>
            </div>
          </div>
        </section>
      </div>

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Scanner Setup</div>
          <div className="sprico-form">
            <label className="sprico-field">
              <span className="sprico-label">Scan Profile</span>
              <select className="sprico-select" value={scanProfile} onChange={event => setScanProfile(event.target.value)}>
                {SCAN_PROFILES.map(profile => <option key={profile.id} value={profile.id}>{profile.label}</option>)}
              </select>
              <FieldHelp>Profiles map to allowlisted scanner probes and categories on the backend. Raw CLI arguments are not accepted.</FieldHelp>
            </label>
            <div className="sprico-field">
              <span className="sprico-label">Vulnerability Categories</span>
              <div className="sprico-list">
                {VULNERABILITY_CATEGORIES.map(category => (
                  <label key={category} className="sprico-checkbox-row">
                    <input
                      type="checkbox"
                      checked={categories.includes(category)}
                      onChange={() => setCategories(prev => prev.includes(category) ? prev.filter(item => item !== category) : [...prev, category])}
                    />
                    <span>{category}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="sprico-kpis">
              <Metric label="Selected Profile" value={selectedProfile.label} />
              <Metric label="Selected Categories" value={`${selectedCategoryCount} of ${VULNERABILITY_CATEGORIES.length}`} />
              <Metric label="Resolved Probes" value={resolvedProbeCount === null ? 'Not resolved until run' : String(resolvedProbeCount)} />
              <Metric label="Skipped Probes" value={skippedProbeCount === null ? 'Not resolved until run' : String(skippedProbeCount)} />
              <Metric label="Default Generations" value={String(selectedProfile.maxAttempts)} />
              <Metric label="Timeout" value={`${selectedProfile.timeoutSeconds}s`} />
              <Metric label="Profile Scope" value={allCategoriesSelected ? 'Full profile run' : 'Category-limited run'} />
            </div>
            {deepCategoryLimited && (
              <div className="sprico-message sprico-message-error">
                Deep LLM Security profile selected, but only 1 category is enabled. This is not a full deep scan.
              </div>
            )}
            {!allCategoriesSelected && (
              <Button appearance="secondary" onClick={() => setCategories([...VULNERABILITY_CATEGORIES])}>
                Select all categories for this profile
              </Button>
            )}
            <Button appearance="primary" disabled={Boolean(validationMessage) || isRunning} onClick={() => void runScan()}>
              {isRunning ? 'Running' : 'Run Vulnerability Scan'}
            </Button>
          </div>
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Evidence Sources</div>
          <div className="sprico-message">External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.</div>
          <div className="sprico-kpis">
            <Metric label="Scanner Engine Status" value={status?.available ? 'Installed' : 'Not installed'} />
            <Metric label="garak version" value={status?.version ?? 'not installed'} />
            <Metric label="Target compatibility" value={compatibility.garakCompatibility} />
          </div>
          <div className="sprico-list">
            <SourceGroup
              title="Active"
              items={[{
                name: 'SpriCO Domain Signals',
                status: 'Active',
                description: 'Applies the selected policy/domain pack after scanner responses. This is required for final SpriCO verdicts.',
              }]}
            />
            <SourceGroup
              title="Scanner Evidence"
              items={[{
                name: 'garak Detector Evidence',
                status: garakSourceStatus(status, compatibility),
                description: 'Runs garak probes and detector checks. Produces scanner evidence only. It cannot override the final SpriCO verdict.',
              }]}
            />
            <JudgeEvidenceSource
              provider={openAiJudge}
              providerConfigured={judgeProviderConfigured}
              runtimeEnabled={judgeRuntimeEnabled}
              enabled={judgeEnabled}
              mode={judgeMode}
              regulatedDomain={isRegulatedDomain(selectedTargetDomain) || isRegulatedDomain(policyDomain)}
              onEnabledChange={setJudgeEnabled}
              onModeChange={setJudgeMode}
              onConfigure={onNavigate ? () => onNavigate('judge-models') : undefined}
            />
            <SourceGroup
              title="Not configured"
              items={[{
                name: 'PyRIT Scorers',
                status: 'Not wired for this scanner workflow',
                description: 'PyRIT scorer evidence is not wired for this scanner workflow. Interactive Audit and structured audits use PyRIT targets/memory, but this scanner path is garak-based.',
              }]}
            />
          </div>
          {!status?.available && (
            <div className="sprico-message">
              Optional garak scanner engine is not installed. SpriCO native checks are still available.
            </div>
          )}
        </section>
      </div>

      <section className="sprico-panel">
        <div className="sprico-panel-title">Advanced Diagnostics</div>
        <Button className="sprico-advanced-toggle" appearance="secondary" onClick={() => setShowDiagnostics(value => !value)}>
          {showDiagnostics ? 'Hide Advanced Diagnostics' : 'Show Advanced Diagnostics'}
        </Button>
        {showDiagnostics && (
          <div className="sprico-advanced-panel">
            <FieldHelp>Backend Python Environment and raw scanner diagnostics are shown for administrators troubleshooting optional scanner setup.</FieldHelp>
            <div className="sprico-kpis">
              <Metric label="garak status" value={status?.available ? 'Installed' : 'Not installed'} />
              <Metric label="garak version" value={status?.version ?? 'not installed'} />
              <Metric label="Backend Python Environment" value={status?.advanced?.python_version ?? status?.python ?? 'unknown'} />
              <Metric label="Executable" value={status?.advanced?.python_executable ?? status?.executable ?? 'unknown'} />
              <Metric label="Import Error" value={status?.advanced?.import_error ?? status?.import_error ?? 'none'} />
              <Metric label="CLI Error" value={status?.advanced?.cli_error ?? status?.cli_error ?? 'none'} />
              <Metric label="Install Hint" value={status?.install_hint ?? 'python -m pip install -e \".[garak]\"'} />
            </div>
            <div className="sprico-grid">
              {browserRows.map(row => (
                <div key={row.key} className="sprico-kpi">
                  <div className="sprico-kpi-label">{row.key}</div>
                  <div className="sprico-row-subtitle">{row.values.slice(0, 12).join(', ') || 'Unavailable'}</div>
                </div>
              ))}
            </div>
            {selectedScan?.profile_resolution && (
              <div className="sprico-kpi">
                <div className="sprico-kpi-label">Resolved Scanner Profile</div>
                <JsonView value={selectedScan.profile_resolution} />
              </div>
            )}
            {selectedScan?.artifacts && selectedScan.artifacts.length > 0 && (
              <div className="sprico-kpi">
                <div className="sprico-kpi-label">Artifact References</div>
                <JsonView value={selectedScan.artifacts} />
              </div>
            )}
            {scanError && (
              <div className="sprico-kpi">
                <div className="sprico-kpi-label">Last Scanner Validation Payload</div>
                <JsonView value={scannerErrorDiagnostics(scanError)} />
              </div>
            )}
          </div>
        )}
      </section>

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Scanner History</div>
          <FieldHelp>Scanner History records scanner jobs. Evidence Center stores the proof produced by completed scans. Findings stores actionable issues.</FieldHelp>
          <div className="sprico-list">
            {history.length === 0 && <EmptyMessage>No scanner runs recorded.</EmptyMessage>}
            {history.map(scan => (
              <button key={scan.scan_id} className="sprico-row" type="button" onClick={() => {
                setSelectedScan(scan)
                setShowSelectedRaw(false)
              }}>
                <span className="sprico-row-main">
                  <span className="sprico-row-title">{valueText(scan.target_name ?? scan.target_id ?? scan.scan_id)}</span>
                  <span className="sprico-row-subtitle">
                    {scan.scan_id} | {historyStatusLabel(scan)} | {valueText(scan.scan_profile ?? scanConfig(scan).scan_profile, 'profile not recorded')} | categories {scanCategories(scan).length} | evidence {evidenceCount(scan)} | findings {findingsCount(scan)} | {displayVerdict(scan)} | {effectiveRisk(scan)} | {formatDateTime(scan.finished_at ?? scan.started_at, 'time not recorded')}
                  </span>
                </span>
                <Badge value={historyStatusLabel(scan)} />
              </button>
            ))}
          </div>
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Selected Scan Result</div>
          {!selectedScan && <EmptyMessage>Select or run a scan.</EmptyMessage>}
          {selectedScan && (
            <div className="sprico-form">
              <ScanReport
                scan={selectedScan}
                currentConfigTarget={currentConfigTarget}
                selectedResultTarget={selectedResultTarget}
                selectedResultDiffers={selectedResultDiffers}
                fallbackTargetDomain={selectedTargetDomain}
                fallbackPolicyDomain={policyDomain}
                fallbackPolicyLabel={selectedPolicy ? `${selectedPolicy.name} (${selectedPolicy.mode})` : policyId}
                showRaw={showSelectedRaw}
                onToggleRaw={() => setShowSelectedRaw(value => !value)}
                onOpenFindings={onNavigate ? () => onNavigate('findings') : undefined}
              />
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

export function ScanReport({
  scan,
  currentConfigTarget,
  selectedResultTarget,
  selectedResultDiffers,
  fallbackTargetDomain,
  fallbackPolicyDomain,
  fallbackPolicyLabel,
  showRaw,
  onToggleRaw,
  onOpenFindings,
}: {
  scan: GarakScanResult | GarakScanReport
  currentConfigTarget: string
  selectedResultTarget: string
  selectedResultDiffers: boolean
  fallbackTargetDomain: string
  fallbackPolicyDomain: string
  fallbackPolicyLabel: string
  showRaw: boolean
  onToggleRaw: () => void
  onOpenFindings?: () => void
}) {
  const scannerEvidence = scan.scanner_evidence ?? scan.raw_findings ?? []
  const signals = scan.signals ?? []
  const profileResolution = scanProfileResolution(scan)
  const categories = scanCategories(scan)
  const probes = resolutionList(profileResolution, 'probes')
  const skippedProbes = skippedResolutionList(profileResolution, 'probes')
  const skippedProbeDetails = skippedResolutionDetails(scan, profileResolution, 'probes')
  const detectors = resolutionList(profileResolution, 'detectors')
  const buffs = resolutionList(profileResolution, 'buffs')
  const categoryLimited = valueText(scan.scan_profile ?? scanConfig(scan).scan_profile).toLowerCase() === 'deep_llm_security'
    && categories.length > 0
    && categories.length < VULNERABILITY_CATEGORIES.length
  const targetDomain = valueText(policyContext(scan).selected_target_domain ?? policyContext(scan).target_domain, selectedResultDiffers ? 'not recorded' : fallbackTargetDomain)
  const policyDomain = valueText(policyContext(scan).policy_domain, fallbackPolicyDomain)
  const policyLabel = valueText(scan.policy_id, fallbackPolicyLabel)

  return (
    <div className="sprico-form">
      {resultBanner(scan)}
      {selectedResultDiffers && (
        <div className="sprico-message">
          You are viewing a previous scan result for {selectedResultTarget}. Current configuration target is {currentConfigTarget}.
        </div>
      )}

      <section className="sprico-kpi">
        <div className="sprico-panel-title">Scan Summary</div>
        <div className="sprico-kpis">
          <Metric label="Status" value={historyStatusLabel(scan)} />
          <Metric label="Final SpriCO Verdict" value={displayVerdict(scan)} />
          <Metric label="Violation Risk" value={effectiveRisk(scan)} />
          <Metric label="Evidence Produced" value={String(evidenceCount(scan))} />
          <Metric label="Findings Created" value={String(findingsCount(scan))} />
          <Metric label="Target Tested" value={valueText(scan.target_name ?? scan.target_id)} />
          <Metric label="Policy Applied" value={policyLabel} />
          <Metric label="Scan Profile" value={scanProfileLabel(scan)} />
          <Metric label="Started / Finished" value={`${formatDateTime(scan.started_at, 'unknown')} / ${formatDateTime(scan.finished_at, 'unknown')}`} />
          <Metric label="Duration" value={scanDuration(scan)} />
          {scan.failure_reason && <Metric label="Failure Reason" value={scan.failure_reason} />}
        </div>
        {effectiveVerdict(scan) === 'PASS' && !isNonEvaluatedScan(scan) && (
          <div className="sprico-message">PASS for selected scan scope. No actionable findings were created for the selected profile and categories.</div>
        )}
      </section>

      <section className="sprico-kpi">
        <div className="sprico-panel-title">Scope Tested</div>
        <div className="sprico-kpis">
          <Metric label="Selected Target" value={valueText(scan.target_name ?? scan.target_id)} />
          <Metric label="Target Type" value={valueText(scan.target_type)} />
          <Metric label="Target Domain" value={targetDomain} />
          <Metric label="Selected Policy" value={policyLabel} />
          <Metric label="Policy Domain" value={policyDomain} />
          <Metric label="Selected Scan Profile" value={scanProfileLabel(scan)} />
          <Metric label="Selected Categories" value={`${categories.length} selected`} />
        </div>
        {categories.length > 0 && (
          <div className="sprico-list">
            {categories.map(category => (
              <div key={category} className="sprico-row">
                <span className="sprico-row-main">
                  <span className="sprico-row-title">{category}</span>
                </span>
              </div>
            ))}
          </div>
        )}
        {categoryLimited && (
          <div className="sprico-message sprico-message-error">
            Category-limited scan: Deep LLM Security profile was selected, but only {categories.length} {categories.length === 1 ? 'category was' : 'categories were'} enabled.
          </div>
        )}
      </section>

      <section className="sprico-kpi">
        <div className="sprico-panel-title">Probe Coverage</div>
        <div className="sprico-kpis">
          <Metric label="Resolved Probes" value={String(reportNumber(scan, 'resolved_probes_count', probes.length))} />
          <Metric label="Skipped Probes" value={String(reportNumber(scan, 'skipped_probes_count', skippedProbes.length))} />
          <Metric label="Detectors" value={String(reportNumber(scan, 'detectors_count', detectors.length))} />
          <Metric label="Buffs" value={String(reportNumber(scan, 'buffs_count', buffs.length))} />
          <Metric label="Default Generations" value={valueText((scan as GarakScanReport).default_generations ?? profileResolution.default_generations ?? scanConfig(scan).max_attempts ?? scanConfig(scan).generations, 'not recorded')} />
          <Metric label="Timeout Seconds" value={valueText((scan as GarakScanReport).timeout_seconds ?? profileResolution.timeout_seconds ?? profileResolution.default_timeout_seconds ?? scanConfig(scan).timeout_seconds, 'not recorded')} />
        </div>
        <FieldHelp>Resolved Probes: garak probe modules successfully selected for this run.</FieldHelp>
        <CoverageList title="Resolved probes list" items={probes} empty="No resolved probes were recorded." />
        <FieldHelp>Skipped Probes: probes requested by profile but skipped due to availability, compatibility, or allowlist rules.</FieldHelp>
        <SkippedCoverageList items={skippedProbeDetails} />
        <FieldHelp>Detectors: explicit detector plugins configured for this run. If zero, probe/default detector behavior may still apply only if garak reports it.</FieldHelp>
        {detectors.length === 0 && (
          <div className="sprico-message">No explicit detectors were configured or captured for this run. Review garak output/artifacts for default probe behavior.</div>
        )}
        <CoverageList title="Detectors list" items={detectors} empty="No detectors were recorded." />
        <FieldHelp>Buffs: prompt transformations/mutations applied before sending probes.</FieldHelp>
        <CoverageList title="Buffs list" items={buffs} empty="No buffs were recorded." />
        <FieldHelp>Default Generations: number of target responses requested per probe prompt.</FieldHelp>
        <FieldHelp>Timeout Seconds: maximum runtime allowed for this scanner run.</FieldHelp>
      </section>

      <section className="sprico-kpi">
        <div className="sprico-panel-title">Evidence & Findings</div>
        <div className="sprico-kpis">
          <Metric label="Scanner Evidence Count" value={String(scannerEvidence.length)} />
          <Metric label="SpriCO Signal Count" value={String(signals.length)} />
          <Metric label="Findings Count" value={String(findingsCount(scan))} />
        </div>
        {!isNonEvaluatedScan(scan) && evidenceCount(scan) === 0 && (
          <div className="sprico-message">No actionable scanner evidence was produced. No Evidence Center records were created for this scan.</div>
        )}
        {!isNonEvaluatedScan(scan) && findingsCount(scan) === 0 && (
          <div className="sprico-message">No Findings were created because SpriCO did not identify an actionable issue in this scan.</div>
        )}
        {!isNonEvaluatedScan(scan) && findingsCount(scan) === 0 && (
          <div className="sprico-message">Findings are only created for actionable issues such as FAIL, HIGH/CRITICAL risk, or high-sensitivity NEEDS_REVIEW. This scan produced no actionable issue.</div>
        )}
        {isNonEvaluatedScan(scan) && evidenceCount(scan) === 0 && (
          <div className="sprico-message">No evidence produced because the scanner did not complete.</div>
        )}
        {findingsCount(scan) > 0 && onOpenFindings && (
          <Button
            appearance="secondary"
            onClick={() => {
              if (typeof window !== 'undefined') {
                window.sessionStorage.setItem('spricoFindingsRunId', scan.run_id ?? `garak_scan:${scan.scan_id}`)
              }
              onOpenFindings()
            }}
          >
            Open Findings for this scan
          </Button>
        )}
        {scannerEvidence.length === 0 ? (
          <EmptyMessage>No scanner evidence rows for this scan.</EmptyMessage>
        ) : (
          <div className="sprico-table-wrap">
            <table className="sprico-table">
              <thead>
                <tr><th>Probe</th><th>Detector</th><th>Scanner Result</th><th>Final SpriCO Verdict</th><th>Prompt</th><th>Output</th></tr>
              </thead>
              <tbody>
                {scannerEvidence.map((item, index) => (
                  <tr key={`${valueText(item.probe ?? item.probe_id)}-${index}`}>
                    <td>{valueText(item.probe ?? item.probe_id)}</td>
                    <td>{valueText(item.detector ?? item.detector_id)}</td>
                    <td>{scannerHitLabel(item)}</td>
                    <td>{displayVerdict(scan)}</td>
                    <td>{valueText(item.prompt).slice(0, 160)}</td>
                    <td>{valueText(item.output ?? item.response).slice(0, 160)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <ArtifactSummary scan={scan} />

      <Button className="sprico-advanced-toggle" appearance="secondary" onClick={onToggleRaw}>
        {showRaw ? 'Hide Advanced Raw Evidence - for administrators and debugging.' : 'Show Advanced Raw Evidence - for administrators and debugging.'}
      </Button>
      {showRaw && (
        <div className="sprico-advanced-panel" data-testid="advanced-raw-evidence-panel">
          <FieldHelp>Advanced Raw Evidence - for administrators and debugging.</FieldHelp>
          <JsonView value={scan} />
        </div>
      )}
    </div>
  )
}

function CoverageList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="sprico-kpi">
      <div className="sprico-kpi-label">{title}</div>
      {items.length === 0 ? (
        <div className="sprico-row-subtitle">{empty}</div>
      ) : (
        <div className="sprico-list">
          {items.map(item => (
            <div key={item} className="sprico-row">
              <span className="sprico-row-main">
                <span className="sprico-row-title">{item}</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SkippedCoverageList({ items }: { items: Array<{ name: string; reason: string }> }) {
  return (
    <div className="sprico-kpi">
      <div className="sprico-kpi-label">Skipped probes list</div>
      {items.length === 0 ? (
        <div className="sprico-row-subtitle">No skipped probes were recorded.</div>
      ) : (
        <div className="sprico-list">
          {items.map(item => (
            <div key={`${item.name}-${item.reason}`} className="sprico-row">
              <span className="sprico-row-main">
                <span className="sprico-row-title">{item.name}</span>
                <span className="sprico-row-subtitle">{item.reason || 'Reason not recorded.'}</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ArtifactSummary({ scan }: { scan: GarakScanResult }) {
  const rows = (scan as GarakScanReport).artifact_summary ?? buildArtifactSummary(scan)
  return (
    <div className="sprico-kpi">
      <div className="sprico-kpi-label">Artifact Summary</div>
      <div className="sprico-list">
        {rows.map(row => (
          <div key={row.label} className="sprico-row">
            <span className="sprico-row-main">
              <span className="sprico-row-title">{row.label}</span>
              {row.detail && <span className="sprico-row-subtitle">{row.detail}</span>}
            </span>
            <Badge value={row.status} />
          </div>
        ))}
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="sprico-kpi">
      <div className="sprico-kpi-label">{label}</div>
      <div className="sprico-kpi-value">{value}</div>
    </div>
  )
}

function SourceGroup({
  title,
  items,
}: {
  title: string
  items: Array<{ name: string; status: string; description: string }>
}) {
  return (
    <div className="sprico-kpi">
      <div className="sprico-kpi-label">{title}</div>
      <div className="sprico-list">
        {items.map(item => (
          <div key={item.name} className="sprico-row">
            <span className="sprico-row-main">
              <span className="sprico-row-title">{item.name}</span>
              <span className="sprico-row-subtitle">{item.description}</span>
            </span>
            <Badge value={item.status} />
          </div>
        ))}
      </div>
    </div>
  )
}

function JudgeEvidenceSource({
  provider,
  providerConfigured,
  runtimeEnabled,
  enabled,
  mode,
  regulatedDomain,
  onEnabledChange,
  onModeChange,
  onConfigure,
}: {
  provider: { allowed_modes?: string[]; configure_hint?: string } | null
  providerConfigured: boolean
  runtimeEnabled: boolean
  enabled: boolean
  mode: string
  regulatedDomain: boolean
  onEnabledChange: (value: boolean) => void
  onModeChange: (value: string) => void
  onConfigure?: () => void
}) {
  const allowedModes = provider?.allowed_modes?.length ? provider.allowed_modes : ['disabled', 'redacted']
  const status = !providerConfigured ? 'Not configured' : runtimeEnabled ? 'Configured, disabled by default' : 'Configured, backend disabled'
  return (
    <div className="sprico-kpi">
      <div className="sprico-kpi-label">Optional / Disabled</div>
      <div className="sprico-list">
        <div className="sprico-row">
          <span className="sprico-row-main">
            <span className="sprico-row-title">OpenAI Judge Evidence</span>
            <span className="sprico-row-subtitle">
              Optional model-based review for ambiguous cases. Disabled by default. {runtimeEnabled ? 'OpenAI Judge provides evidence only. SpriCO PolicyDecisionEngine remains final verdict authority.' : 'Configure in Settings → Judge Models.'}
            </span>
          </span>
          <Badge value={status} />
        </div>
        {!runtimeEnabled && (
          <div className="sprico-message">
            API keys must be configured on the backend. OpenAI Judge provides evidence only and is never a final verdict authority.
            {onConfigure && (
              <div>
                <Button appearance="secondary" onClick={onConfigure}>Configure Judge Models</Button>
              </div>
            )}
          </div>
        )}
        {runtimeEnabled && (
          <div className="sprico-form">
            <label className="sprico-checkbox-row">
              <input type="checkbox" checked={enabled} onChange={event => onEnabledChange(event.target.checked)} />
              <span>Enable OpenAI Judge for this scan</span>
            </label>
            <label className="sprico-field">
              <span className="sprico-label">Judge Mode</span>
              <select className="sprico-select" value={mode} onChange={event => onModeChange(event.target.value)} disabled={!enabled}>
                <option value="redacted">Redacted evidence only</option>
                {allowedModes.includes('raw') && <option value="raw">Raw evidence</option>}
              </select>
            </label>
            <div className="sprico-message">
              OpenAI Judge provides evidence only. SpriCO PolicyDecisionEngine remains final verdict authority.
            </div>
          </div>
        )}
        {regulatedDomain && (
          <div className="sprico-message sprico-message-error">
            Healthcare/PHI content should not be sent to an external judge unless explicitly approved. Redacted mode is required by default.
          </div>
        )}
      </div>
    </div>
  )
}

function ScannerErrorMessage({
  error,
  fallback,
  onOpenTargetConfig,
}: {
  error: ApiError | null
  fallback: string | null
  onOpenTargetConfig?: () => void
}) {
  if (!error && !fallback) return null
  if (!error?.details?.length) {
    return <div className="sprico-message sprico-message-error">{fallback}</div>
  }
  const targetConfigRelevant = error.details.some(detail => shouldOfferTargetConfig(detail.reason))
  const title = error.detail === 'Request validation failed' ? 'Cannot start scanner run.' : (error.detail || 'Cannot start scanner run.')
  return (
    <div className="sprico-message sprico-message-error">
      <strong>{title}</strong>
      <div className="sprico-list">
        {error.details.map((detail, index) => (
          <div key={`${detail.field ?? 'field'}-${index}`} className="sprico-row">
            <span className="sprico-row-main">
              <span className="sprico-row-title">{detail.field ?? 'scanner request'}</span>
              <span className="sprico-row-subtitle">{detail.reason}</span>
            </span>
          </div>
        ))}
      </div>
      {error.nextSteps && error.nextSteps.length > 0 && (
        <div>
          <strong>Next steps</strong>
          <ul>
            {error.nextSteps.map(step => <li key={step}>{step}</li>)}
          </ul>
        </div>
      )}
      {targetConfigRelevant && onOpenTargetConfig && (
        <Button appearance="secondary" onClick={onOpenTargetConfig}>Open Target Configuration</Button>
      )}
    </div>
  )
}

function ClientValidationMessage({
  message,
  onOpenTargetConfig,
}: {
  message: string
  onOpenTargetConfig?: () => void
}) {
  return (
    <div className="sprico-message sprico-message-error">
      {message}
      {shouldOfferTargetConfig(message) && onOpenTargetConfig && (
        <Button appearance="secondary" onClick={onOpenTargetConfig}>Open Target Configuration</Button>
      )}
    </div>
  )
}

function shouldOfferTargetConfig(reason: string): boolean {
  const text = reason.toLowerCase()
  return text.includes('target') || text.includes('endpoint') || text.includes('generator') || text.includes('scanner compatibility')
}

function scannerErrorDiagnostics(error: ApiError): Record<string, unknown> {
  return {
    status: error.status,
    type: error.type,
    code: error.code,
    detail: error.detail,
    details: error.details ?? [],
    next_steps: error.nextSteps ?? [],
  }
}

function scannerHitLabel(item: Record<string, unknown>): string {
  const scannerResult = item.scanner_result
  if (scannerResult && typeof scannerResult === 'object' && !Array.isArray(scannerResult)) {
    const hit = (scannerResult as Record<string, unknown>).hit
    if (hit === true) return 'Hit'
    if (hit === false) return 'No hit'
  }
  const raw = valueText(item.raw_status ?? item.pass_fail).toLowerCase()
  if (raw.includes('pass') || raw.includes('false')) return 'No hit'
  if (raw.includes('hit') || raw.includes('fail') || raw.includes('true')) return 'Hit'
  return valueText(item.raw_status ?? item.pass_fail, 'Unknown')
}

function evidenceCount(scan: GarakScanResult): number {
  return Number(scan.evidence_count ?? scan.aggregate?.evidence_count ?? scan.scanner_evidence?.length ?? scan.raw_findings?.length ?? 0)
}

function findingsCount(scan: GarakScanResult): number {
  return Number(scan.findings_count ?? scan.aggregate?.findings_count ?? scan.findings?.length ?? 0)
}

function isNonEvaluatedScan(scan: GarakScanResult): boolean {
  return scan.evaluation_status === 'not_evaluated' || NON_EVALUATED_STATUSES.has(valueText(scan.status).toLowerCase())
}

function effectiveVerdict(scan: GarakScanResult): string {
  if (isNonEvaluatedScan(scan)) return 'NOT_EVALUATED'
  return valueText(scan.final_verdict ?? scan.sprico_final_verdict?.verdict ?? scan.aggregate?.final_verdict, 'NOT_EVALUATED')
}

function effectiveRisk(scan: GarakScanResult): string {
  if (isNonEvaluatedScan(scan)) return 'NOT_AVAILABLE'
  return valueText(scan.risk ?? scan.sprico_final_verdict?.violation_risk ?? scan.aggregate?.worst_risk, 'NOT_AVAILABLE')
}

function resultBanner(scan: GarakScanResult) {
  const status = valueText(scan.status).toLowerCase()
  const rawVerdict = valueText(scan.sprico_final_verdict?.verdict ?? scan.aggregate?.final_verdict)
  const rawRisk = valueText(scan.sprico_final_verdict?.violation_risk ?? scan.aggregate?.worst_risk)
  const legacyInconsistent = isNonEvaluatedScan(scan) && (rawVerdict === 'PASS' || rawRisk === 'LOW')
  if (status === 'timeout') {
    return (
      <div className="sprico-message sprico-message-error">
        Scanner timed out before producing usable evidence. This run was not evaluated as safe.
        {legacyInconsistent ? ' Legacy/inconsistent PASS/LOW values are suppressed.' : ''}
      </div>
    )
  }
  if (status === 'failed') {
    return (
      <div className="sprico-message sprico-message-error">
        Scanner failed before producing usable evidence. This run was not evaluated as safe.
        {legacyInconsistent ? ' Legacy/inconsistent PASS/LOW values are suppressed.' : ''}
      </div>
    )
  }
  if (status === 'unavailable' || status === 'incompatible_target' || status === 'parsing_failed' || status === 'validation_failed') {
    return (
      <div className="sprico-message sprico-message-error">
        Scanner did not produce usable evidence. This run was not evaluated as safe.
        {legacyInconsistent ? ' Legacy/inconsistent PASS/LOW values are suppressed.' : ''}
      </div>
    )
  }
  if (status === 'completed_no_findings') {
    return (
      <div className="sprico-message">
        Completed - no findings. PASS for selected scan scope. No actionable scanner evidence was produced. No Findings were created. This does not prove the target is safe against all attacks.
      </div>
    )
  }
  return null
}

function countResolutionList(profileResolution: Record<string, unknown> | null, key: string): number | null {
  if (!profileResolution) return null
  const value = profileResolution[key]
  return Array.isArray(value) ? value.length : 0
}

function countSkippedResolution(profileResolution: Record<string, unknown> | null): number | null {
  if (!profileResolution) return null
  const skipped = profileResolution.skipped
  if (!skipped || typeof skipped !== 'object' || Array.isArray(skipped)) return 0
  return Object.values(skipped as Record<string, unknown>).reduce<number>((total, value) => {
    if (Array.isArray(value)) return total + value.length
    if (value && typeof value === 'object') {
      return total + Object.values(value as Record<string, unknown>).filter(Boolean).length
    }
    return value ? total + 1 : total
  }, 0)
}

function buildArtifactSummary(scan: GarakScanResult): Array<{ label: string; status: string; detail?: string }> {
  const artifacts = scan.artifacts ?? []
  const completed = valueText(scan.status).toLowerCase().startsWith('completed')
  const command = findArtifact(artifacts, ['command_metadata', 'command.json'])
  const config = findArtifact(artifacts, ['scan_config', 'config.json'])
  const stdout = findArtifact(artifacts, ['stdout', 'stdout.txt'])
  const stderr = findArtifact(artifacts, ['stderr', 'stderr.txt'])
  const exitCode = findArtifact(artifacts, ['exit_code', 'exit_code.txt'])
  const report = findArtifact(artifacts, ['report', 'report.jsonl', 'garak_report'])
  const hitlog = findArtifact(artifacts, ['hitlog', 'hitlog.jsonl'])
  const html = findArtifact(artifacts, ['html', '.html', '.htm'])
  return [
    { label: 'command metadata', status: command ? 'saved' : 'missing', detail: artifactDetail(command) },
    { label: 'scan config', status: config ? 'saved' : 'missing', detail: artifactDetail(config) },
    { label: 'stdout', status: stdout ? 'saved' : 'missing', detail: artifactDetail(stdout) },
    { label: 'stderr', status: stderrArtifactStatus(artifacts), detail: artifactDetail(stderr) },
    { label: 'exit code', status: exitCode ? 'saved' : 'missing', detail: artifactDetail(exitCode) },
    { label: 'report.jsonl', status: report ? 'saved' : completed ? 'not produced' : 'missing', detail: artifactDetail(report) },
    { label: 'hitlog.jsonl', status: hitlog ? 'saved' : completed ? 'not produced' : 'missing', detail: artifactDetail(hitlog) },
    { label: 'html report', status: html ? 'saved' : completed ? 'not produced' : 'missing', detail: artifactDetail(html) },
  ]
}

function stderrArtifactStatus(artifacts: Array<Record<string, unknown>>): string {
  const artifact = findArtifact(artifacts, ['stderr', 'stderr.txt'])
  if (!artifact) return 'missing'
  return Number(artifact.size ?? 0) > 0 ? 'saved' : 'empty'
}

function findArtifact(artifacts: Array<Record<string, unknown>>, tokens: string[]): Record<string, unknown> | null {
  return artifacts.find(artifact => {
    const name = valueText(artifact.name).toLowerCase()
    const type = valueText(artifact.artifact_type).toLowerCase()
    return tokens.some(token => {
      const normalized = token.toLowerCase()
      return type === normalized || name === normalized || name.includes(normalized)
    })
  }) ?? null
}

function artifactDetail(artifact: Record<string, unknown> | null): string {
  if (!artifact) return ''
  const parts = [
    valueText(artifact.name),
    valueText(artifact.artifact_type),
    artifact.size == null ? '' : `${Number(artifact.size)} bytes`,
    valueText(artifact.sha256).slice(0, 16),
  ].filter(Boolean)
  return parts.join(' | ')
}

function scanConfig(scan: GarakScanResult): Record<string, unknown> {
  return scan.config ?? {}
}

function policyContext(scan: GarakScanResult): Record<string, unknown> {
  const config = scanConfig(scan)
  const context = config.policy_context
  if (context && typeof context === 'object' && !Array.isArray(context)) {
    return context as Record<string, unknown>
  }
  return {}
}

function scanProfileResolution(scan: GarakScanResult): Record<string, unknown> {
  const topLevel = scan.profile_resolution
  if (topLevel && typeof topLevel === 'object' && !Array.isArray(topLevel)) return topLevel
  const configResolution = scanConfig(scan).profile_resolution
  if (configResolution && typeof configResolution === 'object' && !Array.isArray(configResolution)) {
    return configResolution as Record<string, unknown>
  }
  return {}
}

function scanCategories(scan: GarakScanResult): string[] {
  if (Array.isArray(scan.vulnerability_categories)) return scan.vulnerability_categories.map(String)
  const configCategories = scanConfig(scan).vulnerability_categories
  if (Array.isArray(configCategories)) return configCategories.map(String)
  const resolutionCategories = scanProfileResolution(scan).categories
  if (Array.isArray(resolutionCategories)) return resolutionCategories.map(String)
  const contextCategories = policyContext(scan).vulnerability_categories
  if (Array.isArray(contextCategories)) return contextCategories.map(String)
  return []
}

function resolutionList(profileResolution: Record<string, unknown>, key: string): string[] {
  const value = profileResolution[key]
  return Array.isArray(value) ? value.map(String) : []
}

function skippedResolutionList(profileResolution: Record<string, unknown>, key: string): string[] {
  const skipped = profileResolution.skipped
  if (!skipped || typeof skipped !== 'object' || Array.isArray(skipped)) return []
  const value = (skipped as Record<string, unknown>)[key]
  if (Array.isArray(value)) return value.map(String)
  return Object.values(skipped as Record<string, unknown>).flatMap(item => Array.isArray(item) ? item.map(String) : [])
}

function skippedResolutionDetails(scan: GarakScanResult | GarakScanReport, profileResolution: Record<string, unknown>, key: string): Array<{ name: string; reason: string }> {
  const reportDetails = (scan as GarakScanReport).skipped_probe_details
  if (Array.isArray(reportDetails) && reportDetails.length > 0) {
    return reportDetails.map(item => ({
      name: valueText(item.name),
      reason: valueText(item.reason, 'Reason not recorded.'),
    }))
  }
  return skippedResolutionList(profileResolution, key).map(item => ({
    name: item,
    reason: 'Reason not recorded.',
  }))
}

function reportNumber(scan: GarakScanResult | GarakScanReport, key: keyof GarakScanReport, fallback: number): number {
  const value = (scan as GarakScanReport)[key]
  return typeof value === 'number' ? value : fallback
}

function scanProfileLabel(scan: GarakScanResult): string {
  const profile = valueText(scan.scan_profile ?? scanConfig(scan).scan_profile, 'not recorded')
  const match = SCAN_PROFILES.find(item => item.id === profile)
  return match ? match.label : profile
}

function scanDuration(scan: GarakScanResult): string {
  if (!scan.started_at || !scan.finished_at) return 'not recorded'
  const started = Date.parse(scan.started_at)
  const finished = Date.parse(scan.finished_at)
  if (Number.isNaN(started) || Number.isNaN(finished) || finished < started) return 'not recorded'
  const seconds = Math.round((finished - started) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`
}

function displayVerdict(scan: GarakScanResult): string {
  const verdict = effectiveVerdict(scan)
  if (verdict === 'PASS') return 'PASS for selected scan scope'
  return verdict
}

function historyStatusLabel(scan: GarakScanResult): string {
  const status = valueText(scan.status).toLowerCase()
  if (status === 'completed_no_findings') return 'Completed - no findings'
  if (isNonEvaluatedScan(scan)) return 'Not evaluated'
  return valueText(scan.status, 'unknown')
}

function domainsMismatch(targetDomain: string, policyDomain: string): boolean {
  const target = canonicalDomain(targetDomain)
  const policy = canonicalDomain(policyDomain)
  return Boolean(target && policy && target !== 'general' && policy !== 'general' && target !== policy)
}

function canonicalDomain(value: string): string {
  const text = valueText(value).trim().toLowerCase().replace(/_/g, ' ')
  if (['hospital', 'healthcare', 'health', 'clinical', 'medical'].includes(text)) return 'healthcare'
  if (['hr', 'human resources', 'people'].includes(text)) return 'hr'
  if (['financial', 'finance', 'banking'].includes(text)) return 'financial'
  if (['legal', 'law'].includes(text)) return 'legal'
  if (['enterprise', 'general ai', 'general', 'unknown', ''].includes(text)) return 'general'
  return text
}

function isRegulatedDomain(value: string): boolean {
  return canonicalDomain(value) === 'healthcare'
}

function hasExplicitGarakMapping(target: TargetInstance): boolean {
  const params = target.target_specific_params ?? {}
  return Boolean(valueText(params.garak_generator_type).trim() && valueText(params.garak_generator_name).trim())
}

function scannerCompatibility(target: TargetInstance | null, status: GarakStatus | null): {
  workflowCompatible: string
  garakCompatibility: string
  reason: string
} {
  if (!target) {
    return {
      workflowCompatible: 'No target selected',
      garakCompatibility: status?.available ? 'Not configured' : 'Not installed',
      reason: 'Select a configured target to check scanner compatibility.',
    }
  }
  if (!isWorkflowCompatible(target, 'llm_scanner')) {
    return {
      workflowCompatible: 'No',
      garakCompatibility: 'Incompatible',
      reason: 'Selected target is missing an endpoint and cannot be used for scanner execution.',
    }
  }
  const targetType = target.target_type.toLowerCase()
  if (targetType.includes('geminifilesearchtarget') && !hasExplicitGarakMapping(target)) {
    return {
      workflowCompatible: 'Partial',
      garakCompatibility: 'Not configured',
      reason: 'GeminiFileSearchTarget requires explicit scanner generator mapping before garak can run.',
    }
  }
  if (!status?.available) {
    return {
      workflowCompatible: 'Partial',
      garakCompatibility: 'Not installed',
      reason: 'Optional garak scanner engine is not installed. SpriCO native checks are still available.',
    }
  }
  if (!hasExplicitGarakMapping(target) && !targetType.includes('openai') && !targetType.includes('azure') && !targetType.includes('local') && !targetType.includes('huggingface')) {
    return {
      workflowCompatible: 'Partial',
      garakCompatibility: 'Not configured',
      reason: 'This target is configured for Interactive Audit, but not yet configured for garak scanner execution.',
    }
  }
  return {
    workflowCompatible: 'Yes',
    garakCompatibility: 'Ready',
    reason: 'Target and optional garak scanner engine are ready for LLM Vulnerability Scanner execution.',
  }
}

function garakSourceStatus(status: GarakStatus | null, compatibility: { garakCompatibility: string }): string {
  if (!status?.available) return 'Not installed'
  if (compatibility.garakCompatibility === 'Ready') return 'Available'
  if (compatibility.garakCompatibility === 'Not configured') return 'Installed but target not configured'
  if (compatibility.garakCompatibility === 'Incompatible') return 'Incompatible target'
  return compatibility.garakCompatibility
}

function validateScannerSelection({
  targetId,
  selectedTarget,
  attested,
  domainMismatch,
  crossDomainOverride,
  compatibility,
}: {
  targetId: string
  selectedTarget: TargetInstance | null
  attested: boolean
  domainMismatch: boolean
  crossDomainOverride: boolean
  compatibility: { garakCompatibility: string }
}): string | null {
  if (!targetId.trim()) return 'Select a configured target before running a vulnerability scan.'
  if (!selectedTarget) return 'Selected target was not found in the configured target registry.'
  if (!isWorkflowCompatible(selectedTarget, 'llm_scanner')) {
    return 'Selected target is missing an endpoint and cannot be used for scanner execution.'
  }
  if (compatibility.garakCompatibility === 'Not configured') return 'Selected target is not yet configured for garak scanner execution.'
  if (compatibility.garakCompatibility === 'Incompatible') return 'Selected target is incompatible with scanner execution.'
  if (!attested) return 'You must confirm authorization before running this scan.'
  if (domainMismatch && !crossDomainOverride) return 'Confirm cross-domain evaluation before running this scan.'
  return null
}
