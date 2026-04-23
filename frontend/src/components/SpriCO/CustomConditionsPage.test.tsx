/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { render, screen, waitFor } from '@testing-library/react'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import CustomConditionsPage from './CustomConditionsPage'
import { spricoConditionsApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  spricoConditionsApi: {
    types: jest.fn(),
    list: jest.fn(),
    create: jest.fn(),
    simulate: jest.fn(),
    addTest: jest.fn(),
    approve: jest.fn(),
    activate: jest.fn(),
    retire: jest.fn(),
    rollback: jest.fn(),
    versions: jest.fn(),
    auditHistory: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)
}

const notFoundError = {
  isAxiosError: true,
  response: {
    status: 404,
    data: { detail: 'Not Found' },
  },
}

describe('CustomConditionsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('shows a no-conditions empty state when the service is available', async () => {
    ;(spricoConditionsApi.types as jest.Mock).mockResolvedValue({
      allowed_condition_types: ['keyword_match', 'regex_match'],
      final_verdict_authority: 'sprico_policy_decision_engine',
      code_execution_allowed: false,
    })
    ;(spricoConditionsApi.list as jest.Mock).mockResolvedValue([])

    renderWithProvider(<CustomConditionsPage />)

    expect(await screen.findByText('Custom Conditions')).toBeInTheDocument()
    expect(screen.getByText(/Custom Conditions are safe declarative signal rules/)).toBeInTheDocument()
    expect(screen.getByText('No custom conditions created yet.')).toBeInTheDocument()
    expect(screen.getAllByText(/keyword_match/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/llm_judge_condition/).length).toBeGreaterThan(0)
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)
  })

  it('shows a service unavailable message separately from the empty state on 404', async () => {
    ;(spricoConditionsApi.types as jest.Mock).mockRejectedValue(notFoundError)
    ;(spricoConditionsApi.list as jest.Mock).mockResolvedValue([])

    renderWithProvider(<CustomConditionsPage />)

    expect(await screen.findByText('Custom Conditions')).toBeInTheDocument()
    expect(screen.getByText(/Custom Conditions service is unavailable/)).toBeInTheDocument()
    expect(screen.queryByText('No custom conditions created yet.')).not.toBeInTheDocument()
  })
})
