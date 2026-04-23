import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import ActivityHistoryPage from './ActivityHistoryPage'
import { activityApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  activityApi: {
    getHistory: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => (
  render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)
)

describe('ActivityHistoryPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(activityApi.getHistory as jest.Mock).mockResolvedValue({
      generated_at: '2026-04-23T10:00:00Z',
      scope_note: 'Activity History is a cross-workflow index.',
      categories: [
        {
          key: 'scanner_runs',
          title: 'Scanner Runs',
          description: 'LLM Vulnerability Scanner jobs, including completed no-finding and not-evaluated runs.',
          count: 2,
          navigation_view: 'scanner-reports',
          items: [
            {
              id: 'scan-1',
              title: 'Safe Hospital Target',
              subtitle: 'quick_baseline',
              status: 'Completed - no findings',
              created_at: '2026-04-23T09:00:00Z',
            },
          ],
        },
        {
          key: 'findings',
          title: 'Findings',
          description: 'Actionable SpriCO outcomes only.',
          count: 1,
          navigation_view: 'findings',
          items: [],
        },
      ],
    })
  })

  it('shows cross-workflow activity categories and navigates to source pages', async () => {
    const user = userEvent.setup()
    const onNavigate = jest.fn()

    renderWithProvider(<ActivityHistoryPage onNavigate={onNavigate} />)

    expect(await screen.findByText('Activity History')).toBeInTheDocument()
    expect(screen.getByText('Activity History is a cross-workflow index.')).toBeInTheDocument()
    expect(screen.getAllByText('Scanner Runs').length).toBeGreaterThan(0)
    expect(screen.getByText('Safe Hospital Target')).toBeInTheDocument()
    expect(screen.getByText('Completed - no findings')).toBeInTheDocument()
    expect(screen.getAllByText('Findings').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Open Scanner Runs' }))

    await waitFor(() => {
      expect(onNavigate).toHaveBeenCalledWith('scanner-reports')
    })
  })
})
