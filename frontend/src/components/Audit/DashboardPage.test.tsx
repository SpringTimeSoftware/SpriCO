import { render, screen } from '@testing-library/react'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import DashboardPage from './DashboardPage'
import { auditApi, garakApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  auditApi: {
    getDashboard: jest.fn(),
  },
  garakApi: {
    getReportSummary: jest.fn(),
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
  })

  it('shows scanner run totals including no-finding scanner runs', async () => {
    renderWithProvider(<DashboardPage onOpenRun={jest.fn()} />)

    expect(await screen.findByText('LLM Scanner Run Coverage')).toBeInTheDocument()
    expect(screen.getByText(/No-finding scans count toward coverage but do not create Findings/)).toBeInTheDocument()
    expect(screen.getByText('Scanner Runs Total')).toBeInTheDocument()
    expect(screen.getByText('Completed No Findings')).toBeInTheDocument()
    expect(screen.getByText('Runs With Findings')).toBeInTheDocument()
    expect(screen.getByText('Scanner Runs By Status')).toBeInTheDocument()
    expect(screen.getByText('Scanner Runs By Target')).toBeInTheDocument()
    expect(screen.getByText('completed_no_findings')).toBeInTheDocument()
    expect(screen.getByText('timeout')).toBeInTheDocument()
    expect(screen.getByText('Safe Hospital Target')).toBeInTheDocument()
    expect(screen.getByText('quick_baseline')).toBeInTheDocument()
  })
})
