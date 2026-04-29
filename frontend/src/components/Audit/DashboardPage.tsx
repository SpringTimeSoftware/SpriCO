import { useEffect, useMemo, useState } from 'react'
import type { AuditFindingsFilters } from '../../App'
import { auditApi, garakApi, spricoRunsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { AuditDashboardResponse, GarakScannerReportSummary, SpriCORunSummary } from '../../types'
import './auditPlatform.css'

interface DashboardPageProps {
  onOpenRun: (runId: string, filters?: AuditFindingsFilters) => void
}

export default function DashboardPage({ onOpenRun }: DashboardPageProps) {
  const [dashboard, setDashboard] = useState<AuditDashboardResponse | null>(null)
  const [scannerSummary, setScannerSummary] = useState<GarakScannerReportSummary | null>(null)
  const [runSummary, setRunSummary] = useState<SpriCORunSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [response, scannerResponse, unifiedRuns] = await Promise.all([
          auditApi.getDashboard(),
          garakApi.getReportSummary().catch(() => null),
          spricoRunsApi.summary().catch(() => null),
        ])
        setDashboard(response)
        setScannerSummary(scannerResponse)
        setRunSummary(unifiedRuns)
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }

    void load()
  }, [])

  const maxCategoryFindings = useMemo(() => {
    if (!dashboard) return 0
    return Math.max(...dashboard.violations_by_category.map(item => item.violations + item.partials), 0)
  }, [dashboard])

  if (!dashboard && !error) {
    return <div className="audit-platform"><div className="audit-message">Loading structured dashboard analytics from SQLite...</div></div>
  }

  const hasCompletedRuns = Boolean(dashboard && dashboard.totals.run_count > 0)

  return (
    <div className="audit-platform audit-dashboard-shell">
      <section className="audit-hero audit-hero-compact">
        <div>
          <div className="audit-hero-title">Structured Audit Dashboard</div>
          <div className="audit-hero-subtitle">
            Dashboard metrics reflect completed structured audit runs only. Manual PyRIT attack history is separate.
          </div>
        </div>
        <div className="audit-hero-meta audit-hero-meta-row">
          <div className="audit-meta-card">
            <div className="audit-meta-label">Primary View</div>
            <div className="audit-meta-value">Category Violations</div>
          </div>
          <div className="audit-meta-card">
            <div className="audit-meta-label">Data Scope</div>
            <div className="audit-meta-value">Completed structured audits</div>
          </div>
        </div>
      </section>

      {error && <div className="audit-message error">{error}</div>}

      {dashboard && (
        <>
          <section className="audit-kpi-grid">
            <SummaryCard label="Completed Runs" value={dashboard.totals.run_count.toString()} detail="Structured runs only" />
            <SummaryCard label="Executed Tests" value={dashboard.totals.total_tests.toString()} detail="Completed results" />
            <SummaryCard label="Pass Rate" value={`${dashboard.totals.pass_rate}%`} detail="PASS / total" tone="pass" />
            <SummaryCard label="Fail Count" value={dashboard.totals.fail_count.toString()} detail="FAIL verdicts" tone="fail" />
            <SummaryCard label="Warn Count" value={dashboard.totals.warn_count.toString()} detail="WARN verdicts" tone="warn" />
            <SummaryCard label="Critical Findings" value={dashboard.totals.critical_findings.toString()} detail="Critical severity FAIL/WARN" tone="critical" />
          </section>

          {runSummary && (
            <section className="audit-panel">
              <div className="audit-panel-header">
                <div>
                  <div className="audit-panel-title">Unified Run Coverage</div>
                  <div className="audit-note">
                    Unified run coverage counts interactive audit, structured audit, benchmark replay, AuditSpec, promptfoo runtime, scanner, red campaign, Shield, and condition simulation records. No-finding runs count as coverage without becoming Findings.
                  </div>
                </div>
              </div>
              <div className="audit-panel-body">
                <section className="audit-kpi-grid">
                  <SummaryCard label="All Run Records" value={String(runSummary.total_runs)} detail="Unified registry" />
                  <SummaryCard label="No-Finding Runs" value={String(runSummary.coverage.no_finding_runs)} detail="Coverage only" tone="pass" />
                  <SummaryCard label="Runs With Findings" value={String(runSummary.coverage.runs_with_findings)} detail="Actionable outcomes" tone="warn" />
                  <SummaryCard label="Not Evaluated" value={String(runSummary.coverage.not_evaluated_runs)} detail="Timeout / failed / unavailable" tone="fail" />
                  <SummaryCard label="Evidence Total" value={String(runSummary.coverage.evidence_total)} detail="Evidence records" />
                  <SummaryCard label="Targets Covered" value={String(runSummary.coverage.targets_covered)} detail="Unique targets" />
                </section>
                <div className="audit-structured-grid">
                  <ScannerBreakdown title="Runs By Type" rows={runSummary.by_run_type.map(item => ({ label: item.label, count: item.count }))} />
                  <ScannerBreakdown title="Runs By Page" rows={runSummary.by_source_page.map(item => ({ label: item.label, count: item.count }))} />
                  <ScannerBreakdown title="Runs By Verdict" rows={runSummary.by_final_verdict.map(item => ({ label: item.label, count: item.count }))} />
                </div>
              </div>
            </section>
          )}

          {scannerSummary && (
            <section className="audit-panel">
              <div className="audit-panel-header">
                <div>
                  <div className="audit-panel-title">LLM Scanner Run Coverage</div>
                  <div className="audit-note">
                    Scanner runs include completed no-finding, timeout, failed, and not-evaluated LLM Vulnerability Scanner jobs. No-finding scans count toward coverage but do not create Findings.
                  </div>
                </div>
              </div>
              <div className="audit-panel-body">
                <section className="audit-kpi-grid">
                  <SummaryCard label="Scanner Runs Total" value={scannerSummary.scanner_runs_total.toString()} detail="All scanner job statuses" />
                  <SummaryCard label="Completed No Findings" value={scannerSummary.scanner_runs_with_no_findings.toString()} detail="No actionable findings" tone="pass" />
                  <SummaryCard label="Timeout Runs" value={String(scannerSummary.scanner_runs_timeout ?? 0)} detail="Not evaluated as safe" tone="warn" />
                  <SummaryCard label="Failed / Not Evaluated" value={String(scannerSummary.scanner_runs_failed ?? 0)} detail="No safe verdict" tone="fail" />
                  <SummaryCard label="Runs With Findings" value={scannerSummary.scanner_runs_with_findings.toString()} detail="Actionable scanner issues" tone="warn" />
                  <SummaryCard label="High / Critical Scanner Findings" value={scannerSummary.high_critical_scanner_findings.toString()} detail="Scanner-linked triage items" tone="critical" />
                  <SummaryCard label="Scanner Evidence" value={scannerSummary.scanner_evidence_count.toString()} detail="Evidence Center records" />
                  <SummaryCard label="Artifacts Stored" value={scannerSummary.artifacts_stored.toString()} detail="Captured scanner artifacts" />
                </section>
                <div className="audit-structured-grid">
                  <ScannerBreakdown title="Scanner Runs By Status" rows={scannerSummary.scanner_runs_by_status.map(item => ({ label: item.status, count: item.count }))} />
                  <ScannerBreakdown title="Scanner Runs By Profile" rows={scannerSummary.scanner_runs_by_profile.map(item => ({ label: item.profile, count: item.count }))} />
                  <ScannerBreakdown title="Scanner Runs By Target" rows={scannerSummary.scanner_runs_by_target.map(item => ({ label: item.target, count: item.count }))} />
                </div>
              </div>
            </section>
          )}

          {!hasCompletedRuns && (
            <section className="audit-empty-state">
              <div className="audit-empty-title">No completed structured audit runs yet</div>
              <div className="audit-empty-copy">
                Run a workbook-backed audit from the Audit Runner. Category violations, pass rate, severity distribution, and recent findings will populate from SQLite once a structured run completes.
              </div>
            </section>
          )}

          {hasCompletedRuns && (
            <>
              <section className="audit-structured-grid">
                <div className="audit-panel audit-panel-feature audit-structured-main">
                  <div className="audit-panel-header">
                    <div>
                      <div className="audit-panel-title">Violations By Category</div>
                      <div className="audit-note">Critical and warning verdict concentration by workbook category.</div>
                    </div>
                  </div>
                  <div className="audit-panel-body">
                    <div className="audit-category-chart">
                      {dashboard.violations_by_category.map(item => {
                        const findingCount = item.violations + item.partials
                        const failHeight = maxCategoryFindings > 0 ? `${Math.round((item.violations / maxCategoryFindings) * 100)}%` : '0%'
                        const warnHeight = maxCategoryFindings > 0 ? `${Math.round((item.partials / maxCategoryFindings) * 100)}%` : '0%'
                        return (
                          <button
                            key={item.category_name}
                            type="button"
                            className="audit-category-column"
                            disabled={findingCount === 0 || dashboard.recent_runs.length === 0}
                            onClick={() => {
                              const run = dashboard.recent_runs[0]
                              if (run && findingCount > 0) {
                                onOpenRun(run.job_id, { category: item.category_name })
                              }
                            }}
                          >
                            <div className="audit-category-bar-frame">
                              <div className="audit-category-bar-stack">
                                <div className="audit-category-bar-segment fail" style={{ height: failHeight }} />
                                <div className="audit-category-bar-segment warn" style={{ height: warnHeight }} />
                              </div>
                            </div>
                            <div className="audit-category-bar-meta">
                              <span>{item.category_name}</span>
                              <strong>{findingCount}</strong>
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </div>

                <div className="audit-structured-sidebar">
                  <div className="audit-panel">
                    <div className="audit-panel-header">
                      <div className="audit-panel-title">Severity Distribution</div>
                      <div className="audit-note">Completed structured results by severity.</div>
                    </div>
                    <div className="audit-panel-body">
                      <div className="audit-severity-stack">
                        {dashboard.severity_distribution.map(item => (
                          <div key={item.severity} className="audit-severity-row">
                            <div className="audit-severity-head">
                              <span className={`audit-badge ${severityTone(item.severity)}`}>{item.severity}</span>
                              <span className="audit-muted">{item.count} findings / {item.total_count} total</span>
                            </div>
                            <div className="audit-bar-track">
                              <div
                                className={`audit-bar-fill ${severityTone(item.severity)}`}
                                style={{ width: item.total_count > 0 ? `${Math.max(8, Math.round((item.count / item.total_count) * 100))}%` : '0%' }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="audit-panel">
                    <div className="audit-panel-header">
                      <div className="audit-panel-title">Pass Rate</div>
                      <div className="audit-note">Completed structured audit runs only.</div>
                    </div>
                    <div className="audit-panel-body audit-pass-card">
                      <div
                        className="audit-pass-ring"
                        style={{ background: `conic-gradient(var(--audit-pass) 0 ${dashboard.totals.pass_rate}%, var(--audit-border) ${dashboard.totals.pass_rate}% 100%)` }}
                      >
                        <div className="audit-pass-ring-inner">
                          <div className="audit-pass-ring-value">{Math.round(dashboard.totals.pass_rate)}%</div>
                          <div className="audit-pass-ring-label">Pass Rate</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <section className="audit-panel">
                <div className="audit-panel-header">
                  <div className="audit-panel-title">Recent Audits</div>
                  <div className="audit-note">Row click opens run-scoped findings.</div>
                </div>
                <div className="audit-panel-body">
                  <div className="audit-table-wrap">
                    <table className="audit-table audit-table-dense">
                      <thead>
                        <tr>
                          <th>Job ID</th>
                          <th>Target</th>
                          <th>Status</th>
                          <th>Tests</th>
                          <th>Pass</th>
                          <th>Fail</th>
                          <th>Warn</th>
                          <th>Risk Level</th>
                          <th>Timestamp</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.recent_runs.map(run => (
                          <tr key={run.job_id} className="is-clickable" onClick={() => onOpenRun(run.job_id)}>
                            <td className="audit-code-cell">{run.job_id}</td>
                            <td>
                              <div className="audit-test-name">{run.model_name ?? run.target_registry_name}</div>
                              <div className="audit-test-objective">{run.endpoint ?? run.target_registry_name}</div>
                            </td>
                            <td>{renderBadge(run.status, verdictTone(run.status))}</td>
                            <td>{run.total_tests}</td>
                            <td>{run.pass_count}</td>
                            <td>{run.fail_count}</td>
                            <td>{run.warn_count}</td>
                            <td>{renderBadge(deriveRunRisk(run), riskTone(deriveRunRisk(run)))}</td>
                            <td className="audit-code-cell">{formatTimestamp(run.completed_at ?? run.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </section>
            </>
          )}
        </>
      )}
    </div>
  )
}

function SummaryCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string
  value: string
  detail: string
  tone?: 'pass' | 'warn' | 'fail' | 'critical'
}) {
  return (
    <div className={`audit-summary-card ${tone ? `tone-${tone}` : ''}`}>
      <div className="audit-summary-value">{value}</div>
      <div className="audit-summary-label">{label}</div>
      <div className="audit-summary-detail">{detail}</div>
    </div>
  )
}

function ScannerBreakdown({ title, rows }: { title: string; rows: Array<{ label: string; count: number }> }) {
  return (
    <div className="audit-panel">
      <div className="audit-panel-header">
        <div className="audit-panel-title">{title}</div>
      </div>
      <div className="audit-panel-body">
        {rows.length === 0 ? (
          <div className="audit-note">No scanner run data yet.</div>
        ) : (
          <div className="audit-severity-stack">
            {rows.map(row => (
              <div key={row.label} className="audit-severity-row">
                <div className="audit-severity-head">
                  <span>{row.label}</span>
                  <span className="audit-muted">{row.count}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function formatTimestamp(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function deriveRunRisk(run: AuditDashboardResponse['recent_runs'][number]) {
  if (run.fail_count > 0) return 'HIGH'
  if (run.warn_count > 0) return 'MEDIUM'
  return 'LOW'
}

function verdictTone(status?: string | null) {
  const normalized = (status ?? '').toUpperCase()
  if (normalized === 'COMPLETED' || normalized === 'PASS') return 'pass'
  if (normalized === 'FAILED' || normalized === 'FAIL' || normalized === 'ERROR') return 'fail'
  if (normalized === 'RUNNING' || normalized === 'PENDING' || normalized === 'WARN') return 'warn'
  return 'info'
}

function riskTone(risk?: string | null) {
  const normalized = (risk ?? '').toUpperCase()
  if (normalized === 'CRITICAL' || normalized === 'HIGH') return 'fail'
  if (normalized === 'MEDIUM') return 'warn'
  if (normalized === 'LOW') return 'pass'
  return 'info'
}

function severityTone(severity?: string | null) {
  const normalized = (severity ?? '').toUpperCase()
  if (normalized === 'CRITICAL') return 'critical'
  if (normalized === 'HIGH') return 'fail'
  if (normalized === 'MEDIUM') return 'warn'
  if (normalized === 'LOW') return 'pass'
  return 'info'
}

function renderBadge(label: string, tone: 'pass' | 'warn' | 'fail' | 'info' | 'critical') {
  return <span className={`audit-badge ${tone}`}>{label}</span>
}
