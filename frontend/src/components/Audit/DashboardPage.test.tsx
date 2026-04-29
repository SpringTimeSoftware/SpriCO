import { render, screen } from '@testing-library/react'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import DashboardPage from './DashboardPage'
import { auditApi, garakApi, spricoRunsApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  auditApi: {
    getDashboard: jest.fn(),
  },
  garakApi: {
    getReportSummary: jest.fn(),
  },
  spricoRunsApi: {
    summary: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)

describe('DashboardPage scanner coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(auditApi.getDashboard as jest.Mock).mockResolvedValue({
      totals: {
        run_count: 0,
        total_tests: 0,
        pass_count: 0,
        warn_count: 0,
        fail_count: 0,
        safe_count: 0,
        partial_count: 0,
        violation_count: 0,
        finding_count: 0,
        pass_rate: 0,
        critical_findings: 0,
        error_count: 0,
      },
      violations_by_category: [],
      risk_distribution: [],
      severity_distribution: [],
      heatmap: [],
      recent_runs: [],
    })
    ;(garakApi.getReportSummary as jest.Mock).mockResolvedValue({
      scanner_runs_total: 3,
      scanner_runs_by_status: [
        { status: 'completed_no_findings', count: 1 },
        { status: 'completed', count: 1 },
        { status: 'timeout', count: 1 },
      ],
      scanner_runs_by_target: [{ target: 'Safe Hospital Target', count: 2 }],
      scanner_runs_by_profile: [{ profile: 'quick_baseline', count: 2 }],
      scanner_runs_with_findings: 1,
      scanner_runs_with_no_findings: 1,
      high_critical_scanner_findings: 1,
      scanner_evidence_count: 2,
      artifacts_stored: 5,
    })
    ;(spricoRunsApi.summary as jest.Mock).mockResolvedValue({
      generated_at: '2026-04-28T00:00:00Z',
      total_runs: 7,
      by_run_type: [
        { label: 'audit_workstation', count: 1 },
        { label: 'garak_scan', count: 2 },
        { label: 'interactive_audit', count: 1 },
        { label: 'promptfoo_runtime', count: 1 },
        { label: 'red_campaign', count: 1 },
        { label: 'shield_check', count: 1 },
      ],
      by_source_page: [
        { label: 'audit', count: 1 },
        { label: 'benchmark-library', count: 1 },
        { label: 'chat', count: 1 },
        { label: 'garak-scanner', count: 2 },
        { label: 'red', count: 1 },
        { label: 'shield', count: 1 },
      ],
      by_status: [
        { label: 'completed', count: 3 },
        { label: 'completed_no_findings', count: 1 },
      ],
      by_final_verdict: [
        { label: 'FAIL', count: 2 },
        { label: 'PASS', count: 2 },
      ],
      coverage: {
        no_finding_runs: 1,
        runs_with_findings: 3,
        not_evaluated_runs: 1,
        evidence_total: 8,
        findings_total: 3,
        artifact_total: 5,
        targets_covered: 4,
      },
      recent_runs: [],
    })
  })

  it('shows unified run coverage and scanner totals including no-finding scanner runs', async () => {
    renderWithProvider(<DashboardPage onOpenRun={jest.fn()} />)

    expect(await screen.findByText('Unified Run Coverage')).toBeInTheDocument()
    expect(screen.getByText('All Run Records')).toBeInTheDocument()
    expect(screen.getByText('No-Finding Runs')).toBeInTheDocument()
    expect(screen.getByText('Runs By Type')).toBeInTheDocument()
    expect(screen.getByText('interactive_audit')).toBeInTheDocument()
    expect(screen.getByText('promptfoo_runtime')).toBeInTheDocument()
    expect(screen.getByText('shield_check')).toBeInTheDocument()
    expect(await screen.findByText('LLM Scanner Run Coverage')).toBeInTheDocument()
    expect(screen.getByText(/No-finding scans count toward coverage but do not create Findings/)).toBeInTheDocument()
    expect(screen.getByText('Scanner Runs Total')).toBeInTheDocument()
    expect(screen.getByText('Completed No Findings')).toBeInTheDocument()
    expect(screen.getAllByText('Runs With Findings').length).toBeGreaterThan(0)
    expect(screen.getByText('Scanner Runs By Status')).toBeInTheDocument()
    expect(screen.getByText('Scanner Runs By Target')).toBeInTheDocument()
    expect(screen.getByText('completed_no_findings')).toBeInTheDocument()
    expect(screen.getByText('timeout')).toBeInTheDocument()
    expect(screen.getByText('Safe Hospital Target')).toBeInTheDocument()
    expect(screen.getByText('quick_baseline')).toBeInTheDocument()
  })
})
