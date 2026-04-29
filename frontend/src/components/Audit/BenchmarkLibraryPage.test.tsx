/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { render, screen, waitFor } from '@testing-library/react'
import BenchmarkLibraryPage from './BenchmarkLibraryPage'
import { auditApi, targetsApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  auditApi: {
    getBenchmarkLibrary: jest.fn(),
    compareBenchmarkScenario: jest.fn(),
    importFlipAttackBenchmark: jest.fn(),
    replayBenchmarkScenario: jest.fn(),
  },
  targetsApi: {
    listTargets: jest.fn(),
  },
}))

describe('BenchmarkLibraryPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(targetsApi.listTargets as jest.Mock).mockResolvedValue({ items: [] })
    ;(auditApi.getBenchmarkLibrary as jest.Mock).mockResolvedValue({
      taxonomy: [],
      scenarios: [],
      media: [],
    })
    ;(auditApi.compareBenchmarkScenario as jest.Mock).mockResolvedValue({
      delta: 'No replay selected.',
      public_model_result: {},
      client_target_results: [],
    })
  })

  it('explains reusable benchmark tests and hospital examples separately from Evidence Center results', async () => {
    render(<BenchmarkLibraryPage />)

    expect(await screen.findByText('Benchmark Library')).toBeInTheDocument()
    await waitFor(() => expect(auditApi.getBenchmarkLibrary).toHaveBeenCalled())
    expect(screen.getAllByText(/Benchmark Library stores reusable test definitions\./).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Evidence Center stores proof after execution\./).length).toBeGreaterThan(0)
    expect(screen.getByText('AuditSpec is SpriCO-native YAML/JSON for repeatable suites, assertions, and comparisons.')).toBeInTheDocument()
    expect(screen.getByText('Promptfoo Runtime optionally runs promptfoo plugins, strategies, and custom policies. Results are imported as evidence. SpriCO PolicyDecisionEngine remains final verdict authority.')).toBeInTheDocument()
    expect(screen.getByText('Patient ID + diagnosis leakage')).toBeInTheDocument()
    expect(screen.getByText('Patient ID + location follow-up')).toBeInTheDocument()
    expect(screen.getByText('Prompt-claimed doctor/admin/auditor')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)
  })
})
