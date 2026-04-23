/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { render, screen, waitFor } from '@testing-library/react'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import EvidencePage from './EvidencePage'
import { spricoEvidenceApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  spricoEvidenceApi: {
    list: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)
}

describe('EvidencePage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    window.sessionStorage.clear()
  })

  it('loads a related interactive audit evidence record from session storage', async () => {
    window.sessionStorage.setItem('spricoEvidenceFindingId', 'interactive_audit:conversation-1:1:v2')
    ;(spricoEvidenceApi.list as jest.Mock).mockResolvedValue([
      {
        finding_id: 'interactive_audit:conversation-1:1:v2',
        created_at: '2026-04-21T00:00:00Z',
        engine_id: 'sprico_interactive_audit',
        engine_name: 'SpriCO Interactive Audit',
        engine_type: 'sprico_domain_signals',
        scan_id: 'conversation-1',
        conversation_id: 'conversation-1',
        evidence_type: 'interactive_audit_turn',
        final_verdict: 'FAIL',
        violation_risk: 'HIGH',
        data_sensitivity: 'HIGH',
        sprico_final_verdict: { verdict: 'FAIL' },
      },
      {
        finding_id: 'garak-scan-1',
        created_at: '2026-04-21T07:48:26.622898+00:00',
        engine: 'garak',
        engine_id: 'garak_detector',
        engine_name: 'garak',
        engine_type: 'evidence',
        scan_id: 'scan-1',
        evidence_type: 'scanner_evidence',
        final_verdict: 'WARN',
        violation_risk: 'MEDIUM',
        data_sensitivity: 'LOW',
        raw_result: {},
        raw_engine_result: {},
        matched_signals: [],
        policy_context: {},
      },
      {
        finding_id: 'shield-1',
        created_at: '2026-04-21T08:01:00+00:00',
        engine: 'sprico.shield',
        engine_id: 'sprico.shield',
        engine_name: 'sprico.shield',
        engine_type: 'evidence',
        scan_id: 'shield-session-1',
        evidence_type: 'shield_check',
        final_verdict: 'PASS',
        violation_risk: 'LOW',
        data_sensitivity: 'LOW',
        raw_result: {},
        raw_engine_result: {},
        matched_signals: [],
        policy_context: {},
      },
    ])

    renderWithProvider(<EvidencePage />)

    await waitFor(() => expect(spricoEvidenceApi.list).toHaveBeenCalledWith(expect.objectContaining({
      evidence_id: 'interactive_audit:conversation-1:1:v2',
    })))
    expect(await screen.findByText('Evidence Center')).toBeInTheDocument()
    expect(screen.getByText(/Evidence Center stores raw and normalized proof from audits/)).toBeInTheDocument()
    expect(screen.getAllByText('SpriCO Interactive Audit').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('option', { name: 'LLM Scanner Evidence' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('option', { name: 'SpriCO Shield Check' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('option', { name: 'Interactive Audit Turn' }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('interactive_audit_turn').length).toBeGreaterThan(0)
    expect(document.body).not.toHaveTextContent('2026-04-21T00:00:00Z')
    expect(screen.getAllByText('Evidence Source').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Source Type').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Final SpriCO Verdict').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Show Advanced Raw Evidence' })).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)
  })
})
