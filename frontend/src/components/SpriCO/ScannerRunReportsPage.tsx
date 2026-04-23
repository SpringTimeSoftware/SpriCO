import { useEffect, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { garakApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { GarakScanReport, GarakScannerReportSummary } from '../../types'
import type { ViewName } from '../Sidebar/Navigation'
import { Badge, EmptyMessage, ErrorMessage, FieldHelp, LoadingMessage, PageHelp, formatDateTime, valueText } from './common'
import { ScanReport } from './GarakScannerPage'
import './spricoPlatform.css'

interface ScannerRunReportsPageProps {
  onNavigate?: (view: ViewName) => void
}

export default function ScannerRunReportsPage({ onNavigate }: ScannerRunReportsPageProps = {}) {
  const [reports, setReports] = useState<GarakScanReport[]>([])
  const [summary, setSummary] = useState<GarakScannerReportSummary | null>(null)
  const [selectedReport, setSelectedReport] = useState<GarakScanReport | null>(null)
  const [showRaw, setShowRaw] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const response = await garakApi.listReports()
      setReports(response.reports)
      setSummary(response.summary)
      setSelectedReport(prev => {
        if (prev && response.reports.some(report => report.scan_id === prev.scan_id)) {
          return response.reports.find(report => report.scan_id === prev.scan_id) ?? response.reports[0] ?? null
        }
        return response.reports[0] ?? null
      })
      setShowRaw(false)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading scanner run reports" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Scanner Run Reports</div>
          <div className="sprico-subtitle">
            Scanner Run Reports list every LLM Vulnerability Scanner job, including completed no-finding, timeout, failed, and not-evaluated runs.
          </div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <PageHelp>
        Scanner Run Reports are the scanner job ledger. Evidence Center stores proof produced by completed scans, and Findings stores only actionable SpriCO outcomes.
      </PageHelp>

      <ErrorMessage error={error} />

      {summary && (
        <section className="sprico-panel">
          <div className="sprico-panel-title">Scanner Run Metrics</div>
          <div className="sprico-kpis">
            <Metric label="Scanner Runs Total" value={String(summary.scanner_runs_total)} />
            <Metric label="Runs With Findings" value={String(summary.scanner_runs_with_findings)} />
            <Metric label="Completed No Findings" value={String(summary.scanner_runs_with_no_findings)} />
            <Metric label="Timeout Runs" value={String(summary.scanner_runs_timeout ?? 0)} />
            <Metric label="Failed / Not Evaluated" value={String(summary.scanner_runs_failed ?? 0)} />
            <Metric label="High / Critical Scanner Findings" value={String(summary.high_critical_scanner_findings)} />
            <Metric label="Scanner Evidence Produced" value={String(summary.scanner_evidence_count)} />
            <Metric label="Artifacts Stored" value={String(summary.artifacts_stored)} />
          </div>
        </section>
      )}

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Scanner Runs</div>
          <FieldHelp>No-finding scans appear here even though they do not create Findings.</FieldHelp>
          <div className="sprico-table-wrap">
            <table className="sprico-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Target</th>
                  <th>Profile</th>
                  <th>Categories</th>
                  <th>Status</th>
                  <th>Final SpriCO Verdict</th>
                  <th>Risk</th>
                  <th>Evidence Count</th>
                  <th>Findings Count</th>
                  <th>Probe Count</th>
                  <th>Artifact Count</th>
                </tr>
              </thead>
              <tbody>
                {reports.map(report => (
                  <tr
                    key={report.scan_id}
                    className="is-clickable"
                    onClick={() => {
                      setSelectedReport(report)
                      setShowRaw(false)
                    }}
                  >
                    <td>{formatDateTime(report.finished_at ?? report.started_at, 'not recorded')}</td>
                    <td>{valueText(report.target_name ?? report.target_id, 'not recorded')}</td>
                    <td>{valueText(report.scan_profile, 'not recorded')}</td>
                    <td>{report.vulnerability_categories?.length ?? 0}</td>
                    <td><Badge value={report.status} /></td>
                    <td><Badge value={report.final_sprico_verdict ?? report.final_verdict} /></td>
                    <td><Badge value={report.violation_risk ?? report.risk} /></td>
                    <td>{report.evidence_count ?? 0}</td>
                    <td>{report.findings_count ?? 0}</td>
                    <td>{report.resolved_probes_count ?? 0}</td>
                    <td>{report.artifact_count ?? report.artifacts?.length ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {reports.length === 0 && <EmptyMessage>No scanner run reports found.</EmptyMessage>}
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Selected Scanner Run Report</div>
          {!selectedReport && <EmptyMessage>Select a scanner run report.</EmptyMessage>}
          {selectedReport && (
            <ScanReport
              scan={selectedReport}
              currentConfigTarget={valueText(selectedReport.target_name ?? selectedReport.target_id)}
              selectedResultTarget={valueText(selectedReport.target_name ?? selectedReport.target_id)}
              selectedResultDiffers={false}
              fallbackTargetDomain={valueText(reportPolicyContext(selectedReport).selected_target_domain ?? reportPolicyContext(selectedReport).target_domain, 'not recorded')}
              fallbackPolicyDomain={valueText(reportPolicyContext(selectedReport).policy_domain, 'not recorded')}
              fallbackPolicyLabel={valueText(selectedReport.policy_name ?? selectedReport.policy_id, 'not recorded')}
              showRaw={showRaw}
              onToggleRaw={() => setShowRaw(value => !value)}
              onOpenFindings={onNavigate ? () => onNavigate('findings') : undefined}
            />
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

function reportPolicyContext(report: GarakScanReport): Record<string, unknown> {
  const value = report.config?.policy_context
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}
