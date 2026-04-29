import { useEffect, useMemo, useState } from 'react'
import type { ViewName } from '../Sidebar/Navigation'
import { promptfooApi, spricoRunsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type {
  AuditSpecSuite,
  PromptfooCatalog,
  PromptfooRuntimeLaunchResponse,
  PromptfooStatus,
  SpriCOPolicy,
  SpriCORunRecord,
  TargetInstance,
} from '../../types'
import './auditPlatform.css'

const DOMAIN_OPTIONS = ['generic', 'hospital', 'hr', 'legal', 'finance', 'support']

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

  useEffect(() => {
    const load = async () => {
      try {
        const [statusResponse, catalogResponse, recentRunResponse] = await Promise.all([
          promptfooApi.getStatus(),
          promptfooApi.getCatalog(),
          spricoRunsApi.list({ run_type: 'promptfoo_runtime', limit: 12 }).catch(() => []),
        ])
        setStatus(statusResponse)
        setCatalog(catalogResponse)
        setRecentRuns(recentRunResponse)
        if (!pluginGroupId && catalogResponse.plugin_groups[0]) {
          const group = catalogResponse.plugin_groups[0]
          setPluginGroupId(group.id)
          setSelectedPluginIds(defaultPluginIds(group))
        }
        if (!selectedStrategyIds.length) {
          setSelectedStrategyIds(defaultStrategyIds(catalogResponse))
        }
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

  useEffect(() => {
    if (!selectedPluginGroup) return
    const allowed = new Set(selectedPluginGroup.plugins.map(plugin => plugin.id))
    const retained = selectedPluginIds.filter(pluginId => allowed.has(pluginId))
    if (!retained.length) {
      setSelectedPluginIds(defaultPluginIds(selectedPluginGroup))
    } else if (retained.length !== selectedPluginIds.length) {
      setSelectedPluginIds(retained)
    }
  }, [selectedPluginGroup, selectedPluginIds])

  async function refreshRecentRuns() {
    const runs = await spricoRunsApi.list({ run_type: 'promptfoo_runtime', limit: 12 })
    setRecentRuns(runs)
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

  async function handleLaunch() {
    if (!status?.available) {
      setError(status?.install_hint ?? 'promptfoo is not installed in this environment.')
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
    if (!pluginGroupId) {
      setError('Select a promptfoo plugin group.')
      return
    }
    if (!selectedPluginIds.length) {
      setError('Select at least one promptfoo plugin.')
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
      await refreshRecentRuns()
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
            promptfoo is optional. It generates attack/eval evidence through Benchmark Library; SpriCO PolicyDecisionEngine remains the final verdict authority.
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
              <div className="audit-panel-title">Plugins</div>
            </div>
            <div className="audit-panel-body audit-scroll-list audit-scroll-list-compact" style={{ maxHeight: '240px' }}>
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
          <strong>{selectedTargetIds.length}</strong> target(s), <strong>{selectedPolicyIds.length}</strong> policy selection(s), <strong>{selectedPluginIds.length}</strong> plugin(s), <strong>{selectedStrategyIds.length}</strong> strategy selection(s)
        </div>

        <div className="audit-inline-actions">
          <button type="button" className="audit-primary-btn audit-primary-btn-inline" onClick={() => void handleLaunch()} disabled={busy || !status?.available}>
            {busy ? 'Starting promptfoo Runs...' : 'Run promptfoo'}
          </button>
          <button type="button" className="audit-secondary-btn" onClick={() => void refreshRecentRuns()}>
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
                  return (
                    <tr key={run.run_id}>
                      <td>
                        <div className="audit-code-cell">{run.scan_id}</div>
                        <div className="audit-test-objective">{run.comparison_label}</div>
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
                return (
                  <tr key={run.run_id}>
                    <td>
                      <div className="audit-code-cell">{run.run_id}</div>
                      <div className="audit-test-objective">{run.target_name ?? run.target_id ?? 'Unknown target'}</div>
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
