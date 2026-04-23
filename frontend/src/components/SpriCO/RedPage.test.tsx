/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import RedPage from './RedPage'
import { spricoPoliciesApi, spricoRedApi, targetsApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  spricoPoliciesApi: {
    list: jest.fn(),
  },
  spricoRedApi: {
    objectives: jest.fn(),
    createScan: jest.fn(),
    compare: jest.fn(),
  },
  targetsApi: {
    listTargets: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)
}

describe('RedPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(spricoRedApi.objectives as jest.Mock).mockResolvedValue([])
    ;(spricoPoliciesApi.list as jest.Mock).mockResolvedValue([
      {
        id: 'policy_hospital_strict_v1',
        name: 'Hospital Strict',
        mode: 'REDTEAM_STRICT',
        target_domain: 'hospital',
      },
    ])
    ;(targetsApi.listTargets as jest.Mock).mockResolvedValue({
      items: [
        {
          target_registry_name: 'OpenAIVectorStoreTarget::safe',
          display_name: 'Safe Hospital Target',
          target_type: 'OpenAIVectorStoreTarget',
          endpoint: 'https://api.openai.com/v1',
          model_name: 'gpt-4.1',
          target_specific_params: { target_domain: 'Healthcare' },
        },
        {
          target_registry_name: 'TextTarget::local',
          display_name: 'Text Only Target',
          target_type: 'TextTarget',
          endpoint: null,
          model_name: null,
          target_specific_params: {},
        },
      ],
      pagination: { limit: 200, has_more: false, next_cursor: null, prev_cursor: null },
    })
    ;(spricoRedApi.createScan as jest.Mock).mockResolvedValue({
      id: 'redscan-1',
      target_id: 'OpenAIVectorStoreTarget::safe',
      recon_context: {},
      objective_ids: [],
      policy_id: 'policy_hospital_strict_v1',
      engine: 'sprico_manual',
      status: 'completed',
      results: [],
      findings: [],
      risk: { worst_risk: 'LOW' },
      created_at: '2026-04-21T00:00:00Z',
      updated_at: '2026-04-21T00:00:00Z',
    })
  })

  it('distinguishes demo mock scans from permission-gated real target scans', async () => {
    const user = userEvent.setup()

    renderWithProvider(<RedPage />)

    await waitFor(() => expect(screen.getByText('Red Team Campaigns')).toBeInTheDocument())
    expect(screen.getByText(/Run objective-driven attack campaigns against a demo or real target/)).toBeInTheDocument()
    expect(screen.getByText(/Campaign outputs are scored by SpriCO domain policy/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Demo mock scan' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Real target scan' }))

    expect(await screen.findByRole('combobox', { name: 'Target' })).toBeInTheDocument()
    expect(screen.getByText(/I attest that I have permission/)).toBeInTheDocument()
    expect(screen.getByText(/Select a configured target before running a real target campaign/)).toBeInTheDocument()
    expect(screen.getByText('Evidence Engines')).toBeInTheDocument()
    expect(screen.getByText('LLM Scanner Evidence')).toBeInTheDocument()
    expect(screen.getByText(/Final Verdict Authority is locked to SpriCO PolicyDecisionEngine/)).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /DeepTeam metadata only/ })).toBeDisabled()
    expect(screen.getByRole('option', { name: /promptfoo metadata\/import only/ })).toBeDisabled()
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)
  })

  it('blocks real campaigns without target and without permission attestation', async () => {
    const user = userEvent.setup()

    renderWithProvider(<RedPage />)

    await waitFor(() => expect(screen.getByText('Red Team Campaigns')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Real target scan' }))
    const runButton = screen.getByRole('button', { name: 'Run Campaign' })
    expect(runButton).toBeDisabled()
    expect(screen.getByText(/Select a configured target before running a real target campaign/)).toBeInTheDocument()

    await user.selectOptions(await screen.findByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')
    expect(screen.getByText(/You must confirm authorization before running this scan/)).toBeInTheDocument()
    expect(runButton).toBeDisabled()

    await user.click(screen.getByLabelText(/I attest that I have permission/))
    expect(runButton).not.toBeDisabled()
  })

  it('does not fall back to mock when real target is invalid', async () => {
    const user = userEvent.setup()

    renderWithProvider(<RedPage />)

    await waitFor(() => expect(screen.getByText('Red Team Campaigns')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Real target scan' }))
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Target' }), 'TextTarget::local')

    expect(screen.getByText(/Selected target is missing an endpoint and cannot be used for real campaign execution/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run Campaign' })).toBeDisabled()
    expect(spricoRedApi.createScan).not.toHaveBeenCalled()
  })
})
