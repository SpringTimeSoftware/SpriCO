/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { render, screen, waitFor } from '@testing-library/react'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import ExternalEngineMetadataPage from './ExternalEngineMetadataPage'
import { externalEnginesApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  externalEnginesApi: {
    getMatrix: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)
}

describe('ExternalEngineMetadataPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders external engines as evidence/attack sources with SpriCO locked as final authority', async () => {
    ;(externalEnginesApi.getMatrix as jest.Mock).mockResolvedValue({
      message: 'External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.',
      attack_engines: [
        {
          id: 'garak',
          name: 'garak',
          engine_type: 'attack',
          available: false,
          optional: true,
          metadata_only: false,
          final_verdict_capable: false,
          can_generate_attacks: true,
          can_generate_evidence: false,
          can_produce_final_verdict: false,
          license_id: 'Apache-2.0',
          source_file: 'third_party/garak/SOURCE.txt',
          install_hint: 'Install optional garak support with pip.',
        },
      ],
      evidence_engines: [
        {
          id: 'sprico_domain_signals',
          name: 'SpriCO domain signals',
          engine_type: 'evidence',
          available: true,
          optional: false,
          final_verdict_capable: false,
          can_generate_attacks: false,
          can_generate_evidence: true,
          can_produce_final_verdict: false,
        },
      ],
      optional_judge_models: [],
      domain_policy_pack_required: true,
      final_verdict_authority: {
        id: 'sprico_policy_decision_engine',
        name: 'SpriCO PolicyDecisionEngine',
        available: true,
        installed_version: 'native',
      },
      regulated_domain_lock: { locked: true },
      garak_status: { available: false, install_hint: 'Install optional garak support with pip.' },
      legal_components: {},
    })

    renderWithProvider(<ExternalEngineMetadataPage />)

    await waitFor(() => expect(screen.getByText('External Engine Metadata')).toBeInTheDocument())
    expect(screen.getByText(/External engines provide attack\/evidence signals/)).toBeInTheDocument()
    expect(screen.getAllByText('SpriCO PolicyDecisionEngine').length).toBeGreaterThan(0)
    expect(screen.getByText('Locked')).toBeInTheDocument()
    expect(screen.getByText('third_party/garak/SOURCE.txt')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)
  })
})
