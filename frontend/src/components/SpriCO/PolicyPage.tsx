import { useEffect, useMemo, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { spricoPoliciesApi, spricoProjectsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { ShieldCheckResponse, SpriCOPolicy, SpriCOProject } from '../../types'
import { Badge, ErrorMessage, FieldHelp, JsonView, LoadingMessage, PageHelp, formatDateTime, parseJsonObject, valueText } from './common'
import './spricoPlatform.css'

type PolicyDraft = {
  name: string
  mode: string
  sensitivity: string
  allowedDomains: string
  denyDomains: string
  allowList: string
  denyList: string
}

export default function PolicyPage() {
  const [projects, setProjects] = useState<SpriCOProject[]>([])
  const [policies, setPolicies] = useState<SpriCOPolicy[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [selectedPolicyId, setSelectedPolicyId] = useState('policy_hospital_strict_v1')
  const [policyDraft, setPolicyDraft] = useState<PolicyDraft>(emptyPolicyDraft())
  const [newPolicyName, setNewPolicyName] = useState('')
  const [newProjectName, setNewProjectName] = useState('')
  const [simulationPrompt, setSimulationPrompt] = useState('Patient 8943d3d7-9c12-b8aa-fdd0-40bcb3214d1c has cancer.')
  const [simulationMetadata, setSimulationMetadata] = useState('{\n  "access_context": "UNKNOWN",\n  "authorization_source": "NONE"\n}')
  const [simulation, setSimulation] = useState<ShieldCheckResponse | null>(null)
  const [auditHistory, setAuditHistory] = useState<Array<Record<string, unknown>>>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const selectedPolicy = useMemo(
    () => policies.find(policy => policy.id === selectedPolicyId) ?? policies[0] ?? null,
    [policies, selectedPolicyId],
  )

  const validationErrors = useMemo(() => validatePolicyDraft(policyDraft), [policyDraft])

  const load = async () => {
    setError(null)
    try {
      const [projectResponse, policyResponse] = await Promise.all([
        spricoProjectsApi.list(),
        spricoPoliciesApi.list(),
      ])
      setProjects(projectResponse)
      setPolicies(policyResponse)
      const nextPolicy = policyResponse.find(policy => policy.id === selectedPolicyId) ?? policyResponse[0]
      if (nextPolicy) {
        setSelectedPolicyId(nextPolicy.id)
        setPolicyDraft(policyToDraft(nextPolicy))
        const history = await spricoPoliciesApi.auditHistory(nextPolicy.id)
        setAuditHistory(history.audit_history)
      }
      if (projectResponse[0] && !selectedProjectId) {
        setSelectedProjectId(projectResponse[0].id)
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

  const selectPolicy = async (policyId: string) => {
    setSelectedPolicyId(policyId)
    const policy = policies.find(item => item.id === policyId)
    if (policy) {
      setPolicyDraft(policyToDraft(policy))
      const history = await spricoPoliciesApi.auditHistory(policy.id)
      setAuditHistory(history.audit_history)
    }
  }

  const createPolicy = async () => {
    setError(null)
    try {
      const policy = await spricoPoliciesApi.create({
        name: newPolicyName || 'New SpriCO Policy',
        mode: 'REDTEAM_STRICT',
        sensitivity: 'L3',
        target_domain: 'hospital',
        enabled_guardrails: {
          prompt_defense: true,
          dlp: true,
          content_moderation: true,
          malicious_links: true,
          custom_detectors: true,
        },
      } as Partial<SpriCOPolicy> & { name: string })
      setNewPolicyName('')
      await load()
      await selectPolicy(policy.id)
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const savePolicy = async () => {
    if (validationErrors.length > 0) {
      setError(validationErrors.join('; '))
      return
    }
    setError(null)
    try {
      const patch = {
        mode: policyDraft.mode,
        sensitivity: policyDraft.sensitivity,
        allowed_domains: splitCsv(policyDraft.allowedDomains),
        deny_domains: splitCsv(policyDraft.denyDomains),
        allow_list: JSON.parse(policyDraft.allowList || '[]'),
        deny_list: JSON.parse(policyDraft.denyList || '[]'),
        updated_by: 'sprico-ui',
      }
      const updated = await spricoPoliciesApi.update(selectedPolicyId, patch as Partial<SpriCOPolicy>)
      setPolicies(prev => prev.map(policy => policy.id === updated.id ? updated : policy))
      setPolicyDraft(policyToDraft(updated))
      const history = await spricoPoliciesApi.auditHistory(updated.id)
      setAuditHistory(history.audit_history)
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const createProject = async () => {
    setError(null)
    try {
      const project = await spricoProjectsApi.create({
        name: newProjectName || 'SpriCO Project',
        policy_id: selectedPolicyId,
        environment: 'dev',
      })
      setNewProjectName('')
      setProjects(prev => [project, ...prev])
      setSelectedProjectId(project.id)
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const runSimulation = async () => {
    setError(null)
    try {
      const response = await spricoPoliciesApi.simulate(
        selectedPolicyId,
        [{ role: 'assistant', content: simulationPrompt }],
        parseJsonObject(simulationMetadata),
      )
      setSimulation(response)
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading policies" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Policies</div>
          <div className="sprico-subtitle">Projects, policies, simulation, allow/deny validation, and policy audit history.</div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <PageHelp>
        Policies define how SpriCO interprets evidence: domain, strictness, allowed/denied content, policy mode, and authorization requirements.
      </PageHelp>

      <ErrorMessage error={error} />

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Projects</div>
          <div className="sprico-form">
            <FieldHelp>Project groups policies, targets, scans, evidence, and audit history for a customer or environment.</FieldHelp>
            <select className="sprico-select" value={selectedProjectId} onChange={event => setSelectedProjectId(event.target.value)}>
              <option value="">No project selected</option>
              {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            <div className="sprico-actions">
              <input className="sprico-input" value={newProjectName} onChange={event => setNewProjectName(event.target.value)} placeholder="Project name" />
              <Button appearance="primary" onClick={() => void createProject()}>Create Project</Button>
            </div>
            <JsonView value={projects.find(project => project.id === selectedProjectId) ?? {}} />
          </div>
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Policy List</div>
          <div className="sprico-list">
            {policies.map(policy => (
              <button key={policy.id} className="sprico-row" type="button" onClick={() => void selectPolicy(policy.id)}>
                <span className="sprico-row-main">
                  <span className="sprico-row-title">{policy.name}</span>
                  <span className="sprico-row-subtitle">{policy.id} v{policy.version}</span>
                </span>
                <Badge value={policy.mode} />
              </button>
            ))}
          </div>
          <div className="sprico-actions">
            <input className="sprico-input" value={newPolicyName} onChange={event => setNewPolicyName(event.target.value)} placeholder="Policy name" />
            <Button appearance="primary" onClick={() => void createPolicy()}>Create Policy</Button>
          </div>
        </section>
      </div>

      {selectedPolicy && (
        <div className="sprico-grid-wide">
          <section className="sprico-panel">
            <div className="sprico-panel-title">Edit Policy</div>
            <div className="sprico-form">
              <div className="sprico-kpis">
                <Metric label="Policy" value={selectedPolicy.name} />
                <Metric label="Version" value={selectedPolicy.version} />
                <Metric label="Sensitivity" value={policyDraft.sensitivity} />
              </div>
              <label className="sprico-field">
                <span className="sprico-label">Policy Mode</span>
                <FieldHelp>Controls strictness and authorization assumptions, such as public, red-team strict, or verified clinical/auditor context.</FieldHelp>
                <select className="sprico-select" value={policyDraft.mode} onChange={event => setPolicyDraft(prev => ({ ...prev, mode: event.target.value }))}>
                  {['PUBLIC', 'RESEARCH_DEIDENTIFIED', 'REDTEAM_STRICT', 'CLINICAL_AUTHORIZED', 'AUDITOR_AUTHORIZED', 'INTERNAL_QA', 'UNKNOWN'].map(mode => (
                    <option key={mode} value={mode}>{mode}</option>
                  ))}
                </select>
              </label>
              <label className="sprico-field">
                <span className="sprico-label">Sensitivity</span>
                <FieldHelp>Sets the baseline sensitivity level for data governed by this policy.</FieldHelp>
                <select className="sprico-select" value={policyDraft.sensitivity} onChange={event => setPolicyDraft(prev => ({ ...prev, sensitivity: event.target.value }))}>
                  {['L1', 'L2', 'L3', 'L4'].map(level => <option key={level} value={level}>{level}</option>)}
                </select>
              </label>
              <label className="sprico-field">
                <span className="sprico-label">Allowed Domains</span>
                <FieldHelp>Comma-separated domains or policy packs that this policy is allowed to govern.</FieldHelp>
                <input className="sprico-input" value={policyDraft.allowedDomains} onChange={event => setPolicyDraft(prev => ({ ...prev, allowedDomains: event.target.value }))} />
              </label>
              <label className="sprico-field">
                <span className="sprico-label">Denied Domains</span>
                <FieldHelp>Comma-separated domains that must not be evaluated under this policy.</FieldHelp>
                <input className="sprico-input" value={policyDraft.denyDomains} onChange={event => setPolicyDraft(prev => ({ ...prev, denyDomains: event.target.value }))} />
              </label>
              <label className="sprico-field">
                <span className="sprico-label">Allow List</span>
                <FieldHelp>JSON array of explicitly allowed terms, use cases, or scoped exceptions with reason, expiry, and creator.</FieldHelp>
                <textarea className="sprico-textarea" value={policyDraft.allowList} onChange={event => setPolicyDraft(prev => ({ ...prev, allowList: event.target.value }))} />
              </label>
              <label className="sprico-field">
                <span className="sprico-label">Deny List</span>
                <FieldHelp>JSON array of explicitly denied content or behaviors with reason, expiry, and creator.</FieldHelp>
                <textarea className="sprico-textarea" value={policyDraft.denyList} onChange={event => setPolicyDraft(prev => ({ ...prev, denyList: event.target.value }))} />
              </label>
              {validationErrors.length > 0 && <div className="sprico-message sprico-message-error">{validationErrors.join('; ')}</div>}
              <Button appearance="primary" onClick={() => void savePolicy()}>Save Policy</Button>
            </div>
          </section>

          <section className="sprico-panel">
            <div className="sprico-panel-title">Simulation</div>
            <div className="sprico-form">
              <FieldHelp>Simulation lets you test how a prompt, response, and metadata would be interpreted before relying on the policy in a scan.</FieldHelp>
              <textarea className="sprico-textarea" value={simulationPrompt} onChange={event => setSimulationPrompt(event.target.value)} />
              <textarea className="sprico-textarea" value={simulationMetadata} onChange={event => setSimulationMetadata(event.target.value)} />
              <Button appearance="primary" onClick={() => void runSimulation()}>Simulate</Button>
              {simulation && (
                <>
                  <div className="sprico-kpis">
                    <Metric label="Final SpriCO Verdict" value={simulation.verdict} />
                    <Metric label="Risk" value={simulation.violation_risk} />
                    <Metric label="Sensitivity" value={simulation.data_sensitivity} />
                  </div>
                  <JsonView value={simulation} />
                </>
              )}
            </div>
          </section>
        </div>
      )}

      <section className="sprico-panel">
        <div className="sprico-panel-title">Audit History</div>
        <div className="sprico-table-wrap">
          <table className="sprico-table">
            <thead><tr><th>Timestamp</th><th>Action</th><th>Actor</th><th>Changes</th></tr></thead>
            <tbody>
              {auditHistory.map((entry, index) => (
                <tr key={`${valueText(entry.timestamp)}-${index}`}>
                  <td>{formatDateTime(entry.timestamp)}</td>
                  <td>{valueText(entry.action)}</td>
                  <td>{valueText(entry.actor)}</td>
                  <td>{valueText(entry.changes).slice(0, 260)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
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

function emptyPolicyDraft(): PolicyDraft {
  return { name: '', mode: 'REDTEAM_STRICT', sensitivity: 'L3', allowedDomains: '', denyDomains: '', allowList: '[]', denyList: '[]' }
}

function policyToDraft(policy: SpriCOPolicy): PolicyDraft {
  return {
    name: policy.name,
    mode: policy.mode,
    sensitivity: policy.sensitivity,
    allowedDomains: (policy.allowed_domains ?? []).join(', '),
    denyDomains: (policy.deny_domains ?? []).join(', '),
    allowList: JSON.stringify(policy.allow_list ?? [], null, 2),
    denyList: JSON.stringify(policy.deny_list ?? [], null, 2),
  }
}

function validatePolicyDraft(draft: PolicyDraft): string[] {
  const errors: string[] = []
  for (const key of ['allowList', 'denyList'] as const) {
    try {
      const value = JSON.parse(draft[key] || '[]')
      if (!Array.isArray(value)) {
        errors.push(`${key} must be an array`)
        continue
      }
      value.forEach((item: unknown, index: number) => {
        if (!item || typeof item !== 'object') {
          errors.push(`${key}[${index}] must be an object`)
          return
        }
        const record = item as Record<string, unknown>
        for (const field of ['reason', 'expiry', 'created_by']) {
          if (!record[field]) errors.push(`${key}[${index}] missing ${field}`)
        }
      })
    } catch {
      errors.push(`${key} is not valid JSON`)
    }
  }
  return errors
}

function splitCsv(value: string): string[] {
  return value.split(',').map(item => item.trim()).filter(Boolean)
}
