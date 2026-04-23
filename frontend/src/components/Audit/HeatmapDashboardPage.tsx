import { useEffect, useMemo, useState } from 'react'
import type { AuditFindingsFilters } from '../../App'
import { auditApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type {
  HeatmapCell,
  HeatmapDashboardResponse,
  PassRateMatrixCell,
} from '../../types'
import './auditPlatform.css'

const SEVERITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const

interface HeatmapDashboardPageProps {
  onOpenRun: (runId: string, filters?: AuditFindingsFilters) => void
  onOpenPromptVariants: () => void
  onOpenFindings: () => void
}

export default function HeatmapDashboardPage({ onOpenRun, onOpenPromptVariants, onOpenFindings }: HeatmapDashboardPageProps) {
  const [dashboard, setDashboard] = useState<HeatmapDashboardResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const response = await auditApi.getHeatmapDashboard()
        setDashboard(response)
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }
    void load()
  }, [])

  const categoryOrder = useMemo(
    () => dashboard ? Array.from(new Set(dashboard.category_severity_matrix.map(item => item.category_name))) : [],
    [dashboard],
  )

  const maxSeverityCount = useMemo(
    () => dashboard ? Math.max(...dashboard.category_severity_matrix.map(item => item.count), 0) : 0,
    [dashboard],
  )

  const timelineRows = useMemo(() => {
    if (!dashboard) return []
    return categoryOrder.map(category => ({
      category,
      cells: dashboard.run_labels.map(run => (
        dashboard.category_run_pass_rate.find(cell => cell.category_name === category && cell.run_id === run.run_id)
        ?? emptyPassRateCell(category, run.run_id)
      )),
    }))
  }, [categoryOrder, dashboard])

  const modelRowOrder = useMemo(() => {
    if (!dashboard) return []
    return Array.from(new Set(dashboard.test_model_matrix.map(item => `${item.category_name}::${item.test_identifier}::${item.attack_type}`)))
  }, [dashboard])

  const maxRiskCount = useMemo(
    () => dashboard ? Math.max(...dashboard.risk_score_distribution.map(item => item.result_count), 0) : 0,
    [dashboard],
  )

  const periodLabel = useMemo(() => {
    if (!dashboard || dashboard.run_labels.length === 0) return 'No completed runs'
    const dates = dashboard.run_labels.map(item => new Date(item.completed_at))
    const min = new Date(Math.min(...dates.map(item => item.getTime())))
    const max = new Date(Math.max(...dates.map(item => item.getTime())))
    const format = (value: Date) => value.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    return min.toDateString() === max.toDateString() ? format(min) : `${format(min)} - ${format(max)}`
  }, [dashboard])

  const targetLabel = useMemo(() => {
    if (!dashboard) return 'No targets'
    if (dashboard.totals.target_count <= 1) return dashboard.recent_runs[0]?.model_name ?? 'Single target'
    return `${dashboard.totals.target_count} targets`
  }, [dashboard])

  if (!dashboard && !error) {
    return <div className="audit-platform"><div className="audit-message">Loading analyst heatmap dashboard from SQLite...</div></div>
  }

  const hasRuns = Boolean(dashboard && dashboard.totals.run_count > 0)
  const latestRunId = dashboard?.recent_runs[0]?.job_id

  return (
    <div className="audit-platform audit-analyst-shell">
      <section className="audit-analyst-header">
        <div className="audit-analyst-header-main">
          <div className="audit-analyst-brand">
            <div className="audit-analyst-mark">Sa</div>
            <div>
              <div className="audit-analyst-title">Heatmap Dashboard</div>
              <div className="audit-analyst-subtitle">
                Dense analyst dashboard for category severity concentration, model-level behavior, run timelines, and activity density.
              </div>
            </div>
          </div>
          <div className="audit-analyst-nav">
            <button type="button" className="audit-analyst-tab" onClick={onOpenFindings} disabled={!latestRunId}>Findings</button>
            <button type="button" className="audit-analyst-tab" onClick={onOpenPromptVariants}>Prompt Variants</button>
            <button type="button" className="audit-analyst-tab active">Heatmap Dashboard</button>
          </div>
        </div>
        <div className="audit-analyst-meta">
          <div className="audit-analyst-chip"><span>Period</span><strong>{periodLabel}</strong></div>
          <div className="audit-analyst-chip"><span>Target</span><strong>{targetLabel}</strong></div>
          <div className="audit-analyst-chip"><span>Runs</span><strong>{dashboard?.totals.run_count ?? 0}</strong></div>
        </div>
      </section>

      {error && <div className="audit-message error">{error}</div>}

      {dashboard && (
        <>
          <section className="audit-analyst-kpis">
            <AnalystKpiCard label="Failure Rate" value={`${Math.max(0, 100 - dashboard.totals.pass_rate)}%`} tone="fail" detail={`${dashboard.totals.fail_count} fail verdicts`} />
            <AnalystKpiCard label="Critical Findings" value={dashboard.category_severity_matrix.filter(item => item.severity === 'CRITICAL').reduce((sum, item) => sum + item.count, 0).toString()} tone="fail" detail="Critical severity cells" />
            <AnalystKpiCard label="Warn Rate" value={dashboard.totals.total_tests ? `${Math.round((dashboard.totals.warn_count / dashboard.totals.total_tests) * 100)}%` : '0%'} tone="warn" detail={`${dashboard.totals.warn_count} warn verdicts`} />
            <AnalystKpiCard label="Pass Rate" value={`${dashboard.totals.pass_rate}%`} tone="pass" detail={`${dashboard.totals.pass_count} pass verdicts`} />
            <AnalystKpiCard label="Total Tests Run" value={dashboard.totals.total_tests.toString()} detail={`${dashboard.totals.run_count} completed runs`} />
            <AnalystKpiCard label="Systems Audited" value={dashboard.totals.target_count.toString()} detail={`${dashboard.totals.model_count} distinct models`} />
          </section>

          {!hasRuns && (
            <section className="audit-empty-state">
              <div className="audit-empty-title">No structured runs are available for heatmap analysis</div>
              <div className="audit-empty-copy">
                Heatmap panels activate only after workbook-backed audit runs complete. Current visuals intentionally stay empty instead of fabricating analyst data.
              </div>
            </section>
          )}

          {hasRuns && (
            <>
              <section className="audit-analyst-grid audit-analyst-grid-primary">
                <div className="audit-panel audit-panel-feature audit-analyst-panel">
                  <div className="audit-panel-header">
                    <div>
                      <div className="audit-panel-title">Test x Model Failure Heatmap</div>
                      <div className="audit-note">Cell = dominant verdict across real completed results for a test and model.</div>
                    </div>
                    <div className="audit-legend">
                      <LegendSwatch label="Pass" tone="pass" />
                      <LegendSwatch label="Warn" tone="warn" />
                      <LegendSwatch label="Fail" tone="fail" />
                    </div>
                  </div>
                  <div className="audit-panel-body">
                    {dashboard.test_model_matrix.length === 0 || dashboard.model_names.length === 0 ? (
                      <div className="audit-empty-state compact">
                        <div className="audit-empty-title">Model matrix unavailable</div>
                        <div className="audit-empty-copy">
                          Not enough completed results exist to build a real test-by-model matrix yet.
                        </div>
                      </div>
                    ) : (
                      <div className="audit-analyst-matrix">
                        <div className="audit-analyst-matrix-head">
                          <div className="audit-analyst-matrix-label">Test</div>
                          {dashboard.model_names.map(model => (
                            <div key={model} className="audit-analyst-matrix-axis">{model}</div>
                          ))}
                        </div>
                        {modelRowOrder.map(rowKey => {
                          const [categoryName, testIdentifier, attackType] = rowKey.split('::')
                          return (
                            <div key={rowKey} className="audit-analyst-matrix-row">
                              <div className="audit-analyst-row-label">
                                <div className="audit-code-cell">{testIdentifier}</div>
                                <div className="audit-test-objective">{attackType} | {categoryName}</div>
                              </div>
                              {dashboard.model_names.map(modelName => {
                                const cell = dashboard.test_model_matrix.find(item => item.test_identifier === testIdentifier && item.model_name === modelName)
                                return (
                                  <button
                                    key={`${rowKey}-${modelName}`}
                                    type="button"
                                    className={`audit-analyst-cell ${cell ? verdictTone(cell.dominant_status) : 'info'}`}
                                    title={cell
                                      ? `${testIdentifier} | ${modelName} | pass ${cell.pass_count}, warn ${cell.warn_count}, fail ${cell.fail_count}`
                                      : `${testIdentifier} | ${modelName} | no completed result`
                                    }
                                    disabled={!cell?.drilldown_supported}
                                    onClick={() => {
                                      if (cell?.drilldown_supported && cell.drilldown_run_id) {
                                        onOpenRun(cell.drilldown_run_id, { search: testIdentifier })
                                      }
                                    }}
                                  >
                                    <span>{cell?.dominant_status ?? '—'}</span>
                                  </button>
                                )
                              })}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </div>

                <div className="audit-panel audit-analyst-panel">
                  <div className="audit-panel-header">
                    <div>
                      <div className="audit-panel-title">Category x Severity Matrix</div>
                      <div className="audit-note">Click a populated category/severity cell to open findings in the latest run context.</div>
                    </div>
                  </div>
                  <div className="audit-panel-body">
                    <div className="audit-heatmap audit-heatmap-compact">
                      <div className="audit-heatmap-corner">Category</div>
                      {SEVERITY_ORDER.map(severity => (
                        <div key={severity} className="audit-heatmap-axis">{severity}</div>
                      ))}
                      {categoryOrder.map(category => (
                        <MatrixSeverityRow
                          key={category}
                          category={category}
                          cells={SEVERITY_ORDER.map(severity => (
                            dashboard.category_severity_matrix.find(cell => cell.category_name === category && cell.severity === severity)
                            ?? emptySeverityCell(category, severity)
                          ))}
                          maxHeatCount={maxSeverityCount}
                          onCellClick={(cell) => {
                            if (latestRunId) {
                              onOpenRun(latestRunId, { category: cell.category_name, severity: cell.severity })
                            }
                          }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              <section className="audit-analyst-grid audit-analyst-grid-secondary">
                <div className="audit-panel audit-analyst-panel">
                  <div className="audit-panel-header">
                    <div>
                      <div className="audit-panel-title">Category Pass-Rate Matrix</div>
                      <div className="audit-note">Rows are workbook categories. Columns are recent completed runs.</div>
                    </div>
                  </div>
                  <div className="audit-panel-body">
                    <div className="audit-pass-rate-matrix">
                      <div className="audit-pass-rate-head">
                        <div className="audit-pass-rate-label">Category</div>
                        {dashboard.run_labels.map(run => (
                          <div key={run.run_id} className="audit-pass-rate-axis" title={`${run.run_id} | ${run.model_name ?? 'Unknown model'}`}>
                            {run.label}
                          </div>
                        ))}
                      </div>
                      {timelineRows.map(row => (
                        <div key={row.category} className="audit-pass-rate-row">
                          <div className="audit-pass-rate-label">{row.category}</div>
                          {row.cells.map(cell => (
                            <button
                              key={`${cell.category_name}-${cell.run_id}`}
                              type="button"
                              className={`audit-pass-rate-cell ${passRateTone(cell.pass_rate)}`}
                              title={`${cell.category_name} | ${cell.run_id} | ${cell.pass_rate ?? 'N/A'}% pass | ${cell.total_count} results`}
                              disabled={!cell.drilldown_supported}
                              onClick={() => {
                                if (cell.drilldown_supported) {
                                  onOpenRun(cell.run_id, { category: cell.category_name })
                                }
                              }}
                            >
                              <span>{cell.pass_rate === null || cell.pass_rate === undefined ? '—' : `${Math.round(cell.pass_rate)}%`}</span>
                            </button>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="audit-panel audit-analyst-panel">
                  <div className="audit-panel-header">
                    <div>
                      <div className="audit-panel-title">Audit Activity Heatmap</div>
                      <div className="audit-note">Daily finding density over recent completed structured runs.</div>
                    </div>
                  </div>
                  <div className="audit-panel-body">
                    <div className="audit-activity-grid">
                      {dashboard.activity_heatmap.map(cell => (
                        <button
                          key={cell.activity_date}
                          type="button"
                          className={`audit-activity-cell ${activityTone(cell.failure_density)}`}
                          title={`${cell.activity_date} | ${cell.run_count} runs | ${cell.finding_count} findings / ${cell.total_tests} tests`}
                          disabled={!cell.drilldown_supported}
                          onClick={() => {
                            if (cell.drilldown_supported && cell.single_run_id) {
                              onOpenRun(cell.single_run_id)
                            }
                          }}
                        >
                          <span>{formatShortDay(cell.activity_date)}</span>
                        </button>
                      ))}
                    </div>
                    <div className="audit-activity-legend">
                      <span>Clean</span>
                      <span className="audit-legend-swatch zero" />
                      <span className="audit-legend-swatch low" />
                      <span className="audit-legend-swatch high" />
                      <span>Dense findings</span>
                    </div>
                  </div>
                </div>
              </section>

              <section className="audit-panel audit-analyst-panel">
                <div className="audit-panel-header">
                  <div>
                    <div className="audit-panel-title">Risk Score Distribution Heatmap</div>
                    <div className="audit-note">Score bucket x category. Bubble size reflects result count. Color tracks finding density.</div>
                  </div>
                </div>
                <div className="audit-panel-body">
                  {dashboard.risk_score_distribution.length === 0 ? (
                    <div className="audit-empty-state compact">
                      <div className="audit-empty-title">Risk score distribution unavailable</div>
                      <div className="audit-empty-copy">Completed results with numeric scores are required before the distribution can render.</div>
                    </div>
                  ) : (
                    <div className="audit-risk-bubble-chart">
                      {categoryOrder.map(category => {
                        const points = dashboard.risk_score_distribution.filter(item => item.category_name === category)
                        return (
                          <div key={category} className="audit-risk-bubble-row">
                            <div className="audit-risk-bubble-label">{category}</div>
                            <div className="audit-risk-bubble-track">
                              {points.map(point => (
                                <button
                                  key={`${category}-${point.score_bucket}`}
                                  type="button"
                                  className={`audit-risk-bubble ${riskBubbleTone(point.failure_density)}`}
                                  title={`${category} | score ${point.score_bucket}-${Math.min(point.score_bucket + 9, 100)} | ${point.result_count} results`}
                                  style={{
                                    left: `calc(${point.score_bucket}% - 10px)`,
                                    width: `${Math.max(12, Math.round((point.result_count / Math.max(maxRiskCount, 1)) * 28))}px`,
                                    height: `${Math.max(12, Math.round((point.result_count / Math.max(maxRiskCount, 1)) * 28))}px`,
                                  }}
                                  disabled={!latestRunId}
                                  onClick={() => {
                                    if (latestRunId) {
                                      onOpenRun(latestRunId, { category })
                                    }
                                  }}
                                />
                              ))}
                            </div>
                          </div>
                        )
                      })}
                      <div className="audit-risk-axis">
                        {[0, 20, 40, 60, 80, 100].map(value => <span key={value}>{value}</span>)}
                      </div>
                    </div>
                  )}
                </div>
              </section>

              <section className="audit-panel audit-analyst-panel">
                <div className="audit-panel-header">
                  <div>
                    <div className="audit-panel-title">Recent Audits</div>
                    <div className="audit-note">Run click opens findings. Structured audit history only.</div>
                  </div>
                </div>
                <div className="audit-panel-body">
                  <div className="audit-table-wrap">
                    <table className="audit-table audit-table-dense">
                      <thead>
                        <tr>
                          <th>Run</th>
                          <th>Model</th>
                          <th>Pass</th>
                          <th>Fail</th>
                          <th>Warn</th>
                          <th>Timestamp</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.recent_runs.map(run => (
                          <tr key={run.job_id} className="is-clickable" onClick={() => onOpenRun(run.job_id)}>
                            <td className="audit-code-cell">{run.job_id}</td>
                            <td>{run.model_name ?? run.target_registry_name}</td>
                            <td>{run.pass_count}</td>
                            <td>{run.fail_count}</td>
                            <td>{run.warn_count}</td>
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

function AnalystKpiCard({ label, value, tone, detail }: { label: string; value: string; tone?: 'pass' | 'warn' | 'fail'; detail?: string }) {
  return (
    <div className={`audit-analyst-kpi ${tone ? `tone-${tone}` : ''}`}>
      <div className="audit-analyst-kpi-value">{value}</div>
      <div className="audit-analyst-kpi-label">{label}</div>
      {detail && <div className="audit-analyst-kpi-detail">{detail}</div>}
    </div>
  )
}

function MatrixSeverityRow({
  category,
  cells,
  maxHeatCount,
  onCellClick,
}: {
  category: string
  cells: HeatmapCell[]
  maxHeatCount: number
  onCellClick: (cell: HeatmapCell) => void
}) {
  return (
    <>
      <div className="audit-heatmap-row-label">{category}</div>
      {cells.map(cell => {
        const intensity = maxHeatCount > 0 ? cell.count / maxHeatCount : 0
        return (
          <button
            key={`${cell.category_name}-${cell.severity}`}
            type="button"
            className={`audit-heatmap-cell ${severityTone(cell.severity)} analyst`}
            style={{ opacity: Math.max(0.2, intensity || 0.08) }}
            title={`${cell.category_name} | ${cell.severity} | ${cell.count} findings`}
            disabled={cell.count === 0}
            onClick={() => onCellClick(cell)}
          >
            <span>{cell.count}</span>
          </button>
        )
      })}
    </>
  )
}

function LegendSwatch({ label, tone }: { label: string; tone: 'pass' | 'warn' | 'fail' }) {
  return (
    <div className="audit-legend-item">
      <span className={`audit-legend-swatch ${tone}`} />
      <span>{label}</span>
    </div>
  )
}

function emptySeverityCell(category: string, severity: string): HeatmapCell {
  return {
    category_name: category,
    severity: severity as HeatmapCell['severity'],
    count: 0,
    total_count: 0,
  }
}

function emptyPassRateCell(category: string, runId: string): PassRateMatrixCell {
  return {
    category_name: category,
    run_id: runId,
    total_count: 0,
    finding_count: 0,
    pass_rate: null,
    drilldown_supported: false,
  }
}

function verdictTone(status?: string | null) {
  const normalized = (status ?? '').toUpperCase()
  if (normalized === 'PASS') return 'pass'
  if (normalized === 'WARN') return 'warn'
  if (normalized === 'FAIL' || normalized === 'ERROR') return 'fail'
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

function passRateTone(value?: number | null) {
  if (value === null || value === undefined) return 'empty'
  if (value >= 80) return 'pass'
  if (value >= 50) return 'warn'
  return 'fail'
}

function activityTone(value: number) {
  if (value >= 75) return 'critical'
  if (value >= 50) return 'high'
  if (value >= 20) return 'medium'
  if (value > 0) return 'low'
  return 'empty'
}

function riskBubbleTone(value: number) {
  if (value >= 75) return 'fail'
  if (value >= 40) return 'warn'
  return 'pass'
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

function formatShortDay(value: string) {
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
