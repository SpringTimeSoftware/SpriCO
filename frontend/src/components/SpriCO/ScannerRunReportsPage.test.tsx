import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import ScannerRunReportsPage from './ScannerRunReportsPage'
import { garakApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  garakApi: {
    listReports: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)

describe('ScannerRunReportsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(garakApi.listReports as jest.Mock).mockResolvedValue({
      reports: [
        {
          scan_id: 'scan-no-findings',
          status: 'completed_no_findings',
          evaluation_status: 'evaluated',
          target_name: 'Safe Hospital Target',
          target_type: 'OpenAIVectorStoreTarget',
          policy_id: 'policy_hospital_strict_v1',
          policy_name: 'Hospital Strict',
          scan_profile: 'quick_baseline',
          vulnerability_categories: ['Privacy & Data Leakage'],
          resolved_probes_count: 1,
          resolved_probes: ['probe.One'],
          skipped_probes_count: 1,
          skipped_probes: ['probe.Missing'],
          skipped_probe_details: [{ name: 'probe.Missing', reason: 'Reason not recorded.' }],
          detectors_count: 0,
          detectors: [],
          buffs_count: 0,
          buffs: [],
          default_generations: 1,
          timeout_seconds: 180,
          evidence_count: 0,
          findings_count: 0,
          artifact_count: 1,
          final_sprico_verdict: 'PASS',
          violation_risk: 'LOW',
          sprico_final_verdict: { verdict: 'PASS', violation_risk: 'LOW' },
          aggregate: { final_verdict: 'PASS', worst_risk: 'LOW' },
          garak: {},
          raw_findings: [],
          scanner_evidence: [],
          signals: [],
          findings: [],
          artifacts: [{ artifact_type: 'command_metadata', name: 'command.json' }],
          config: { policy_context: { selected_target_domain: 'healthcare', policy_domain: 'hospital' } },
        },
        {
          scan_id: 'scan-finding',
          status: 'completed',
          evaluation_status: 'evaluated',
          target_name: 'Finding Target',
          scan_profile: 'deep_llm_security',
          vulnerability_categories: ['Privacy & Data Leakage', 'Prompt Injection & Jailbreaks'],
          resolved_probes_count: 2,
          resolved_probes: ['probe.One', 'probe.Two'],
          evidence_count: 1,
          findings_count: 1,
          artifact_count: 2,
          final_sprico_verdict: 'FAIL',
          violation_risk: 'HIGH',
          sprico_final_verdict: { verdict: 'FAIL', violation_risk: 'HIGH' },
          aggregate: { final_verdict: 'FAIL', worst_risk: 'HIGH' },
          garak: {},
          raw_findings: [],
          scanner_evidence: [{ probe: 'probe.One', detector: 'detector.One', scanner_result: { hit: true } }],
          signals: [{ category: 'data_leakage' }],
          findings: [{ finding_id: 'finding-1', scan_id: 'scan-finding' }],
          artifacts: [{}, {}],
          config: { policy_context: { selected_target_domain: 'healthcare', policy_domain: 'hospital' } },
        },
      ],
      summary: {
        scanner_runs_total: 2,
        scanner_runs_by_status: [
          { status: 'completed', count: 1 },
          { status: 'completed_no_findings', count: 1 },
        ],
        scanner_runs_by_target: [],
        scanner_runs_by_profile: [],
        scanner_runs_with_findings: 1,
        scanner_runs_with_no_findings: 1,
        high_critical_scanner_findings: 1,
        scanner_evidence_count: 1,
        artifacts_stored: 3,
      },
    })
  })

  it('lists completed no-finding scanner runs and opens a detailed report', async () => {
    renderWithProvider(<ScannerRunReportsPage />)

    expect(await screen.findByText('Scanner Run Reports')).toBeInTheDocument()
    expect(screen.getByText(/including completed no-finding/)).toBeInTheDocument()
    expect(screen.getByText('Scanner Runs Total')).toBeInTheDocument()
    expect(screen.getAllByText('2').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Safe Hospital Target').length).toBeGreaterThan(0)
    expect(screen.getByText('completed_no_findings')).toBeInTheDocument()
    expect(screen.getAllByText(/Completed - no findings/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/No actionable scanner evidence was produced/).length).toBeGreaterThan(0)
    expect(screen.getByText(/No Findings were created because SpriCO did not identify an actionable issue/)).toBeInTheDocument()
    expect(screen.getByText('Timeout Seconds')).toBeInTheDocument()
    expect(screen.getByText('180')).toBeInTheDocument()
    expect(screen.getByText(/garak probe modules successfully selected for this run/)).toBeInTheDocument()
    expect(screen.getByText(/probes requested by profile but skipped/)).toBeInTheDocument()
    expect(screen.getByText(/No explicit detectors were configured or captured for this run/)).toBeInTheDocument()
    expect(screen.getByText('Reason not recorded.')).toBeInTheDocument()
  })

  it('shows findings action only for reports with actionable findings', async () => {
    const user = userEvent.setup()
    const onNavigate = jest.fn()
    renderWithProvider(<ScannerRunReportsPage onNavigate={onNavigate} />)

    await screen.findByText('Scanner Run Reports')
    expect(screen.getAllByText('Safe Hospital Target').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Open Findings for this scan' })).not.toBeInTheDocument()

    const table = screen.getByText('Scanner Runs').closest('.sprico-panel') as HTMLElement
    await user.click(within(table).getByText('Finding Target'))

    await user.click(screen.getByRole('button', { name: 'Open Findings for this scan' }))
    expect(onNavigate).toHaveBeenCalledWith('findings')
  })
})
