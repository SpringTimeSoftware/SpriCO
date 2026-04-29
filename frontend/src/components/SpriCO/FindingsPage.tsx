import { useEffect, useMemo, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { spricoFindingsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { SpriCOFinding } from '../../types'
import type { ViewName } from '../Sidebar/Navigation'
import { Badge, EmptyMessage, ErrorMessage, FieldHelp, LoadingMessage, PageHelp, formatDateTime, redactedJson, valueText } from './common'
import './spricoPlatform.css'

interface FindingsPageProps {
  initialRunId?: string | null
  backLink?: { label: string; onClick: () => void }
  onNavigate?: (view: ViewName) => void
}

const FINDINGS_SESSION_RUN_KEY = 'spricoFindingsRunId'

export default function FindingsPage({ initialRunId = null, backLink, onNavigate }: FindingsPageProps = {}) {
  const [allItems, setAllItems] = useState<SpriCOFinding[]>([])
  const [selected, setSelected] = useState<SpriCOFinding | null>(null)
  const [runId, setRunId] = useState(() => initialRunId ?? readSessionValue(FINDINGS_SESSION_RUN_KEY))
  const [targetId, setTargetId] = useState('')
  const [sourcePage, setSourcePage] = useState('')
  const [engine, setEngine] = useState('')
  const [policyId, setPolicyId] = useState('')
  const [domain, setDomain] = useState('')
  const [severity, setSeverity] = useState('')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!initialRunId) return
    setRunId(initialRunId)
  }, [initialRunId])

  const load = async () => {
    setError(null)
    try {
      const response = await spricoFindingsApi.list({
        limit: 250,
        run_id: runId || undefined,
        target_id: targetId || undefined,
        source_page: sourcePage || undefined,
        engine: engine || undefined,
        policy_id: policyId || undefined,
        domain: domain || undefined,
        severity: severity || undefined,
        status: status || undefined,
        search: search || undefined,
      })
      setAllItems(response)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    setSelected(prev => {
      if (prev && allItems.some(item => item.finding_id === prev.finding_id)) return prev
      return allItems[0] ?? null
    })
  }, [allItems])

  const sourcePages = useMemo(() => uniqueValues(allItems.map(item => item.source_page)), [allItems])
  const engines = useMemo(() => uniqueValues(allItems.map(item => item.engine_name ?? item.engine_id ?? '')), [allItems])
  const policies = useMemo(() => uniqueValues(allItems.map(item => item.policy_id ?? '')), [allItems])
  const domains = useMemo(() => uniqueValues(allItems.map(item => item.domain ?? '')), [allItems])
  const severities = useMemo(() => uniqueValues(allItems.map(item => item.severity)), [allItems])
  const statuses = useMemo(() => uniqueValues(allItems.map(item => item.status)), [allItems])

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading findings" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Findings</div>
          <div className="sprico-subtitle">Actionable issues only. Coverage-only runs such as completed no-finding scanner jobs do not create Findings.</div>
        </div>
        <div className="sprico-actions">
          {backLink && <Button appearance="secondary" onClick={backLink.onClick}>{backLink.label}</Button>}
          <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
        </div>
      </header>

      <PageHelp>
        Findings are the platform-wide triage surface for actionable issues. Evidence Center stores proof, Activity History shows coverage and execution history, and no-finding runs remain visible in reporting without becoming Findings.
      </PageHelp>

      <ErrorMessage error={error} />

      <section className="sprico-panel">
        <div className="sprico-panel-title">Filters</div>
        <div className="sprico-grid">
          <label className="sprico-field">
            <span className="sprico-label">Run</span>
            <FieldHelp>Use a unified run ID or a legacy source ID such as an audit run ID or scanner scan ID.</FieldHelp>
            <input className="sprico-input" value={runId} onChange={event => setRunId(event.target.value)} />
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Target</span>
            <input className="sprico-input" value={targetId} onChange={event => setTargetId(event.target.value)} />
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Source Page</span>
            <select className="sprico-select" value={sourcePage} onChange={event => setSourcePage(event.target.value)}>
              <option value="">All</option>
              {sourcePages.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Engine</span>
            <select className="sprico-select" value={engine} onChange={event => setEngine(event.target.value)}>
              <option value="">All</option>
              {engines.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Policy</span>
            <select className="sprico-select" value={policyId} onChange={event => setPolicyId(event.target.value)}>
              <option value="">All</option>
              {policies.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Domain</span>
            <select className="sprico-select" value={domain} onChange={event => setDomain(event.target.value)}>
              <option value="">All</option>
              {domains.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Severity</span>
            <select className="sprico-select" value={severity} onChange={event => setSeverity(event.target.value)}>
              <option value="">All</option>
              {severities.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Status</span>
            <select className="sprico-select" value={status} onChange={event => setStatus(event.target.value)}>
              <option value="">All</option>
              {statuses.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Search</span>
            <input className="sprico-input" value={search} onChange={event => setSearch(event.target.value)} />
          </label>
        </div>
        <div className="sprico-actions">
          <Button appearance="primary" onClick={() => void load()}>Apply</Button>
        </div>
      </section>

      <section className="sprico-panel">
        <div className="sprico-panel-title">Finding Coverage</div>
        <div className="sprico-kpis">
          <Metric label="Actionable Findings" value={String(allItems.length)} />
          <Metric label="Unique Runs" value={String(uniqueValues(allItems.map(item => item.run_id ?? '')).length)} />
          <Metric label="Unique Targets" value={String(uniqueValues(allItems.map(item => item.target_id ?? '')).length)} />
          <Metric label="Policies" value={String(uniqueValues(allItems.map(item => item.policy_id ?? '')).length)} />
        </div>
      </section>

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Findings</div>
          <div className="sprico-table-wrap">
            <table className="sprico-table">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Title</th>
                  <th>Run</th>
                  <th>Target</th>
                  <th>Source</th>
                  <th>Severity</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {allItems.map(item => (
                  <tr key={item.finding_id} className="is-clickable" onClick={() => setSelected(item)}>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td>{valueText(item.title)}</td>
                    <td>{valueText(item.run_id)}</td>
                    <td>{valueText(item.target_name ?? item.target_id)}</td>
                    <td>{valueText(item.source_page)}</td>
                    <td><Badge value={item.severity} /></td>
                    <td><Badge value={item.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {allItems.length === 0 && <EmptyMessage>No actionable Findings matched the filters.</EmptyMessage>}
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Selected Finding</div>
          {!selected && <EmptyMessage>Select a finding.</EmptyMessage>}
          {selected && (
            <div className="sprico-form">
              <div className="sprico-kpis">
                <Metric label="Run ID" value={valueText(selected.run_id)} />
                <Metric label="Target" value={valueText(selected.target_name ?? selected.target_id)} />
                <Metric label="Source Page" value={valueText(selected.source_page)} />
                <Metric label="Engine" value={valueText(selected.engine_name ?? selected.engine_id)} />
                <Metric label="Policy" value={valueText(selected.policy_name ?? selected.policy_id)} />
                <Metric label="Domain" value={valueText(selected.domain)} />
                <Metric label="Severity" value={valueText(selected.severity)} />
                <Metric label="Status" value={valueText(selected.status)} />
                <Metric label="Review Status" value={valueText(selected.review_status)} />
                <Metric label="Evidence Count" value={String(selected.evidence_ids.length)} />
              </div>
              <div className="sprico-message">
                <strong>{selected.title}</strong><br />
                {valueText(selected.description)}
              </div>
              <div className="sprico-grid">
                <div>
                  <div className="sprico-panel-title">Root Cause</div>
                  <pre className="sprico-pre">{valueText(selected.root_cause)}</pre>
                </div>
                <div>
                  <div className="sprico-panel-title">Remediation</div>
                  <pre className="sprico-pre">{valueText(selected.remediation)}</pre>
                </div>
              </div>
              <div>
                <div className="sprico-panel-title">Prompt / Response Excerpt</div>
                <pre className="sprico-pre">{redactedJson({
                  prompt_excerpt: selected.prompt_excerpt,
                  response_excerpt: selected.response_excerpt,
                })}</pre>
              </div>
              <div>
                <div className="sprico-panel-title">Matched Signals And Policy Context</div>
                <pre className="sprico-pre">{redactedJson({
                  matched_signals: selected.matched_signals,
                  policy_context: selected.policy_context,
                  evidence_ids: selected.evidence_ids,
                })}</pre>
              </div>
              <div className="sprico-actions">
                {onNavigate && selected.evidence_ids.length > 0 && (
                  <Button
                    appearance="secondary"
                    onClick={() => {
                      window.sessionStorage.setItem('spricoEvidenceFindingId', selected.evidence_ids[0])
                      onNavigate('evidence')
                    }}
                  >
                    Open Linked Evidence
                  </Button>
                )}
                {onNavigate && isKnownView(selected.source_page) && (
                  <Button appearance="secondary" onClick={() => onNavigate(selected.source_page as ViewName)}>
                    Open Source Page
                  </Button>
                )}
              </div>
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

function uniqueValues(values: string[]): string[] {
  return Array.from(new Set(values.map(item => item.trim()).filter(Boolean))).sort()
}

function readSessionValue(key: string): string {
  if (typeof window === 'undefined') return ''
  const value = window.sessionStorage.getItem(key) ?? ''
  window.sessionStorage.removeItem(key)
  return value
}

function isKnownView(value: string): value is ViewName {
  return [
    'chat',
    'history',
    'config',
    'audit',
    'dashboard',
    'heatmap-dashboard',
    'stability-dashboard',
    'findings',
    'prompt-variants',
    'target-help',
    'benchmark-library',
    'garak-scanner',
    'scanner-reports',
    'shield',
    'policy',
    'red',
    'evidence',
    'conditions',
    'open-source-components',
    'external-engines',
    'judge-models',
    'diagnostics',
    'activity-history',
    'landing',
  ].includes(value)
}
