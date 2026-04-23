import { useEffect, useMemo, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { spricoPoliciesApi, spricoRedApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { RedObjective, RedScan, SpriCOPolicy, TargetInstance } from '../../types'
import { Badge, EmptyMessage, ErrorMessage, FieldHelp, JsonView, LoadingMessage, PageHelp, friendlySourceLabel, valueText } from './common'
import UnifiedTargetSelector, { isWorkflowCompatible } from './UnifiedTargetSelector'
import './spricoPlatform.css'

const MOCK_TARGET_ID = 'mock_hospital_target'

const ATTACK_ENGINES = [
  { id: 'sprico_manual', label: 'SpriCO Manual', executable: true },
  { id: 'pyrit', label: 'PyRIT', executable: true },
  { id: 'garak', label: 'garak scanner evidence only', executable: false },
  { id: 'deepteam', label: 'DeepTeam metadata only', executable: false },
  { id: 'promptfoo_import_or_assertions', label: 'promptfoo metadata/import only', executable: false },
]

const EVIDENCE_SOURCES = [
  'sprico_domain_signals',
  'garak_detector',
  'deepteam_metric',
  'promptfoo_assertion',
  'pyrit_scorer',
  'openai_judge',
]

export default function RedPage() {
  const [objectives, setObjectives] = useState<RedObjective[]>([])
  const [policies, setPolicies] = useState<SpriCOPolicy[]>([])
  const [executionMode, setExecutionMode] = useState<'mock' | 'real'>('mock')
  const [targetId, setTargetId] = useState(MOCK_TARGET_ID)
  const [selectedTarget, setSelectedTarget] = useState<TargetInstance | null>(null)
  const [permissionAttestation, setPermissionAttestation] = useState(false)
  const [policyId, setPolicyId] = useState('policy_hospital_strict_v1')
  const [engine, setEngine] = useState('sprico_manual')
  const [maxTurns, setMaxTurns] = useState(5)
  const [maxObjectives, setMaxObjectives] = useState(10)
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [selectedObjectiveIds, setSelectedObjectiveIds] = useState<string[]>([])
  const [scans, setScans] = useState<RedScan[]>([])
  const [selectedScan, setSelectedScan] = useState<RedScan | null>(null)
  const [compareScanId, setCompareScanId] = useState('')
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [objectiveResponse, policyResponse] = await Promise.all([
          spricoRedApi.objectives(),
          spricoPoliciesApi.list(),
        ])
        setObjectives(objectiveResponse)
        setPolicies(policyResponse)
        if (policyResponse.length > 0 && !policyResponse.some(policy => policy.id === policyId)) {
          setPolicyId(policyResponse[0].id)
        }
      } catch (err) {
        setError(toApiError(err).detail)
      } finally {
        setIsLoading(false)
      }
    }
    void load()
  }, [])

  const categories = useMemo(
    () => ['ALL', ...Array.from(new Set(objectives.map(objective => objective.category))).sort()],
    [objectives],
  )

  const filteredObjectives = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return objectives.filter(objective => {
      const categoryMatch = categoryFilter === 'ALL' || objective.category === categoryFilter
      const textMatch = !needle || `${objective.id} ${objective.name} ${objective.description}`.toLowerCase().includes(needle)
      return categoryMatch && textMatch
    })
  }, [categoryFilter, objectives, search])

  const validationMessage = validateRedSelection({
    executionMode,
    targetId,
    selectedTarget,
    permissionAttestation,
    engine,
  })

  const runScan = async () => {
    const validation = validateRedSelection({ executionMode, targetId, selectedTarget, permissionAttestation, engine })
    if (validation) {
      setError(validation)
      return
    }
    setIsRunning(true)
    setError(null)
    try {
      const scan = await spricoRedApi.createScan({
        target_id: executionMode === 'mock' ? MOCK_TARGET_ID : targetId,
        objective_ids: selectedObjectiveIds,
        policy_id: policyId,
        engine,
        max_turns: maxTurns,
        max_objectives: maxObjectives,
        permission_attestation: executionMode === 'real' ? permissionAttestation : false,
        policy_context: {
          execution_mode: executionMode === 'mock' ? 'demo_mock' : 'real_target',
          target_id: executionMode === 'mock' ? MOCK_TARGET_ID : targetId,
          target_name: selectedTarget?.display_name ?? targetId,
          target_type: selectedTarget?.target_type,
        },
      })
      setSelectedScan(scan)
      setScans(prev => [scan, ...prev.filter(item => item.id !== scan.id)])
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsRunning(false)
    }
  }

  const compare = async () => {
    if (!selectedScan || !compareScanId) return
    setError(null)
    try {
      const response = await spricoRedApi.compare(selectedScan.id, compareScanId)
      setComparison(response)
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const toggleObjective = (objectiveId: string) => {
    setSelectedObjectiveIds(prev => prev.includes(objectiveId) ? prev.filter(item => item !== objectiveId) : [...prev, objectiveId])
  }

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading Red Team Campaigns" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Red Team Campaigns</div>
          <div className="sprico-subtitle">External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.</div>
        </div>
      </header>

      <PageHelp>
        Run objective-driven attack campaigns against a demo or real target. Campaign outputs are scored by SpriCO domain policy and stored as evidence and findings.
      </PageHelp>

      <ErrorMessage error={error} />

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Campaign Mode</div>
          <div className="sprico-form">
            <div className="sprico-message">
              Demo mock scans use a deterministic hospital demo target. Real target scans require a configured SpriCO target endpoint and explicit permission attestation.
            </div>
            <div className="sprico-actions">
              <Button
                appearance={executionMode === 'mock' ? 'primary' : 'secondary'}
                onClick={() => {
                  setExecutionMode('mock')
                  setTargetId(MOCK_TARGET_ID)
                  setSelectedTarget(null)
                  setPermissionAttestation(false)
                }}
              >
                Demo mock scan
              </Button>
              <Button
                appearance={executionMode === 'real' ? 'primary' : 'secondary'}
                onClick={() => {
                  setExecutionMode('real')
                  if (targetId === MOCK_TARGET_ID) setTargetId('')
                  setSelectedTarget(null)
                }}
              >
                Real target scan
              </Button>
            </div>
            {executionMode === 'mock' ? (
              <div className="sprico-kpi">
                <div className="sprico-kpi-label">Demo Target</div>
                <div className="sprico-kpi-value">{MOCK_TARGET_ID}</div>
                <FieldHelp>Demo-only deterministic hospital target. It is not a configured production target and is never used when Real target scan is selected.</FieldHelp>
              </div>
            ) : (
              <>
                <UnifiedTargetSelector
                  value={targetId}
                  workflow="red_campaign"
                  onChange={(next, target) => {
                    setTargetId(next)
                    setSelectedTarget(target ?? null)
                  }}
                  help="Real target campaigns use the same configured target registry as Interactive Audit."
                />
                <label className="sprico-checkbox-row">
                  <input
                    type="checkbox"
                    checked={permissionAttestation}
                    onChange={event => setPermissionAttestation(event.target.checked)}
                  />
                  <span>I attest that I have permission to run this campaign against the selected configured target.</span>
                </label>
              </>
            )}
            {validationMessage && <div className="sprico-message sprico-message-error">{validationMessage}</div>}
          </div>
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Campaign Config</div>
          <div className="sprico-form">
            <label className="sprico-field">
              <span className="sprico-label">Policy</span>
              <FieldHelp>Controls the domain pack, strictness, and authorization rules used to score campaign responses.</FieldHelp>
              <select className="sprico-select" value={policyId} onChange={event => setPolicyId(event.target.value)}>
                {policies.map(policy => <option key={policy.id} value={policy.id}>{policy.name} ({policy.mode})</option>)}
                {policies.length === 0 && <option value="policy_hospital_strict_v1">Hospital Strict (default)</option>}
              </select>
            </label>
            <label className="sprico-field">
              <span className="sprico-label">Attack Engine</span>
              <FieldHelp>Attack Engine is the source of attack prompts and campaign execution.</FieldHelp>
              <select className="sprico-select" value={engine} onChange={event => setEngine(event.target.value)}>
                {ATTACK_ENGINES.map(item => (
                  <option key={item.id} value={item.id} disabled={!item.executable}>
                    {item.label}{item.executable ? '' : ' - not executable in Red campaigns'}
                  </option>
                ))}
              </select>
            </label>
            <div className="sprico-field">
              <span className="sprico-label">Evidence Engines</span>
              <FieldHelp>Evidence Engines produce raw or normalized proof. They do not produce the final SpriCO verdict.</FieldHelp>
              <div className="sprico-list">
                {EVIDENCE_SOURCES.map(item => (
                  <label key={item} className="sprico-checkbox-row">
                    <input type="checkbox" checked={item === 'sprico_domain_signals'} disabled readOnly />
                    <span>{friendlySourceLabel(item)}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="sprico-message">
              garak, DeepTeam, promptfoo, PyRIT scorers, and optional judge models are evidence sources only. Final Verdict Authority is locked to SpriCO PolicyDecisionEngine.
            </div>
            <div className="sprico-grid">
              <div className="sprico-kpi">
                <div className="sprico-kpi-label">Domain Policy Pack</div>
                <div className="sprico-kpi-value">{policies.find(policy => policy.id === policyId)?.target_domain ?? 'hospital'}</div>
              </div>
              <div className="sprico-kpi">
                <div className="sprico-kpi-label">Final Verdict Authority</div>
                <div className="sprico-kpi-value">SpriCO PolicyDecisionEngine</div>
              </div>
            </div>
            <div className="sprico-grid">
              <label className="sprico-field">
                <span className="sprico-label">Max Turns</span>
                <input className="sprico-input" type="number" min="1" value={maxTurns} onChange={event => setMaxTurns(Number(event.target.value))} />
              </label>
              <label className="sprico-field">
                <span className="sprico-label">Max Objectives</span>
                <input className="sprico-input" type="number" min="1" value={maxObjectives} onChange={event => setMaxObjectives(Number(event.target.value))} />
              </label>
            </div>
            <Button
              appearance="primary"
              disabled={isRunning || Boolean(validationMessage)}
              onClick={() => void runScan()}
            >
              {isRunning ? 'Running' : 'Run Campaign'}
            </Button>
          </div>
        </section>
      </div>

      <section className="sprico-panel">
        <div className="sprico-panel-title">Objective Library</div>
        <div className="sprico-actions">
          <select className="sprico-select" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}>
            {categories.map(category => <option key={category} value={category}>{category}</option>)}
          </select>
          <input className="sprico-input" value={search} onChange={event => setSearch(event.target.value)} placeholder="Filter objectives" />
        </div>
        <div className="sprico-list">
          {filteredObjectives.slice(0, 80).map(objective => (
            <label key={objective.id} className="sprico-row">
              <span className="sprico-row-main">
                <span className="sprico-row-title">{objective.name}</span>
                <span className="sprico-row-subtitle">{objective.category} - {objective.description}</span>
              </span>
              <input type="checkbox" checked={selectedObjectiveIds.includes(objective.id)} onChange={() => toggleObjective(objective.id)} />
            </label>
          ))}
        </div>
      </section>

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Scan Results</div>
          {!selectedScan && <EmptyMessage>No Red scan selected.</EmptyMessage>}
          {selectedScan && (
            <div className="sprico-form">
              <div className="sprico-kpis">
                <Metric label="Status" value={selectedScan.status} />
                <Metric label="Worst Risk" value={valueText(selectedScan.risk.worst_risk)} />
                <Metric label="Findings" value={String(selectedScan.findings?.length ?? 0)} />
                <Metric label="Turns" value={String(selectedScan.results.length)} />
              </div>
              <div className="sprico-table-wrap">
                <table className="sprico-table">
                  <thead><tr><th>Objective</th><th>Final SpriCO Verdict</th><th>Risk</th><th>Sensitivity</th><th>Response</th></tr></thead>
                  <tbody>
                    {selectedScan.results.map((result, index) => (
                      <tr key={`${valueText(result.turn_id)}-${index}`}>
                        <td>{valueText(result.objective_id)}</td>
                        <td><Badge value={result.verdict} /></td>
                        <td><Badge value={result.violation_risk} /></td>
                        <td><Badge value={result.data_sensitivity} /></td>
                        <td>{valueText(result.response).slice(0, 220)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <JsonView value={selectedScan} />
            </div>
          )}
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Compare Scans</div>
          <div className="sprico-list">
            {scans.map(scan => (
              <button key={scan.id} className="sprico-row" type="button" onClick={() => setSelectedScan(scan)}>
                <span className="sprico-row-main">
                  <span className="sprico-row-title">{scan.id}</span>
                  <span className="sprico-row-subtitle">{scan.status} - {valueText(scan.risk.worst_risk)}</span>
                </span>
                <Badge value={scan.risk.worst_risk} />
              </button>
            ))}
          </div>
          <div className="sprico-actions">
            <input className="sprico-input" value={compareScanId} onChange={event => setCompareScanId(event.target.value)} placeholder="Other scan id" />
            <Button appearance="secondary" disabled={!selectedScan || !compareScanId} onClick={() => void compare()}>Compare</Button>
          </div>
          {comparison && <JsonView value={comparison} />}
        </section>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="sprico-kpi">
      <div className="sprico-kpi-label">{label}</div>
      <div className="sprico-kpi-value"><Badge value={value} /></div>
    </div>
  )
}

function validateRedSelection({
  executionMode,
  targetId,
  selectedTarget,
  permissionAttestation,
  engine,
}: {
  executionMode: 'mock' | 'real'
  targetId: string
  selectedTarget: TargetInstance | null
  permissionAttestation: boolean
  engine: string
}): string | null {
  if (engine === 'garak') {
    return 'garak is scanner evidence only. Use LLM Vulnerability Scanner for garak diagnostics.'
  }
  if (engine.includes('deepteam') || engine.includes('promptfoo')) {
    return 'This engine is registered as metadata/evidence only and cannot execute campaigns yet.'
  }
  if (executionMode === 'mock') return null
  if (!targetId.trim()) return 'Select a configured target before running a real target campaign.'
  if (!selectedTarget) return 'Selected target was not found in the configured target registry.'
  if (!isWorkflowCompatible(selectedTarget, 'red_campaign')) {
    return 'Selected target is missing an endpoint and cannot be used for real campaign execution.'
  }
  if (!permissionAttestation) return 'You must confirm authorization before running this scan.'
  return null
}
