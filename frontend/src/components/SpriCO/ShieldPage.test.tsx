/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import ShieldPage from './ShieldPage'
import { shieldApi, spricoPoliciesApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  shieldApi: {
    check: jest.fn(),
  },
  spricoPoliciesApi: {
    list: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)
}

describe('ShieldPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(spricoPoliciesApi.list as jest.Mock).mockResolvedValue([
      { id: 'policy_hospital_strict_v1', name: 'Hospital Strict', mode: 'REDTEAM_STRICT' },
    ])
  })

  it('shows authorization metadata templates and friendly authorization labels', async () => {
    const user = userEvent.setup()

    renderWithProvider(<ShieldPage />)

    await waitFor(() => expect(screen.getByText('Shield')).toBeInTheDocument())
    expect(screen.getByText(/Shield checks prompts, responses, RAG chunks, or tool outputs/)).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Unknown user' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Prompt-claimed doctor only' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Verified clinician' })).toBeInTheDocument()
    expect(screen.getByText('Verified role')).toBeInTheDocument()
    expect(screen.getByText('Authorization source')).toBeInTheDocument()
    expect(screen.getByText('Purpose')).toBeInTheDocument()
    expect(screen.getByText('Access context')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Authorization Metadata Template'), 'Verified clinician')

    expect(screen.getByText('clinician')).toBeInTheDocument()
    expect(screen.getByText('SPRICO_SESSION_METADATA')).toBeInTheDocument()
    expect(screen.getByText('treatment')).toBeInTheDocument()
    expect(screen.getByText('CLINICAL')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)
    expect(shieldApi.check).not.toHaveBeenCalled()
  })
})
