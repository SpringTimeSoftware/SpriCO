/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import MainLayout from '../Layout/MainLayout'
import LandingPage from './LandingPage'
import { versionApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  versionApi: {
    getVersion: jest.fn(),
  },
}))

const mockedVersionApi = versionApi as jest.Mocked<typeof versionApi>

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)
}

describe('LandingPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockedVersionApi.getVersion.mockResolvedValue({ version: 'test' })
  })

  it('renders modern multi-domain platform framing and required architecture copy', () => {
    renderWithProvider(<LandingPage onNavigate={jest.fn()} />)

    expect(screen.getByRole('heading', {
      name: 'Secure, audit, and red-team AI systems with evidence-backed verdicts.',
    })).toBeInTheDocument()
    expect(screen.getByText('Domain-aware scoring for high-risk AI workflows')).toBeInTheDocument()
    expect(screen.getByText('Healthcare AI')).toBeInTheDocument()
    expect(screen.getByText('Legal AI')).toBeInTheDocument()
    expect(screen.getByText('HR AI')).toBeInTheDocument()
    expect(screen.getByText('Financial AI')).toBeInTheDocument()
    expect(screen.getByText('Enterprise AI')).toBeInTheDocument()
    expect(screen.getByText(/External engines provide attack\/evidence signals/)).toBeInTheDocument()
    expect(screen.getByText(/SpriCO produces the final policy-aware verdict/)).toBeInTheDocument()
  })

  it('renders the original AI-security animation and key signal nodes', () => {
    renderWithProvider(<LandingPage onNavigate={jest.fn()} />)

    expect(screen.getByTestId('landing-ai-animation')).toBeInTheDocument()
    expect(screen.getByTestId('privacy-signal')).toBeInTheDocument()
    expect(screen.getByTestId('prompt-injection-signal')).toBeInTheDocument()
    expect(screen.getByTestId('rag-poisoning-signal')).toBeInTheDocument()
    expect(screen.getByTestId('tool-misuse-signal')).toBeInTheDocument()
    expect(screen.getByTestId('policy-engine-node')).toBeInTheDocument()
    expect(screen.getByTestId('verdict-output-node')).toBeInTheDocument()
  })

  it('routes hero CTAs to existing currentView values', () => {
    const onNavigate = jest.fn()
    renderWithProvider(<LandingPage onNavigate={onNavigate} />)

    fireEvent.click(screen.getByRole('button', { name: 'Start Interactive Audit' }))
    expect(onNavigate).toHaveBeenCalledWith('chat')

    fireEvent.click(screen.getByRole('button', { name: 'Run LLM Vulnerability Scanner' }))
    expect(onNavigate).toHaveBeenCalledWith('garak-scanner')

    fireEvent.click(screen.getByRole('button', { name: 'Launch Red Team Campaign' }))
    expect(onNavigate).toHaveBeenCalledWith('red')

    fireEvent.click(screen.getByRole('button', { name: 'Review Evidence Center' }))
    expect(onNavigate).toHaveBeenCalledWith('evidence')
  })

  it('does not render old hospital-only or prohibited authority wording', () => {
    renderWithProvider(<LandingPage onNavigate={jest.fn()} />)
    const restrictedVendorPattern = new RegExp(['La', 'kera'].join(''), 'i')

    expect(document.body).not.toHaveTextContent(/Built for high-risk hospital AI workflows/i)
    expect(document.body).not.toHaveTextContent(restrictedVendorPattern)
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)
  })

  it('renders the landing shell with top navigation only and no compact left rail', async () => {
    const onNavigate = jest.fn()

    renderWithProvider(
      <MainLayout
        currentView="landing"
        onNavigate={onNavigate}
        onToggleTheme={jest.fn()}
        isDarkMode={false}
        brandingName="SpriCO AI Audit Platform"
      >
        <LandingPage onNavigate={onNavigate} />
      </MainLayout>
    )

    expect(screen.queryByLabelText('Quick access navigation')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Home' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Policies' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Polcies' })).not.toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/\bHx\b/)
    expect(document.body).not.toHaveTextContent(/\bSt\b/)
    expect(document.body).not.toHaveTextContent(/\bBm\b/)
    expect(document.body).not.toHaveTextContent(/\bFi\b/)
    expect(document.body).not.toHaveTextContent(/\bPv\b/)

    fireEvent.click(screen.getByRole('button', { name: 'Open Home' }))
    expect(onNavigate).toHaveBeenCalledWith('landing')

    await waitFor(() => expect(mockedVersionApi.getVersion).toHaveBeenCalled())
  })
})
