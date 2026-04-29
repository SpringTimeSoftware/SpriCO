import { useEffect, useMemo, useState } from 'react'
import type { ViewName } from '../Sidebar/Navigation'
import { promptfooApi, spricoRunsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type {
  AuditSpecSuite,
  PromptfooCatalog,
  PromptfooCustomIntent,
  PromptfooCustomPolicy,
  PromptfooRuntimeLaunchResponse,
  PromptfooStatus,
  SpriCOPolicy,
  SpriCORunRecord,
  TargetInstance,
} from '../../types'
import './auditPlatform.css'

const DOMAIN_OPTIONS = ['generic', 'hospital', 'hr', 'legal', 'finance', 'support']
const PROMPTFOO_SEVERITY_OPTIONS = ['low', 'medium', 'high', 'critical'] as const

interface PromptfooRuntimePanelProps {
  suites: AuditSpecSuite[]
  selectedSuiteId: string
  selectedSuite: AuditSpecSuite | null
  targets: TargetInstance[]
  policies: SpriCOPolicy[]
  onNavigate?: (view: ViewName) => void
}

export default function PromptfooRuntimePanel({
  suites,
  selectedSuiteId,
  selectedSuite,
  targets,
  policies,
  onNavigate,
}: PromptfooRuntimePanelProps) {
  const [status, setStatus] = useState<PromptfooStatus | null>(null)
  const [catalog, setCatalog] = useState<PromptfooCatalog | null>(null)
  const [selectedTargetIds, setSelectedTargetIds] = useState<string[]>([])
  const [selectedPolicyIds, setSelectedPolicyIds] = useState<string[]>([])
  const [domain, setDomain] = useState('generic')
  const [pluginGroupId, setPluginGroupId] = useState('')
  const [selectedPluginIds, setSelectedPluginIds] = useState<string[]>([])
  const [selectedStrategyIds, setSelectedStrategyIds] = useState<string[]>([])
  const [customPolicies, setCustomPolicies] = useState<PromptfooCustomPolicy[]>([])
  const [customIntents, setCustomIntents] = useState<PromptfooCustomIntent[]>([])
  const [suiteOverlayId, setSuiteOverlayId] = useState('')
  const [purpose, setPurpose] = useState('')
  const [numTestsPerPlugin, setNumTestsPerPlugin] = useState(2)
  const [maxConcurrency, setMaxConcurrency] = useState(2)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [launchResponse, setLaunchResponse] = useState<PromptfooRuntimeLaunchResponse | null>(null)
  const [launchRuns, setLaunchRuns] = useState<Record<string, SpriCORunRecord>>({})
  const [recentRuns, setRecentRuns] = useState<SpriCORunRecord[]>([])

  const eligibleTargets = useMemo(
    () => targets.filter(target => target.target_type !== 'TextTarget' && Boolean(target.endpoint) && Boolean(target.model_name)),
    [targets],
  )
  const selectedPluginGroup = useMemo(
    () => catalog?.plugin_groups.find(group => group.id === pluginGroupId) ?? null,
    [catalog, pluginGroupId],
  )
  const credentialStatus = status?.provider_credentials?.openai ?? null
  const selectedTargetObjects = useMemo(
    () => eligibleTargets.filter(target => selectedTargetIds.includes(target.target_registry_name)),
    [eligibleTargets, selectedTargetIds],
  )
  const selectedPolicyObjects = useMemo(
    () => policies.filter(policy => selectedPolicyIds.includes(policy.id)),
    [policies, selectedPolicyIds],
  )
  const availablePluginIds = useMemo(
    () => new Set((selectedPluginGroup?.plugins ?? []).map(plugin => plugin.id)),
    [selectedPluginGroup],
  )
  const missingSelectedPlugins = useMemo(
    () => selectedPluginIds
      .filter(pluginId => !availablePluginIds.has(pluginId))
      .map(pluginId => ({
        id: pluginId,
        label: catalog?.plugins.find(plugin => plugin.id === pluginId)?.label ?? fallbackPromptfooLabel(pluginId),
      })),
    [availablePluginIds, catalog?.plugins, selectedPluginIds],
  )
  const availableStrategyIds = useMemo(
    () => new Set((catalog?.strategies ?? []).map(strategy => strategy.id)),
    [catalog?.strategies],
  )
  const missingSelectedStrategies = useMemo(
    () => selectedStrategyIds
      .filter(strategyId => !availableStrategyIds.has(strategyId))
      .map(strategyId => ({
        id: strategyId,
        label: (catalog?.strategies ?? []).find(strategy => strategy.id === strategyId)?.label ?? fallbackPromptfooLabel(strategyId),
      })),
    [availableStrategyIds, catalog?.strategies, selectedStrategyIds],
  )
  const promptfooCredentialConfigured = Boolean(credentialStatus?.configured)
  const catalogLoaded = Boolean(catalog)
  const hasCustomPromptfooWorkload = customPolicies.length > 0 || customIntents.length > 0
  const selectedPromptfooScopeCount = selectedPluginIds.length + customPolicies.length + customIntents.length
  const customPolicyValidation = useMemo(
    () => customPolicies.map(policy => validateCustomPolicy(policy, domain)),
    [customPolicies, domain],
  )
  const customIntentValidation = useMemo(
    () => customIntents.map(intent => validateCustomIntent(intent, domain)),
    [customIntents, domain],
  )
  const promptfooCustomValidationError = useMemo(() => {
    const policyError = customPolicyValidation.flatMap(result => result.errors)[0]
    if (policyError) return policyError
    const intentError = customIntentValidation.flatMap(result => result.errors)[0]
    return intentError ?? null
  }, [customIntentValidation, customPolicyValidation])
  const promptfooDisabledReason = useMemo(() => {
    if (!status?.available) {
      return 'Disabled because promptfoo is not installed or unavailable.'
    }
    if (!promptfooCredentialConfigured) {
      return 'Disabled because promptfoo provider credential is not configured.'
    }
    if (!catalogLoaded) {
      return 'Disabled because promptfoo catalog is not loaded.'
    }
    if (selectedTargetObjects.length === 0) {
      return 'Disabled because no target is selected.'
    }
    if (selectedPolicyObjects.length === 0) {
      return 'Disabled because no policy is selected.'
    }
    if (selectedPluginIds.length === 0 && !hasCustomPromptfooWorkload) {
      return 'Disabled because no plugin is selected.'
    }
    if (selectedStrategyIds.length === 0) {
      return 'Disabled because no strategy is selected.'
    }
    if (missingSelectedPlugins.length > 0) {
      return 'Disabled because selected promptfoo plugin is not available in the current catalog.'
    }
    if (missingSelectedStrategies.length > 0) {
      return 'Disabled because selected promptfoo strategy is not available in the current catalog.'
    }
    return null
  }, [
    missingSelectedPlugins.length,
    missingSelectedStrategies.length,
    promptfooCredentialConfigured,
    catalogLoaded,
    hasCustomPromptfooWorkload,
    selectedPluginIds.length,
    selectedPolicyObjects.length,
    selectedStrategyIds.length,
    selectedTargetObjects.length,
    status?.available,
  ])

  useEffect(() => {
    const load = async () => {
      try {
        await refreshRuntimeState({ initializeDefaults: true })
      } catch (err) {
        setError(toApiError(err).detail)
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  useEffect(() => {
    if (!selectedTargetIds.length && eligibleTargets.length) {
      const suiteTargets = (selectedSuite?.target_ids ?? []).filter(targetId =>
        eligibleTargets.some(target => target.target_registry_name === targetId),
      )
      const defaults = suiteTargets.length ? suiteTargets : [eligibleTargets[0].target_registry_name]
      setSelectedTargetIds(defaults)
    }
  }, [eligibleTargets, selectedSuite, selectedTargetIds.length])

  useEffect(() => {
    if (!selectedPolicyIds.length) {
      const suitePolicyId = selectedSuite?.policy_id
      if (suitePolicyId && policies.some(policy => policy.id === suitePolicyId)) {
        setSelectedPolicyIds([suitePolicyId])
      } else if (policies[0]) {
        setSelectedPolicyIds([policies[0].id])
      }
    }
  }, [policies, selectedPolicyIds.length, selectedSuite])

  useEffect(() => {
    if (!suiteOverlayId && selectedSuiteId) {
      setSuiteOverlayId(selectedSuiteId)
    }
  }, [selectedSuiteId, suiteOverlayId])

  useEffect(() => {
    if (selectedSuite?.domain && domain === 'generic') {
      setDomain(selectedSuite.domain.toLowerCase())
    }
  }, [domain, selectedSuite])

  async function refreshRuntimeState(options?: { initializeDefaults?: boolean }) {
    const [statusResponse, catalogResponse, recentRunResponse] = await Promise.all([
      promptfooApi.getStatus(),
      promptfooApi.getCatalog(),
      spricoRunsApi.list({ run_type: 'promptfoo_runtime', limit: 12 }).catch(() => []),
    ])
    setStatus(statusResponse)
    setCatalog(catalogResponse)
    setRecentRuns(recentRunResponse)
    if (options?.initializeDefaults && !pluginGroupId && catalogResponse.plugin_groups[0]) {
      const group = catalogResponse.plugin_groups[0]
      setPluginGroupId(group.id)
      if (!selectedPluginIds.length) {
        setSelectedPluginIds(defaultPluginIds(group))
      }
    }
    if (options?.initializeDefaults && !selectedStrategyIds.length) {
      setSelectedStrategyIds(defaultStrategyIds(catalogResponse))
    }
  }

  function toggleTarget(targetRegistryName: string) {
    setSelectedTargetIds(current => (
      current.includes(targetRegistryName)
        ? current.filter(item => item !== targetRegistryName)
        : [...current, targetRegistryName]
    ))
  }

  function togglePolicy(policyId: string) {
    setSelectedPolicyIds(current => (
      current.includes(policyId)
        ? current.filter(item => item !== policyId)
        : [...current, policyId]
    ))
  }

  function togglePlugin(pluginId: string) {
    setSelectedPluginIds(current => (
      current.includes(pluginId)
        ? current.filter(item => item !== pluginId)
        : [...current, pluginId]
    ))
  }

  function toggleStrategy(strategyId: string) {
    setSelectedStrategyIds(current => (
      current.includes(strategyId)
        ? current.filter(item => item !== strategyId)
        : [...current, strategyId]
    ))
  }

  function removeMissingPlugin(pluginId: string) {
    setSelectedPluginIds(current => current.filter(item => item !== pluginId))
  }

  function removeMissingStrategy(strategyId: string) {
    setSelectedStrategyIds(current => current.filter(item => item !== strategyId))
  }

  function addCustomPolicy() {
    setCustomPolicies(current => [
      ...current,
      {
        policy_id: `policy_${cryptoId()}`,
        policy_name: '',
        policy_text: '',
        severity: 'medium',
        num_tests: 2,
        domain,
        tags: [],
      },
    ])
  }

  function updateCustomPolicy(policyId: string, patch: Partial<PromptfooCustomPolicy>) {
    setCustomPolicies(current => current.map(policy => (
      policy.policy_id === policyId ? { ...policy, ...patch } : policy
    )))
  }

  function removeCustomPolicy(policyId: string) {
    setCustomPolicies(current => current.filter(policy => policy.policy_id !== policyId))
  }

  function addCustomIntent() {
    setCustomIntents(current => [
      ...current,
      {
        intent_id: `intent_${cryptoId()}`,
        intent_name: '',
        prompt_text: '',
        prompt_sequence: [],
        category: '',
        severity: 'medium',
        num_tests: 1,
        tags: [],
      },
    ])
  }

  function updateCustomIntent(intentId: string, patch: Partial<PromptfooCustomIntent>) {
    setCustomIntents(current => current.map(intent => (
      intent.intent_id === intentId ? { ...intent, ...patch } : intent
    )))
  }

  function removeCustomIntent(intentId: string) {
    setCustomIntents(current => current.filter(intent => intent.intent_id !== intentId))
  }

  function handleConfigureCredentials() {
    if (onNavigate) {
      onNavigate('diagnostics')
      return
    }
    setStatusMessage('Open About / Diagnostics to review the promptfoo provider credential source configuration. Secret values are never shown or written to promptfoo configs.')
  }

  async function handleLaunch() {
    if (!status?.available) {
      setError(status?.install_hint ?? 'promptfoo is not installed in this environment.')
      return
    }
    if (!promptfooCredentialConfigured) {
      setError('Promptfoo provider credentials are not configured for this backend runtime.')
      return
    }
    if (!catalogLoaded) {
      setError('promptfoo catalog is not loaded yet.')
      return
    }
    if (!selectedTargetIds.length) {
      setError('Select at least one configured target.')
      return
    }
    if (!selectedPolicyIds.length) {
      setError('Select at least one SpriCO policy.')
      return
    }
    if (!pluginGroupId && !hasCustomPromptfooWorkload) {
      setError('Select a promptfoo plugin group.')
      return
    }
    if (!selectedPluginIds.length && !hasCustomPromptfooWorkload) {
      setError('Select at least one promptfoo plugin.')
      return
    }
    if (!selectedStrategyIds.length) {
      setError('Select at least one promptfoo strategy.')
      return
    }
    if (missingSelectedPlugins.length) {
      setError('Selected promptfoo plugin is not available in the current catalog.')
      return
    }
    if (missingSelectedStrategies.length) {
      setError('Selected promptfoo strategy is not available in the current catalog.')
      return
    }
    if (promptfooCustomValidationError) {
      setError(promptfooCustomValidationError)
      return
    }
    setBusy(true)
    setError(null)
    setStatusMessage(null)
    try {
      const response = await promptfooApi.createRuns({
        target_ids: selectedTargetIds,
        policy_ids: selectedPolicyIds,
        domain,
        plugin_group_id: pluginGroupId,
        plugin_ids: selectedPluginIds,
        strategy_ids: selectedStrategyIds,
        custom_policies: customPolicies,
        custom_intents: customIntents,
        suite_id: suiteOverlayId || null,
        purpose: purpose.trim() || null,
        num_tests_per_plugin: Math.max(1, Math.min(10, numTestsPerPlugin)),
        max_concurrency: Math.max(1, Math.min(10, maxConcurrency)),
        use_remote_generation: false,
      })
      setLaunchResponse(response)
      setStatusMessage(
        `Started ${response.runs.length} promptfoo run(s) in ${response.comparison_mode}. Results import into Evidence Center and only actionable SpriCO outcomes create Findings.`,
      )
      const unifiedPairs = await Promise.all(
        response.runs.map(async run => {
          try {
            const unifiedRun = await spricoRunsApi.get(run.run_id)
            return [run.run_id, unifiedRun] as const
          } catch {
            return [run.run_id, null] as const
          }
        }),
      )
      setLaunchRuns(
        Object.fromEntries(unifiedPairs.filter((entry): entry is [string, SpriCORunRecord] => entry[1] !== null)),
      )
      await refreshRuntimeState()
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="audit-panel audit-panel-feature">
      <div className="audit-panel-header">
        <div>
          <div className="audit-panel-title">Optional promptfoo Runtime</div>
          <div className="audit-note">
            Promptfoo Runtime optionally runs promptfoo plugins, strategies, and custom policies. Results are imported as evidence. SpriCO PolicyDecisionEngine remains final verdict authority.
          </div>
        </div>
      </div>
      <div className="audit-panel-body">
        {loading && <div className="audit-message">Loading promptfoo runtime status...</div>}
        {error && <div className="audit-message error">{error}</div>}
        {statusMessage && <div className="audit-message success">{statusMessage}</div>}

        <div className="audit-message compact">
          {status?.available
            ? `promptfoo is available${status.version ? ` (${status.version})` : ''}. Generated configs use configured SpriCO targets only and never store target secrets.`
            : status?.install_hint ?? 'promptfoo is optional and not installed in this environment.'}
        </div>
        <div className="audit-message compact">
          {promptfooCredentialConfigured
            ? `Promptfoo provider credential is configured via ${humanizeCredentialSourceType(credentialStatus?.source_type)}. Secret values are never shown or written to promptfoo configs.`
            : 'Promptfoo provider credential is not configured. Secret values are never shown or written to promptfoo configs.'}
        </div>
        <div className="audit-message compact">
          promptfoo policy plugin can generate tests from policy text. SpriCO Custom Conditions and Policies remain the final evaluation layer.
        </div>
        {!promptfooCredentialConfigured && (
          <div className="audit-inline-actions">
            <button type="button" className="audit-secondary-btn" onClick={handleConfigureCredentials}>
              Configure promptfoo credentials
            </button>
          </div>
        )}
        {catalog && (
          <>
            <div className="audit-message compact">
              Catalog {catalog.promptfoo_version ?? status?.version ?? 'unknown'} | hash <code>{catalog.catalog_hash}</code>
              {catalog.discovered_at ? ` | discovered ${catalog.discovered_at}` : ''}
            </div>
            <details className="audit-code-panel">
              <summary>Catalog details</summary>
              <div className="audit-detail-grid">
                <DetailLine label="promptfoo version" value={catalog.promptfoo_version ?? status?.version ?? 'unknown'} />
                <DetailLine label="catalog hash" value={catalog.catalog_hash} />
                <DetailLine label="discovered at" value={catalog.discovered_at ?? 'unknown'} />
                <DetailLine label="plugin groups" value={String(catalog.plugin_groups.length)} />
                <DetailLine label="plugins" value={String(catalog.plugins.length)} />
                <DetailLine label="strategies" value={String(catalog.strategies.length)} />
              </div>
            </details>
          </>
        )}

        <div className="audit-form-grid">
          <label className="audit-form-field">
            <span>Domain</span>
            <select value={domain} onChange={event => setDomain(event.target.value)}>
              {DOMAIN_OPTIONS.map(option => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <label className="audit-form-field">
            <span>Plugin Group</span>
            <select
              value={pluginGroupId}
              onChange={event => {
                const nextGroup = catalog?.plugin_groups.find(group => group.id === event.target.value) ?? null
                setPluginGroupId(event.target.value)
                if (nextGroup) {
                  setSelectedPluginIds(defaultPluginIds(nextGroup))
                }
              }}
            >
              <option value="">Select plugin group</option>
              {(catalog?.plugin_groups ?? []).map(group => (
                <option key={group.id} value={group.id}>{group.label}</option>
              ))}
            </select>
          </label>
          <label className="audit-form-field">
            <span>AuditSpec Assertion Overlay</span>
            <select value={suiteOverlayId} onChange={event => setSuiteOverlayId(event.target.value)}>
              <option value="">None</option>
              {suites.map(suite => (
                <option key={suite.suite_id} value={suite.suite_id}>{suite.name} ({suite.suite_id})</option>
              ))}
            </select>
          </label>
          <label className="audit-form-field">
            <span>Purpose</span>
            <input
              value={purpose}
              onChange={event => setPurpose(event.target.value)}
              placeholder="Optional purpose override for promptfoo generation"
            />
          </label>
          <label className="audit-form-field">
            <span>Tests / Plugin</span>
            <input
              type="number"
              min={1}
              max={10}
              value={numTestsPerPlugin}
              onChange={event => setNumTestsPerPlugin(Number(event.target.value) || 1)}
            />
          </label>
          <label className="audit-form-field">
            <span>Max Concurrency</span>
            <input
              type="number"
              min={1}
              max={10}
              value={maxConcurrency}
              onChange={event => setMaxConcurrency(Number(event.target.value) || 1)}
            />
          </label>
        </div>

        {selectedPluginGroup && (
          <div className="audit-message compact">
            {selectedPluginGroup.description}
          </div>
        )}

        <div className="audit-structured-grid">
          <div className="audit-panel">
            <div className="audit-panel-header">
              <div className="audit-panel-title">Targets</div>
            </div>
            <div className="audit-panel-body audit-scroll-list audit-scroll-list-compact" style={{ maxHeight: '220px' }}>
              {eligibleTargets.map(target => (
                <label key={target.target_registry_name} className={`audit-target-item ${selectedTargetIds.includes(target.target_registry_name) ? 'active' : ''}`}>
                  <input type="checkbox" checked={selectedTargetIds.includes(target.target_registry_name)} onChange={() => toggleTarget(target.target_registry_name)} />
                  <div className="audit-item-main">
                    <div className="audit-item-title">{target.display_name ?? target.target_registry_name}</div>
                    <div className="audit-item-subtitle">{target.model_name}</div>
                    <div className="audit-small-meta">{target.target_type} | {target.endpoint}</div>
                  </div>
                </label>
              ))}
              {eligibleTargets.length === 0 && <div className="audit-muted">No configured runtime targets are available for promptfoo execution.</div>}
            </div>
          </div>

          <div className="audit-panel">
            <div className="audit-panel-header">
              <div className="audit-panel-title">Policies</div>
            </div>
            <div className="audit-panel-body audit-scroll-list audit-scroll-list-compact" style={{ maxHeight: '220px' }}>
              {policies.map(policy => (
                <label key={policy.id} className={`audit-check-item ${selectedPolicyIds.includes(policy.id) ? 'active' : ''}`}>
                  <input type="checkbox" checked={selectedPolicyIds.includes(policy.id)} onChange={() => togglePolicy(policy.id)} />
                  <div className="audit-item-main">
                    <div className="audit-item-title">{policy.name}</div>
                    <div className="audit-item-subtitle">{policy.id}</div>
                    <div className="audit-small-meta">{policy.mode} | {policy.target_domain ?? 'generic'}</div>
                  </div>
                </label>
              ))}
              {policies.length === 0 && <div className="audit-muted">No policies loaded yet.</div>}
            </div>
          </div>
        </div>

        <div className="audit-structured-grid">
          <div className="audit-panel">
            <div className="audit-panel-header">
              <div>
                <div className="audit-panel-title">Custom Policies</div>
                <div className="audit-note">Add custom promptfoo policy plugins from policy text. These generate evidence only; SpriCO still decides final verdicts.</div>
              </div>
              <button type="button" className="audit-secondary-btn" onClick={addCustomPolicy}>
                Add Custom Policy
              </button>
            </div>
            <div className="audit-panel-body audit-scroll-list audit-scroll-list-compact" style={{ maxHeight: '360px' }}>
              {customPolicies.map((policy, index) => (
                <div key={policy.policy_id} className="audit-code-panel">
                  <div className="audit-inline-actions" style={{ justifyContent: 'space-between' }}>
                    <div className="audit-code-title">Custom Policy {index + 1}</div>
                    <button type="button" className="audit-secondary-btn audit-secondary-btn-small" onClick={() => removeCustomPolicy(policy.policy_id)}>
                      Remove
                    </button>
                  </div>
                  <div className="audit-form-grid">
                    <label className="audit-form-field">
                      <span>Policy Name</span>
                      <input value={policy.policy_name} onChange={event => updateCustomPolicy(policy.policy_id, { policy_name: event.target.value })} />
                    </label>
                    <label className="audit-form-field">
                      <span>Severity</span>
                      <select value={policy.severity} onChange={event => updateCustomPolicy(policy.policy_id, { severity: event.target.value as PromptfooCustomPolicy['severity'] })}>
                        {PROMPTFOO_SEVERITY_OPTIONS.map(option => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>
                    <label className="audit-form-field">
                      <span>Tests</span>
                      <input type="number" min={1} max={10} value={policy.num_tests} onChange={event => updateCustomPolicy(policy.policy_id, { num_tests: clampPromptfooNumber(event.target.value, 1, 10) })} />
                    </label>
                    <label className="audit-form-field">
                      <span>Domain</span>
                      <select value={policy.domain ?? domain} onChange={event => updateCustomPolicy(policy.policy_id, { domain: event.target.value })}>
                        {DOMAIN_OPTIONS.map(option => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>
                    <label className="audit-form-field">
                      <span>Tags</span>
                      <input value={(policy.tags ?? []).join(', ')} onChange={event => updateCustomPolicy(policy.policy_id, { tags: splitCommaList(event.target.value) })} placeholder="privacy, refusal, compliance" />
                    </label>
                  </div>
                  <label className="audit-form-field">
                    <span>Policy Text</span>
                    <textarea value={policy.policy_text} onChange={event => updateCustomPolicy(policy.policy_id, { policy_text: event.target.value })} placeholder="Describe the rule the target must not violate." />
                  </label>
                  {customPolicyValidation[index]?.warnings.map(warning => (
                    <div key={warning} className="audit-message compact">{warning}</div>
                  ))}
                  {customPolicyValidation[index]?.errors.map(validationError => (
                    <div key={validationError} className="audit-message error">{validationError}</div>
                  ))}
                </div>
              ))}
              {customPolicies.length === 0 && <div className="audit-muted">No custom policies added. Built-in plugins can be used alone, or add a custom policy plugin here.</div>}
            </div>
          </div>

          <div className="audit-panel">
            <div className="audit-panel-header">
              <div>
                <div className="audit-panel-title">Custom Intents</div>
                <div className="audit-note">Custom Intent is the starting prompt itself. Multi-step sequences run as authored; promptfoo does not transform them with strategies.</div>
              </div>
              <button type="button" className="audit-secondary-btn" onClick={addCustomIntent}>
                Add Custom Intent
              </button>
            </div>
            <div className="audit-panel-body audit-scroll-list audit-scroll-list-compact" style={{ maxHeight: '360px' }}>
              {customIntents.map((intent, index) => (
                <div key={intent.intent_id} className="audit-code-panel">
                  <div className="audit-inline-actions" style={{ justifyContent: 'space-between' }}>
                    <div className="audit-code-title">Custom Intent {index + 1}</div>
                    <button type="button" className="audit-secondary-btn audit-secondary-btn-small" onClick={() => removeCustomIntent(intent.intent_id)}>
                      Remove
                    </button>
                  </div>
                  <div className="audit-form-grid">
                    <label className="audit-form-field">
                      <span>Intent Name</span>
                      <input value={intent.intent_name} onChange={event => updateCustomIntent(intent.intent_id, { intent_name: event.target.value })} />
                    </label>
                    <label className="audit-form-field">
                      <span>Category</span>
                      <input value={intent.category ?? ''} onChange={event => updateCustomIntent(intent.intent_id, { category: event.target.value })} placeholder="privacy, access, harmful content" />
                    </label>
                    <label className="audit-form-field">
                      <span>Severity</span>
                      <select value={intent.severity} onChange={event => updateCustomIntent(intent.intent_id, { severity: event.target.value as PromptfooCustomIntent['severity'] })}>
                        {PROMPTFOO_SEVERITY_OPTIONS.map(option => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>
                    <label className="audit-form-field">
                      <span>Tests</span>
                      <input type="number" min={1} max={10} value={intent.num_tests} onChange={event => updateCustomIntent(intent.intent_id, { num_tests: clampPromptfooNumber(event.target.value, 1, 10) })} />
                    </label>
                    <label className="audit-form-field">
                      <span>Tags</span>
                      <input value={(intent.tags ?? []).join(', ')} onChange={event => updateCustomIntent(intent.intent_id, { tags: splitCommaList(event.target.value) })} placeholder="historical-abuse, hospital, multi-turn" />
                    </label>
                  </div>
                  <label className="audit-form-field">
                    <span>Single-Turn Prompt</span>
                    <textarea value={intent.prompt_text ?? ''} onChange={event => updateCustomIntent(intent.intent_id, { prompt_text: event.target.value })} placeholder="Enter a single-turn starting prompt." />
                  </label>
                  <label className="audit-form-field">
                    <span>Optional Multi-Step Sequence</span>
                    <textarea value={(intent.prompt_sequence ?? []).join('\n')} onChange={event => updateCustomIntent(intent.intent_id, { prompt_sequence: splitNonEmptyLines(event.target.value) })} placeholder="One step per line. Leave blank for a single-turn custom intent." />
                  </label>
                  {customIntentValidation[index]?.warnings.map(warning => (
                    <div key={warning} className="audit-message compact">{warning}</div>
                  ))}
                  {customIntentValidation[index]?.errors.map(validationError => (
                    <div key={validationError} className="audit-message error">{validationError}</div>
                  ))}
                </div>
              ))}
              {customIntents.length === 0 && <div className="audit-muted">No custom intents added. Use this when you already know the exact prompt or prompt sequence you want to test.</div>}
            </div>
          </div>
        </div>

        <div className="audit-structured-grid">
          <div className="audit-panel">
            <div className="audit-panel-header">
              <div className="audit-panel-title">Plugins</div>
            </div>
            <div className="audit-panel-body audit-scroll-list audit-scroll-list-compact" style={{ maxHeight: '240px' }}>
              {missingSelectedPlugins.map(plugin => (
                <div key={`missing-${plugin.id}`} className="audit-check-item active" aria-disabled="true">
                  <input type="checkbox" checked disabled readOnly aria-label={`${plugin.label} missing from current catalog`} />
                  <div className="audit-item-main">
                    <div className="audit-item-title">{plugin.label}</div>
                    <div className="audit-item-subtitle">{plugin.id}</div>
                    <div className="audit-small-meta">Missing from current catalog</div>
                  </div>
                  <button type="button" className="audit-secondary-btn" onClick={() => removeMissingPlugin(plugin.id)}>
                    Clear
                  </button>
                </div>
              ))}
              {(selectedPluginGroup?.plugins ?? []).map(plugin => (
                <label key={plugin.id} className={`audit-check-item ${selectedPluginIds.includes(plugin.id) ? 'active' : ''}`}>
                  <input type="checkbox" checked={selectedPluginIds.includes(plugin.id)} onChange={() => togglePlugin(plugin.id)} />
                  <div className="audit-item-main">
                    <div className="audit-item-title">{plugin.label}</div>
                    <div className="audit-item-subtitle">{plugin.id}</div>
                  </div>
                </label>
              ))}
              {!selectedPluginGroup && <div className="audit-muted">Select a plugin group to choose promptfoo plugins.</div>}
            </div>
          </div>

          <div className="audit-panel">
            <div className="audit-panel-header">
              <div className="audit-panel-title">Strategies</div>
            </div>
            <div className="audit-panel-body audit-scroll-list audit-scroll-list-compact" style={{ maxHeight: '240px' }}>
              {missingSelectedStrategies.map(strategy => (
                <div key={`missing-${strategy.id}`} className="audit-check-item active" aria-disabled="true">
                  <input type="checkbox" checked disabled readOnly aria-label={`${strategy.label} missing from current catalog`} />
                  <div className="audit-item-main">
                    <div className="audit-item-title">{strategy.label}</div>
                    <div className="audit-item-subtitle">{strategy.id}</div>
                    <div className="audit-small-meta">Missing from current catalog</div>
                  </div>
                  <button type="button" className="audit-secondary-btn" onClick={() => removeMissingStrategy(strategy.id)}>
                    Clear
                  </button>
                </div>
              ))}
              {(catalog?.strategies ?? []).map(strategy => (
                <label key={strategy.id} className={`audit-check-item ${selectedStrategyIds.includes(strategy.id) ? 'active' : ''}`}>
                  <input type="checkbox" checked={selectedStrategyIds.includes(strategy.id)} onChange={() => toggleStrategy(strategy.id)} />
                  <div className="audit-item-main">
                    <div className="audit-item-title">{strategy.label}</div>
                    <div className="audit-item-subtitle">{strategy.description}</div>
                    <div className="audit-small-meta">{strategy.id} | {strategy.cost} cost</div>
                  </div>
                </label>
              ))}
              {!catalog && <div className="audit-muted">Strategy catalog unavailable.</div>}
            </div>
          </div>
        </div>

        <div className="audit-run-summary">
          <strong>{selectedTargetIds.length}</strong> target(s), <strong>{selectedPolicyIds.length}</strong> policy selection(s), <strong>{selectedPromptfooScopeCount}</strong> plugin / custom prompt scope item(s), <strong>{selectedStrategyIds.length}</strong> strategy selection(s)
        </div>
        {(promptfooDisabledReason || promptfooCustomValidationError) && !busy && (
          <div className="audit-message compact">
            {promptfooDisabledReason ?? promptfooCustomValidationError}
          </div>
        )}

        <div className="audit-inline-actions">
          <button
            type="button"
            className="audit-primary-btn audit-primary-btn-inline"
            onClick={() => void handleLaunch()}
            disabled={busy || Boolean(promptfooDisabledReason) || Boolean(promptfooCustomValidationError)}
          >
            {busy ? 'Starting promptfoo Runs...' : 'Run promptfoo'}
          </button>
          <button type="button" className="audit-secondary-btn" onClick={() => void refreshRuntimeState()}>
            Refresh promptfoo Runs
          </button>
          <button type="button" className="audit-secondary-btn" onClick={() => onNavigate?.('evidence')}>
            Evidence Center
          </button>
          <button type="button" className="audit-secondary-btn" onClick={() => onNavigate?.('dashboard')}>
            Dashboard
          </button>
          <button type="button" className="audit-secondary-btn" onClick={() => onNavigate?.('findings')}>
            Findings
          </button>
          <button type="button" className="audit-secondary-btn" onClick={() => onNavigate?.('activity-history')}>
            Activity History
          </button>
        </div>
      </div>

      {launchResponse && (
        <div className="audit-panel-body">
          <div className="audit-message compact">
            Latest promptfoo launch <code>{launchResponse.comparison_group_id}</code> | mode <code>{launchResponse.comparison_mode}</code>
          </div>
          <div className="audit-table-wrap">
            <table className="audit-table audit-table-dense">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Target</th>
                  <th>Policy</th>
                  <th>Status</th>
                  <th>Evidence</th>
                  <th>Findings</th>
                </tr>
              </thead>
              <tbody>
                {launchResponse.runs.map(run => {
                  const unified = launchRuns[run.run_id]
                  const details = promptfooRunDetails(unified)
                  return (
                    <tr key={run.run_id}>
                      <td>
                        <div className="audit-code-cell">{run.scan_id}</div>
                        <div className="audit-test-objective">{run.comparison_label}</div>
                        {details && <div className="audit-small-meta">{details}</div>}
                      </td>
                      <td>{run.target_name}</td>
                      <td>{run.policy_name ?? run.policy_id}</td>
                      <td>{renderBadge(unified?.status ?? run.status, verdictTone(unified?.status ?? run.status))}</td>
                      <td>{String(unified?.evidence_count ?? 0)}</td>
                      <td>{String(unified?.findings_count ?? 0)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="audit-panel-body">
        <div className="audit-panel-title">Recent promptfoo Coverage</div>
        <div className="audit-note">No-finding promptfoo runs remain visible as coverage in unified runs, dashboards, and Activity History without creating Findings.</div>
        <div className="audit-table-wrap">
          <table className="audit-table audit-table-dense">
            <thead>
              <tr>
                <th>Run</th>
                <th>Plugins</th>
                <th>Status</th>
                <th>Verdict</th>
                <th>Evidence</th>
                <th>Findings</th>
              </tr>
            </thead>
            <tbody>
              {recentRuns.map(run => {
                const coverage = run.coverage_summary ?? {}
                const pluginLabel = String(coverage.plugin_group_label ?? coverage.plugin_group_id ?? 'promptfoo')
                const rowCount = Number(coverage.rows_total ?? 0)
                const details = promptfooRunDetails(run)
                return (
                  <tr key={run.run_id}>
                    <td>
                      <div className="audit-code-cell">{run.run_id}</div>
                      <div className="audit-test-objective">{run.target_name ?? run.target_id ?? 'Unknown target'}</div>
                      {details && <div className="audit-small-meta">{details}</div>}
                    </td>
                    <td>{pluginLabel}{rowCount > 0 ? ` | ${rowCount} row(s)` : ''}</td>
                    <td>{renderBadge(run.status ?? 'unknown', verdictTone(run.status))}</td>
                    <td>{renderBadge(run.final_verdict ?? 'NOT_EVALUATED', verdictTone(run.final_verdict))}</td>
                    <td>{String(run.evidence_count)}</td>
                    <td>{String(run.findings_count)}</td>
                  </tr>
                )
              })}
              {recentRuns.length === 0 && <tr><td colSpan={6} className="audit-muted">No promptfoo runs recorded yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

function DetailLine({ label, value }: { label: string; value: string }) {
  return <div className="audit-detail-line"><span>{label}</span><strong>{value}</strong></div>
}

function defaultPluginIds(group: PromptfooCatalog['plugin_groups'][number]) {
  const defaults = group.plugins.filter(plugin => plugin.default_selected).map(plugin => plugin.id)
  if (defaults.length) return defaults
  return group.plugins.slice(0, 2).map(plugin => plugin.id)
}

function defaultStrategyIds(catalog: PromptfooCatalog) {
  const defaults = catalog.strategies.filter(strategy => strategy.default_selected).map(strategy => strategy.id)
  if (defaults.length) return defaults
  return catalog.strategies.filter(strategy => strategy.recommended).map(strategy => strategy.id)
}

function humanizeCredentialSourceType(sourceType?: string | null) {
  switch ((sourceType ?? '').toLowerCase()) {
    case 'environment':
      return 'environment variable'
    case 'secret_ref':
      return 'secret reference'
    case 'target_secret_ref':
      return 'target secret reference'
    default:
      return 'disabled configuration'
  }
}

function fallbackPromptfooLabel(value: string) {
  return value.replace(/[-_:]+/g, ' ').replace(/\s+/g, ' ').trim() || value
}

function validateCustomPolicy(policy: PromptfooCustomPolicy, domain: string) {
  const errors: string[] = []
  const warnings: string[] = []
  if (!policy.policy_name.trim()) {
    errors.push('Custom policy name is required.')
  }
  if (!policy.policy_text.trim()) {
    errors.push('Custom policy text is required.')
  }
  if (containsSecretLikeContent(policy.policy_name) || containsSecretLikeContent(policy.policy_text)) {
    errors.push(`Custom policy '${policy.policy_name || 'Untitled policy'}' must not contain secrets or API keys.`)
  }
  if (!PROMPTFOO_SEVERITY_OPTIONS.includes(policy.severity)) {
    errors.push(`Custom policy '${policy.policy_name || 'Untitled policy'}' must use a valid severity.`)
  }
  if ((policy.num_tests ?? 0) < 1 || (policy.num_tests ?? 0) > 10) {
    errors.push(`Custom policy '${policy.policy_name || 'Untitled policy'}' must keep tests between 1 and 10.`)
  }
  if ((policy.domain ?? domain) === 'hospital' && looksLikeHospitalPhi(policy.policy_text)) {
    warnings.push(`Custom policy '${policy.policy_name || 'Untitled policy'}' contains hospital/PHI-like text. Use synthetic examples only.`)
  }
  return { errors, warnings }
}

function validateCustomIntent(intent: PromptfooCustomIntent, domain: string) {
  const errors: string[] = []
  const warnings: string[] = []
  const promptText = (intent.prompt_text ?? '').trim()
  const promptSequence = (intent.prompt_sequence ?? []).filter(step => step.trim())
  if (!intent.intent_name.trim()) {
    errors.push('Custom intent name is required.')
  }
  if (!promptText && promptSequence.length === 0) {
    errors.push(`Custom intent '${intent.intent_name || 'Untitled intent'}' requires prompt text or a multi-step sequence.`)
  }
  if (containsSecretLikeContent(intent.intent_name) || containsSecretLikeContent(promptText) || promptSequence.some(containsSecretLikeContent)) {
    errors.push(`Custom intent '${intent.intent_name || 'Untitled intent'}' must not contain secrets or API keys.`)
  }
  if (!PROMPTFOO_SEVERITY_OPTIONS.includes(intent.severity)) {
    errors.push(`Custom intent '${intent.intent_name || 'Untitled intent'}' must use a valid severity.`)
  }
  if ((intent.num_tests ?? 0) < 1 || (intent.num_tests ?? 0) > 10) {
    errors.push(`Custom intent '${intent.intent_name || 'Untitled intent'}' must keep tests between 1 and 10.`)
  }
  const combinedText = [promptText, ...promptSequence].join('\n')
  if (domain === 'hospital' && looksLikeHospitalPhi(combinedText)) {
    warnings.push(`Custom intent '${intent.intent_name || 'Untitled intent'}' contains hospital/PHI-like text. Use synthetic examples only.`)
  }
  if (promptSequence.length > 0) {
    warnings.push('Multi-step custom intents run as authored. promptfoo does not apply strategies to multi-step sequences.')
  }
  return { errors, warnings }
}

function containsSecretLikeContent(value: string) {
  return /\b(?:sk-[A-Za-z0-9_-]{8,}|(?:api[_ -]?key|token|secret|password)\s*[:=]\s*[^\s,;]+)/i.test(value)
}

function looksLikeHospitalPhi(value: string) {
  return /\b(?:mrn|medical record|patient|diagnosis|dob|date of birth|insurance id|discharge notes)\b|\b\d{4}-\d{2}-\d{2}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i.test(value)
}

function splitCommaList(value: string) {
  return value.split(',').map(item => item.trim()).filter(Boolean)
}

function splitNonEmptyLines(value: string) {
  return value.split(/\r?\n/).map(item => item.trim()).filter(Boolean)
}

function clampPromptfooNumber(value: string, min: number, max: number) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return min
  return Math.max(min, Math.min(max, parsed))
}

function cryptoId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID().replace(/-/g, '').slice(0, 12)
  }
  return Math.random().toString(16).slice(2, 14)
}

function promptfooRunDetails(run?: SpriCORunRecord | null) {
  if (!run) return null
  const coverage = run.coverage_summary ?? {}
  const metadata = run.metadata ?? {}
  const promptfoo = asRecord(metadata.promptfoo)
  const promptfooCatalog = asRecord(metadata.promptfoo_catalog)
  const selectedPlugins = asArray(promptfooCatalog.plugins).map(item => asRecord(item).label ?? asRecord(item).id).filter(Boolean)
  const selectedStrategies = asArray(promptfooCatalog.strategies).map(item => asRecord(item).label ?? asRecord(item).id).filter(Boolean)
  const version = String(promptfoo.version ?? coverage.promptfoo_version ?? '').trim()
  const catalogHash = String(promptfoo.catalog_hash ?? coverage.catalog_hash ?? '').trim()
  const parts = [
    version ? `v${version}` : '',
    catalogHash ? `catalog ${catalogHash}` : '',
    selectedPlugins.length ? `plugins ${selectedPlugins.join(', ')}` : '',
    selectedStrategies.length ? `strategies ${selectedStrategies.join(', ')}` : '',
  ].filter(Boolean)
  return parts.length ? parts.join(' | ') : null
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function verdictTone(status?: string | null): 'pass' | 'warn' | 'fail' | 'info' | 'critical' {
  const normalized = (status ?? '').toUpperCase()
  if (normalized === 'COMPLETED' || normalized === 'COMPLETED_NO_FINDINGS' || normalized === 'PASS') return 'pass'
  if (normalized === 'FAILED' || normalized === 'FAIL' || normalized === 'ERROR' || normalized === 'UNAVAILABLE') return 'fail'
  if (normalized === 'RUNNING' || normalized === 'PENDING' || normalized === 'WARN' || normalized === 'NEEDS_REVIEW') return 'warn'
  if (normalized === 'CRITICAL') return 'critical'
  return 'info'
}

function renderBadge(label: string, tone: 'pass' | 'warn' | 'fail' | 'info' | 'critical') {
  return <span className={`audit-badge ${tone}`}>{label}</span>
}
