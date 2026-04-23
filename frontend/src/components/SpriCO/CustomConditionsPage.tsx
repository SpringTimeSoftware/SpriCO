import { useEffect, useMemo, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { spricoConditionsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { SpriCOCondition } from '../../types'
import { Badge, EmptyMessage, ErrorMessage, FieldHelp, JsonView, LoadingMessage, PageHelp, formatDateTime, parseJsonObject, valueText } from './common'
import './spricoPlatform.css'

const DEFAULT_PARAMETERS = JSON.stringify({ keywords: ['patient'] }, null, 2)

const CONDITION_TYPE_HELP = [
  ['keyword_match', 'Matches configured words or phrases in reviewed text.'],
  ['regex_match', 'Uses bounded regular expressions with timeout and length limits.'],
  ['entity_linkage', 'Detects risky links between identifiers and sensitive attributes.'],
  ['sensitive_signal_match', 'Matches existing domain-pack sensitive signals.'],
  ['policy_context_match', 'Matches policy mode, purpose, scope, or authorization context.'],
  ['threshold_condition', 'Emits a signal when a numeric threshold is crossed.'],
  ['composite_condition', 'Combines other declarative conditions without running code.'],
  ['llm_judge_condition', 'Optional judge-assisted condition, disabled by default.'],
] as const

export default function CustomConditionsPage() {
  const [conditions, setConditions] = useState<SpriCOCondition[]>([])
  const [conditionTypes, setConditionTypes] = useState<string[]>([])
  const [selected, setSelected] = useState<SpriCOCondition | null>(null)
  const [conditionVersions, setConditionVersions] = useState<Array<Record<string, unknown>>>([])
  const [conditionAuditHistory, setConditionAuditHistory] = useState<Array<Record<string, unknown>>>([])
  const [name, setName] = useState('Patient keyword condition')
  const [conditionType, setConditionType] = useState('keyword_match')
  const [parameters, setParameters] = useState(DEFAULT_PARAMETERS)
  const [author, setAuthor] = useState('policy-author')
  const [domain, setDomain] = useState('hospital')
  const [simulationText, setSimulationText] = useState('patient record')
  const [testName, setTestName] = useState('positive')
  const [testText, setTestText] = useState('patient record')
  const [testExpected, setTestExpected] = useState(true)
  const [approver, setApprover] = useState('policy-approver')
  const [rollbackTarget, setRollbackTarget] = useState('')
  const [retireReason, setRetireReason] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isDetailsLoading, setIsDetailsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [serviceUnavailableDetail, setServiceUnavailableDetail] = useState<string | null>(null)
  const [showServiceDetails, setShowServiceDetails] = useState(false)

  const selectedAudit = useMemo(
    () => conditionAuditHistory.length > 0 ? conditionAuditHistory : selected?.audit_history ?? [],
    [conditionAuditHistory, selected],
  )

  const activationRequirements = useMemo(() => {
    if (!selected) return []
    const tests = selected.test_cases ?? []
    return [
      { label: 'positive test', met: tests.some(test => expectedMatch(test)) },
      { label: 'negative test', met: tests.some(test => !expectedMatch(test)) },
      { label: 'simulation', met: Boolean(selected.simulation_result) },
      { label: 'approval', met: Boolean(selected.approver) || ['approve', 'activate', 'monitor'].includes(selected.status) },
      { label: 'frozen version', met: Boolean(selected.version_frozen) },
      { label: 'audit history', met: selectedAudit.length > 0 },
    ]
  }, [selected, selectedAudit])

  const canActivate = selected ? activationRequirements.every(item => item.met) : false

  const load = async () => {
    setError(null)
    setServiceUnavailableDetail(null)
    try {
      const [typesResponse, conditionsResponse] = await Promise.all([
        spricoConditionsApi.types(),
        spricoConditionsApi.list(),
      ])
      setConditionTypes(typesResponse.allowed_condition_types)
      setConditions(conditionsResponse)
      setSelected(conditionsResponse[0] ?? null)
    } catch (err) {
      const apiError = toApiError(err)
      if (apiError.status === 404) {
        setServiceUnavailableDetail(apiError.detail)
        setConditions([])
        setConditionTypes([])
        setSelected(null)
      } else {
        setError(apiError.detail)
      }
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    if (!selected) {
      setConditionVersions([])
      setConditionAuditHistory([])
      setRollbackTarget('')
      return
    }
    setRollbackTarget(selected.rollback_target ?? selected.version)
    void loadConditionDetails(selected.condition_id)
  }, [selected?.condition_id])

  const loadConditionDetails = async (conditionId: string) => {
    setIsDetailsLoading(true)
    setError(null)
    try {
      const [versionsResponse, auditResponse] = await Promise.all([
        spricoConditionsApi.versions(conditionId),
        spricoConditionsApi.auditHistory(conditionId),
      ])
      setConditionVersions(versionsResponse.versions ?? [])
      setConditionAuditHistory(auditResponse.audit_history ?? [])
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsDetailsLoading(false)
    }
  }

  const createCondition = async () => {
    setIsSaving(true)
    setError(null)
    try {
      const condition = await spricoConditionsApi.create({
        name,
        condition_type: conditionType,
        parameters: parseJsonObject(parameters),
        author,
        domain,
        policy_modes: ['REDTEAM_STRICT', 'PUBLIC'],
        data_sensitivity: 'HIGH',
        violation_risk: 'HIGH',
      })
      setConditions(prev => [condition, ...prev])
      setSelected(condition)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsSaving(false)
    }
  }

  const refreshSelected = (condition: SpriCOCondition) => {
    setSelected(condition)
    setConditions(prev => [condition, ...prev.filter(item => item.condition_id !== condition.condition_id)])
    void loadConditionDetails(condition.condition_id)
  }

  const simulate = async () => {
    if (!selected) return
    setError(null)
    try {
      await spricoConditionsApi.simulate(selected.condition_id, {
        text: simulationText,
        policy_context: { policy_mode: 'REDTEAM_STRICT', access_context: 'UNKNOWN' },
        actor: author,
      })
      const refreshed = await spricoConditionsApi.list()
      setConditions(refreshed)
      setSelected(refreshed.find(item => item.condition_id === selected.condition_id) ?? selected)
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const addTest = async () => {
    if (!selected) return
    setError(null)
    try {
      const condition = await spricoConditionsApi.addTest(selected.condition_id, {
        name: testName,
        input_text: testText,
        expected_match: testExpected,
        policy_context: { policy_mode: 'REDTEAM_STRICT' },
        actor: author,
      })
      refreshSelected(condition)
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const approve = async () => {
    if (!selected) return
    setError(null)
    try {
      refreshSelected(await spricoConditionsApi.approve(selected.condition_id, { approver }))
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const activate = async () => {
    if (!selected) return
    setError(null)
    try {
      refreshSelected(await spricoConditionsApi.activate(selected.condition_id, { actor: approver }))
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const retire = async () => {
    if (!selected) return
    setError(null)
    try {
      refreshSelected(await spricoConditionsApi.retire(selected.condition_id, { actor: approver, reason: retireReason || 'Retired from Custom Conditions UI' }))
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const rollback = async () => {
    if (!selected) return
    setError(null)
    try {
      refreshSelected(await spricoConditionsApi.rollback(selected.condition_id, { actor: approver, rollback_target: rollbackTarget }))
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading custom conditions" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Custom Conditions</div>
          <div className="sprico-subtitle">
            Conditions are safe declarative signal rules. They must be simulated, tested, approved, and activated before monitoring.
          </div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <PageHelp>
        Custom Conditions are safe declarative signal rules. They do not execute code and cannot directly set final verdicts. They emit signals that SpriCO PolicyDecisionEngine evaluates.
      </PageHelp>

      <ErrorMessage error={error} />
      {serviceUnavailableDetail && (
        <div className="sprico-message sprico-message-error">
          Custom Conditions service is unavailable. Please restart backend or check route registration.
          <div className="sprico-actions" style={{ marginTop: 10 }}>
            <Button appearance="secondary" onClick={() => setShowServiceDetails(value => !value)}>
              {showServiceDetails ? 'Hide Advanced' : 'Show Advanced'}
            </Button>
          </div>
          {showServiceDetails && <pre className="sprico-pre">{serviceUnavailableDetail}</pre>}
        </div>
      )}

      <section className="sprico-panel">
        <div className="sprico-panel-title">Condition Type Guide</div>
        <ul className="sprico-help-list">
          {CONDITION_TYPE_HELP.map(([type, description]) => (
            <li key={type}><strong>{type}</strong>: {description}</li>
          ))}
        </ul>
        <div className="sprico-message" style={{ marginTop: 12 }}>
          Lifecycle: draft -&gt; simulate -&gt; test -&gt; approve -&gt; activate -&gt; monitor -&gt; retire/rollback
        </div>
      </section>

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Author Draft</div>
          <div className="sprico-form">
            <label className="sprico-field">
              <span className="sprico-label">Name</span>
              <input className="sprico-input" value={name} onChange={event => setName(event.target.value)} />
            </label>
            <label className="sprico-field">
              <span className="sprico-label">Condition Type</span>
              <FieldHelp>Select a safe declarative rule type. Custom code, shell commands, SQL, Python, and JavaScript are not supported.</FieldHelp>
              <select className="sprico-select" value={conditionType} onChange={event => setConditionType(event.target.value)}>
                {conditionTypes.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="sprico-field">
              <span className="sprico-label">Parameters JSON</span>
              <FieldHelp>Declarative parameters for the selected condition type. The condition emits signals only.</FieldHelp>
              <textarea className="sprico-textarea" value={parameters} onChange={event => setParameters(event.target.value)} />
            </label>
            <div className="sprico-grid">
              <label className="sprico-field">
                <span className="sprico-label">Author</span>
                <input className="sprico-input" value={author} onChange={event => setAuthor(event.target.value)} />
              </label>
              <label className="sprico-field">
                <span className="sprico-label">Domain</span>
                <input className="sprico-input" value={domain} onChange={event => setDomain(event.target.value)} />
              </label>
            </div>
            <Button appearance="primary" disabled={isSaving} onClick={() => void createCondition()}>
              {isSaving ? 'Creating' : 'Create Draft'}
            </Button>
          </div>
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Condition Library</div>
          {conditions.length === 0 && !serviceUnavailableDetail && <EmptyMessage>No custom conditions created yet.</EmptyMessage>}
          <div className="sprico-list">
            {conditions.map(condition => (
              <button key={condition.condition_id} className="sprico-row" type="button" onClick={() => setSelected(condition)}>
                <span className="sprico-row-main">
                  <span className="sprico-row-title">{condition.name}</span>
                  <span className="sprico-row-subtitle">{condition.condition_type} - v{condition.version} - {condition.domain}</span>
                </span>
                <Badge value={condition.status} />
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Lifecycle</div>
          {!selected && <EmptyMessage>Select a condition.</EmptyMessage>}
          {selected && (
            <div className="sprico-form">
              <div className="sprico-kpis">
                <Metric label="Status" value={selected.status} />
                <Metric label="Activation" value={selected.activation_state} />
                <Metric label="Frozen" value={selected.version_frozen ? 'true' : 'false'} />
                <Metric label="Authority" value="SpriCO PolicyDecisionEngine" />
              </div>
              <div className="sprico-message">
                draft -&gt; simulate -&gt; test -&gt; approve -&gt; activate -&gt; monitor -&gt; retire/rollback
              </div>
              <div className="sprico-list">
                {activationRequirements.map(requirement => (
                  <div key={requirement.label} className="sprico-row">
                    <span className="sprico-row-main">
                      <span className="sprico-row-title">{requirement.label}</span>
                      <span className="sprico-row-subtitle">
                        {requirement.met ? 'Requirement satisfied' : 'Required before activation'}
                      </span>
                    </span>
                    <Badge value={requirement.met ? 'ready' : 'missing'} />
                  </div>
                ))}
              </div>
              <label className="sprico-field">
                <span className="sprico-label">Simulation Text</span>
                <textarea className="sprico-textarea" value={simulationText} onChange={event => setSimulationText(event.target.value)} />
              </label>
              <Button appearance="secondary" onClick={() => void simulate()}>Run Simulation</Button>

              <div className="sprico-grid">
                <label className="sprico-field">
                  <span className="sprico-label">Test Name</span>
                  <input className="sprico-input" value={testName} onChange={event => setTestName(event.target.value)} />
                </label>
                <label className="sprico-field">
                  <span className="sprico-label">Expected</span>
                  <select className="sprico-select" value={testExpected ? 'true' : 'false'} onChange={event => setTestExpected(event.target.value === 'true')}>
                    <option value="true">positive match</option>
                    <option value="false">negative non-match</option>
                  </select>
                </label>
              </div>
              <label className="sprico-field">
                <span className="sprico-label">Test Text</span>
                <textarea className="sprico-textarea" value={testText} onChange={event => setTestText(event.target.value)} />
              </label>
              <Button appearance="secondary" onClick={() => void addTest()}>Add Test</Button>

              <div className="sprico-grid">
                <label className="sprico-field">
                  <span className="sprico-label">Approver</span>
                  <input className="sprico-input" value={approver} onChange={event => setApprover(event.target.value)} />
                </label>
                <div className="sprico-actions">
                  <Button appearance="secondary" onClick={() => void approve()}>Approve</Button>
                  <Button appearance="primary" disabled={!canActivate} onClick={() => void activate()}>Activate</Button>
                </div>
              </div>
              <div className="sprico-grid">
                <label className="sprico-field">
                  <span className="sprico-label">Retire Reason</span>
                  <input className="sprico-input" value={retireReason} onChange={event => setRetireReason(event.target.value)} />
                </label>
                <label className="sprico-field">
                  <span className="sprico-label">Rollback Target</span>
                  <input className="sprico-input" value={rollbackTarget} onChange={event => setRollbackTarget(event.target.value)} />
                </label>
              </div>
              <div className="sprico-actions">
                <Button appearance="secondary" onClick={() => void retire()}>Retire Condition</Button>
                <Button appearance="secondary" disabled={!rollbackTarget.trim()} onClick={() => void rollback()}>Roll Back Condition</Button>
              </div>
            </div>
          )}
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Version And Audit History</div>
          {!selected && <EmptyMessage>Select a condition.</EmptyMessage>}
          {selected && (
            <div className="sprico-form">
              <div className="sprico-actions">
                <Button appearance="secondary" disabled={isDetailsLoading} onClick={() => void loadConditionDetails(selected.condition_id)}>View Version History</Button>
                <Button appearance="secondary" disabled={isDetailsLoading} onClick={() => void loadConditionDetails(selected.condition_id)}>View Audit History</Button>
              </div>
              <div className="sprico-table-wrap">
                <table className="sprico-table">
                  <thead><tr><th>Test</th><th>Expected</th><th>Passed</th></tr></thead>
                  <tbody>
                    {selected.test_cases.map((test, index) => (
                      <tr key={`${valueText(test.id)}-${index}`}>
                        <td>{valueText(test.name)}</td>
                        <td>{valueText(test.expected_match)}</td>
                        <td><Badge value={valueText(test.passed)} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="sprico-table-wrap">
                <table className="sprico-table">
                  <thead><tr><th>Version</th><th>Status</th><th>Frozen</th><th>Updated</th></tr></thead>
                  <tbody>
                    {conditionVersions.map((version, index) => (
                      <tr key={`${valueText(version.version)}-${index}`}>
                        <td>{valueText(version.version)}</td>
                        <td>{valueText(version.status)}</td>
                        <td>{valueText(version.version_frozen)}</td>
                        <td>{formatDateTime(version.updated_at ?? version.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {conditionVersions.length === 0 && <EmptyMessage>No version history returned.</EmptyMessage>}
              <div className="sprico-table-wrap">
                <table className="sprico-table">
                  <thead><tr><th>Action</th><th>Actor</th><th>Time</th></tr></thead>
                  <tbody>
                    {selectedAudit.map((event, index) => (
                      <tr key={`${valueText(event.action)}-${index}`}>
                        <td>{valueText(event.action)}</td>
                        <td>{valueText(event.actor)}</td>
                        <td>{formatDateTime(event.timestamp ?? event.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selectedAudit.length === 0 && <EmptyMessage>No audit history returned.</EmptyMessage>}
              <JsonView value={{ simulation_result: selected.simulation_result, versions: conditionVersions, audit_history: selectedAudit }} />
            </div>
          )}
        </section>
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

function expectedMatch(test: Record<string, unknown>): boolean {
  const raw = test.expected_match
  if (typeof raw === 'boolean') return raw
  if (typeof raw === 'string') return raw.toLowerCase() === 'true'
  return Boolean(raw)
}
