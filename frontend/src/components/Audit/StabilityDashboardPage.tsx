import { useEffect, useMemo, useState } from 'react'
import { auditApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { StabilityDashboardResponse, StabilityGroupDetailResponse, StabilityGroupRow } from '../../types'
import './auditPlatform.css'

interface StabilityDashboardPageProps {
  onOpenRun?: (runId: string) => void
}

export default function StabilityDashboardPage({ onOpenRun }: StabilityDashboardPageProps) {
  const [dashboard, setDashboard] = useState<StabilityDashboardResponse | null>(null)
  const [detail, setDetail] = useState<StabilityGroupDetailResponse | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)
  const [modeFilter, setModeFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [verdictFilter, setVerdictFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  const [search, setSearch] = useState('')
  const [rerunningGroupId, setRerunningGroupId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setDashboard(await auditApi.getStabilityDashboard())
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }
    void load()
  }, [])

  const categories = useMemo(
    () => Array.from(new Set((dashboard?.groups ?? []).map(item => item.category_name).filter(Boolean))) as string[],
    [dashboard],
  )

  const filteredGroups = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (dashboard?.groups ?? []).filter(group => {
      if (modeFilter && group.mode_code !== modeFilter) return false
      if (categoryFilter && group.category_name !== categoryFilter) return false
      if (verdictFilter && group.aggregate_verdict !== verdictFilter) return false
      if (riskFilter && group.aggregate_risk_level !== riskFilter) return false
      if (!query) return true
      return [
        group.audit_session_id,
        group.prompt_source_ref ?? '',
        group.category_name ?? '',
        group.subcategory_name ?? '',
        group.objective_text ?? '',
        group.model_name ?? group.model_target_name ?? '',
      ].join(' ').toLowerCase().includes(query)
    })
  }, [categoryFilter, dashboard, modeFilter, riskFilter, search, verdictFilter])

  async function openGroup(group: StabilityGroupRow) {
    setSelectedGroupId(group.id)
    try {
      setDetail(await auditApi.getStabilityGroup(group.id))
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  async function rerunGroup(group: StabilityGroupRow) {
    setRerunningGroupId(group.id)
    try {
      const run = await auditApi.rerunStabilityGroup(group.id)
      onOpenRun?.(run.job_id)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setRerunningGroupId(null)
    }
  }

  if (!dashboard && !error) {
    return <div className="audit-platform"><div className="audit-message">Loading stability dashboard from SQLite...</div></div>
  }

  const summary = dashboard?.summary

  return (
    <div className="audit-platform audit-stability-shell">
      <section className="audit-hero audit-hero-compact">
        <div>
          <div className="audit-hero-title">Stability Dashboard</div>
          <div className="audit-hero-subtitle">
            Variability, repeatability, and worst-case behavior from structured audit result groups. Legacy single-run results render as one-run Compliance groups.
          </div>
        </div>
        <div className="audit-hero-meta audit-hero-meta-row">
          <div className="audit-meta-card">
            <div className="audit-meta-label">Scope</div>
            <div className="audit-meta-value">Structured audits only</div>
          </div>
          <div className="audit-meta-card">
            <div className="audit-meta-label">Default Mode</div>
            <div className="audit-meta-value">Compliance</div>
          </div>
        </div>
      </section>

      {error && <div className="audit-message error">{error}</div>}

      {dashboard && (
        <>
          <section className="audit-kpi-grid">
            <SummaryCard label="Total Test Groups" value={(summary?.total_groups ?? 0).toString()} detail="Logical workbook tests" />
            <SummaryCard label="Avg Stability" value={`${summary?.avg_stability_score ?? 0}%`} detail="100 = no divergence" tone="pass" />
            <SummaryCard label="Avg Fail Rate" value={`${summary?.avg_fail_rate ?? 0}%`} detail="FAIL runs / completed" tone="fail" />
            <SummaryCard label="Worst Category" value={summary?.worst_category ?? 'N/A'} detail="Highest fail density" tone="warn" />
            <SummaryCard label="Most Unstable Target" value={summary?.most_unstable_target ?? 'N/A'} detail="Lowest stability score" />
            <SummaryCard label="Worst-Case Fails" value={(summary?.worst_case_fail_count ?? 0).toString()} detail="Groups with FAIL worst case" tone="critical" />
          </section>

          <section className="audit-panel">
            <div className="audit-panel-body audit-stability-filters">
              <FilterSelect label="Mode" value={modeFilter} onChange={setModeFilter} options={dashboard.by_mode.map(item => item.mode_code)} />
              <FilterSelect label="Category" value={categoryFilter} onChange={setCategoryFilter} options={categories} />
              <FilterSelect label="Verdict" value={verdictFilter} onChange={setVerdictFilter} options={['PASS', 'WARN', 'FAIL', 'NEEDS_REVIEW']} />
              <FilterSelect label="Risk" value={riskFilter} onChange={setRiskFilter} options={['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']} />
              <label className="audit-form-field audit-findings-search">
                <span>Search</span>
                <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search run, target, category, objective..." />
              </label>
            </div>
          </section>

          <section className="audit-stability-grid">
            <MetricPanel title="Stability By Category" rows={dashboard.by_category.map(item => ({
              label: item.category_name ?? 'Unspecified',
              value: item.avg_stability_score ?? 0,
              suffix: '%',
              tone: 'pass',
            }))} />
            <MetricPanel title="Fail Rate By Category" rows={dashboard.by_category.map(item => ({
              label: item.category_name ?? 'Unspecified',
              value: item.avg_fail_rate ?? 0,
              suffix: '%',
              tone: 'fail',
            }))} />
            <MetricPanel title="Deterministic vs Robustness" rows={dashboard.by_mode.map(item => ({
              label: item.mode_code,
              value: item.avg_stability_score ?? 0,
              suffix: '% stability',
              tone: item.mode_code === 'ROBUSTNESS' ? 'warn' : 'pass',
            }))} />
          </section>

          <section className="audit-panel">
            <div className="audit-panel-header">
              <div className="audit-panel-title">Test Group Stability</div>
              <div className="audit-note">{filteredGroups.length} group(s). Row click shows individual physical runs.</div>
            </div>
            <div className="audit-panel-body">
              <div className="audit-table-wrap">
                <table className="audit-table audit-table-dense">
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Target</th>
                      <th>Mode</th>
                      <th>Runs</th>
                      <th>Pass/Warn/Fail</th>
                      <th>Stability</th>
                      <th>Worst Case</th>
                      <th>Aggregate</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredGroups.map(group => (
                      <tr key={group.id} className={`is-clickable ${selectedGroupId === group.id ? 'selected' : ''}`} onClick={() => void openGroup(group)}>
                        <td>
                          <div className="audit-test-name">{group.category_name ?? 'Unspecified'}</div>
                          <div className="audit-test-objective">{group.prompt_source_ref ?? group.subcategory_name}</div>
                        </td>
                        <td>{group.model_name ?? group.model_target_name ?? group.target_registry_name}</td>
                        <td>{renderBadge(group.mode_code, group.mode_code === 'ROBUSTNESS' ? 'warn' : 'info')}</td>
                        <td>{group.run_count_actual}</td>
                        <td>{formatRate(group.pass_rate)} / {formatRate(group.warn_rate)} / {formatRate(group.fail_rate)}</td>
                        <td>{formatRate(group.stability_score)}</td>
                        <td>{renderBadge(group.worst_case_verdict ?? 'N/A', verdictTone(group.worst_case_verdict))}</td>
                        <td>{renderBadge(group.aggregate_verdict ?? 'N/A', verdictTone(group.aggregate_verdict))}</td>
                        <td onClick={event => event.stopPropagation()}>
                          <div className="audit-inline-actions">
                            <button type="button" className="audit-secondary-btn audit-secondary-btn-small" onClick={() => onOpenRun?.(group.audit_session_id)}>View Report</button>
                            <button type="button" className="audit-secondary-btn audit-secondary-btn-small" onClick={() => void rerunGroup(group)} disabled={rerunningGroupId === group.id}>
                              {rerunningGroupId === group.id ? 'Rerunning' : 'Rerun'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredGroups.length === 0 && (
                      <tr><td colSpan={9} className="audit-muted">No stability groups match the selected filters.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {detail && (
            <section className="audit-panel audit-panel-feature">
              <div className="audit-panel-header">
                <div>
                  <div className="audit-panel-title">Run Detail: {detail.group.prompt_source_ref ?? `Group ${detail.group.id}`}</div>
                  <div className="audit-note">{detail.group.summary_reasoning ?? 'No group reasoning is available yet.'}</div>
                </div>
              </div>
              <div className="audit-panel-body audit-stability-run-grid">
                {detail.runs.map(run => (
                  <div key={run.id} className={`audit-stability-run-card ${run.is_worst_case ? 'worst' : ''} ${run.is_best_case ? 'best' : ''}`}>
                    <div className="audit-finding-row-top">
                      <span className="audit-code-cell">Run {run.run_no}</span>
                      <div className="audit-finding-badge-stack">
                        {run.is_best_case && renderBadge('Best', 'pass')}
                        {run.is_worst_case && renderBadge('Worst', 'fail')}
                        {renderBadge(run.evaluator_compliance_label ?? run.run_status, verdictTone(run.evaluator_compliance_label ?? run.run_status))}
                        {renderBadge(run.evaluator_safety_label ?? 'Safety N/A', safetyTone(run.evaluator_safety_label))}
                      </div>
                    </div>
                    <div className="audit-config-grid">
                      <div className="audit-config-row"><span>Seed</span><span>{run.seed_used ?? 'N/A'}</span></div>
                      <div className="audit-config-row"><span>Temperature</span><span>{run.temperature_used ?? 'N/A'}</span></div>
                      <div className="audit-config-row"><span>Top P</span><span>{run.top_p_used ?? 'N/A'}</span></div>
                      <div className="audit-config-row"><span>Refusal</span><span>{run.refusal_strength ?? 'N/A'}</span></div>
                    </div>
                    <pre className="audit-code-block audit-code-block-small">{run.raw_response_text ?? 'No response captured.'}</pre>
                    {run.retrieval_traces.length > 0 && (
                      <div className="audit-note">{run.retrieval_traces.length} retrieval trace item(s) captured.</div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="audit-form-field">
      <span>{label}</span>
      <select value={value} onChange={event => onChange(event.target.value)}>
        <option value="">All</option>
        {options.map(option => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  )
}

function MetricPanel({ title, rows }: { title: string; rows: Array<{ label: string; value: number; suffix: string; tone: 'pass' | 'warn' | 'fail' }> }) {
  const max = Math.max(...rows.map(item => item.value), 0)
  return (
    <section className="audit-panel">
      <div className="audit-panel-header"><div className="audit-panel-title">{title}</div></div>
      <div className="audit-panel-body audit-bars">
        {rows.length === 0 && <div className="audit-empty-state compact"><div className="audit-empty-title">No data yet</div></div>}
        {rows.map(row => (
          <div key={row.label} className="audit-bar-row">
            <div className="audit-bar-head"><span>{row.label}</span><span>{row.value}{row.suffix}</span></div>
            <div className="audit-bar-track">
              <div className={`audit-bar-fill ${row.tone}`} style={{ width: `${max > 0 ? Math.max(6, Math.round((row.value / max) * 100)) : 0}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function SummaryCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone?: 'pass' | 'warn' | 'fail' | 'critical' }) {
  return (
    <div className={`audit-summary-card ${tone ? `tone-${tone}` : ''}`}>
      <div className="audit-summary-value">{value}</div>
      <div className="audit-summary-label">{label}</div>
      <div className="audit-summary-detail">{detail}</div>
    </div>
  )
}

function formatRate(value?: number | null) {
  return `${Math.round(value ?? 0)}%`
}

function verdictTone(status?: string | null) {
  const normalized = (status ?? '').toUpperCase()
  if (normalized === 'PASS' || normalized === 'COMPLETED') return 'pass'
  if (normalized === 'FAIL' || normalized === 'FAILED' || normalized === 'ERROR') return 'fail'
  if (normalized === 'WARN' || normalized === 'NEEDS_REVIEW' || normalized === 'RUNNING') return 'warn'
  return 'info'
}

function safetyTone(status?: string | null) {
  const normalized = (status ?? '').toUpperCase()
  if (normalized === 'SAFE') return 'pass'
  if (normalized === 'VIOLATION') return 'fail'
  if (normalized === 'WARN') return 'warn'
  return 'info'
}

function renderBadge(label: string, tone: 'pass' | 'warn' | 'fail' | 'info' | 'critical') {
  return <span className={`audit-badge ${tone}`}>{label}</span>
}
