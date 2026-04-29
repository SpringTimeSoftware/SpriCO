import { fireEvent, render, screen } from '@testing-library/react'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import FindingsPage from './FindingsPage'
import { spricoFindingsApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  spricoFindingsApi: {
    list: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)

describe('FindingsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(spricoFindingsApi.list as jest.Mock).mockResolvedValue([
      {
        id: 'finding-1',
        finding_id: 'finding-1',
        run_id: 'garak_scan:scan-1',
        evidence_ids: ['garak_scan:scan-1:evidence-1'],
        target_id: 'target-1',
        target_name: 'Target One',
        source_page: 'garak-scanner',
        engine_id: 'garak',
        engine_name: 'garak LLM Scanner',
        domain: 'hospital',
        policy_id: 'policy_hospital_strict_v1',
        policy_name: 'Hospital Strict',
        category: 'Prompt Injection',
        severity: 'HIGH',
        status: 'open',
        title: 'Scanner finding',
        description: 'Actionable scanner issue',
        root_cause: 'Detected unsafe leakage pattern.',
        remediation: 'Fix the issue and rerun the selected scope.',
        review_status: 'pending',
        created_at: '2026-04-28T00:00:00Z',
        updated_at: '2026-04-28T00:00:00Z',
        final_verdict: 'FAIL',
        violation_risk: 'HIGH',
        matched_signals: [{ signal_id: 'scanner.signal' }],
        policy_context: { policy_mode: 'REDTEAM_STRICT' },
        prompt_excerpt: 'Prompt excerpt',
        response_excerpt: 'Response excerpt',
        legacy_source_ref: { scan_id: 'scan-1' },
      },
    ])
  })

  it('shows actionable-only copy and finding detail with links', async () => {
    const onNavigate = jest.fn()
    renderWithProvider(<FindingsPage onNavigate={onNavigate} />)

    expect((await screen.findAllByText('Findings')).length).toBeGreaterThan(0)
    expect(screen.getByText(/Actionable issues only/)).toBeInTheDocument()
    expect(screen.getByText('Finding Coverage')).toBeInTheDocument()
    expect(screen.getAllByText('Scanner finding').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Open Linked Evidence' }))
    expect(onNavigate).toHaveBeenCalledWith('evidence')
  })
})
