/**
 * Copyright (c) Microsoft Corporation.
 * Licensed under the MIT license.
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import GarakScannerPage from './GarakScannerPage'
import { garakApi, judgeApi, spricoPoliciesApi, targetsApi } from '../../services/api'

jest.mock('../../services/api', () => ({
  garakApi: {
    getStatus: jest.fn(),
    getPlugins: jest.fn(),
    listScans: jest.fn(),
    listReports: jest.fn(),
    createScan: jest.fn(),
  },
  judgeApi: {
    getStatus: jest.fn(),
  },
  spricoPoliciesApi: {
    list: jest.fn(),
  },
  targetsApi: {
    listTargets: jest.fn(),
  },
}))

const renderWithProvider = (ui: React.ReactElement) => {
  return render(<FluentProvider theme={webLightTheme}>{ui}</FluentProvider>)
}

const reportsResponse = (reports: Array<Record<string, unknown>>) => ({
  reports,
  summary: {
    scanner_runs_total: reports.length,
    scanner_runs_by_status: [],
    scanner_runs_by_target: [],
    scanner_runs_by_profile: [],
    scanner_runs_with_findings: reports.filter(item => Number(item.findings_count ?? 0) > 0).length,
    scanner_runs_with_no_findings: reports.filter(item => item.status === 'completed_no_findings').length,
    high_critical_scanner_findings: 0,
    scanner_evidence_count: reports.reduce((total, item) => total + Number(item.evidence_count ?? 0), 0),
    artifacts_stored: reports.reduce((total, item) => total + (Array.isArray(item.artifacts) ? item.artifacts.length : Number(item.artifact_count ?? 0)), 0),
  },
})

describe('GarakScannerPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(garakApi.getStatus as jest.Mock).mockResolvedValue({
      available: false,
      version: null,
      python: 'C:\\Python312\\python.exe',
      executable: 'C:\\Private\\garak.exe',
      import_error: 'No module named garak',
      cli_error: null,
      install_hint: 'python -m pip install -e ".[garak]"',
    })
    ;(garakApi.getPlugins as jest.Mock).mockResolvedValue({ plugins: { probes: [], detectors: [], generators: [] } })
    ;(garakApi.listScans as jest.Mock).mockResolvedValue([])
    ;(garakApi.listReports as jest.Mock).mockResolvedValue(reportsResponse([]))
    ;(garakApi.createScan as jest.Mock).mockResolvedValue({
      scan_id: 'scan-1',
      status: 'unavailable',
      garak: {},
      raw_findings: [],
      scanner_evidence: [],
      signals: [],
      findings: [],
      aggregate: { final_verdict: 'NEEDS_REVIEW' },
      sprico_final_verdict: { verdict: 'NEEDS_REVIEW', violation_risk: 'MEDIUM' },
      artifacts: [],
    })
    ;(judgeApi.getStatus as jest.Mock).mockResolvedValue({
      enabled: false,
      configured: false,
      final_verdict_authority: 'sprico_policy_decision_engine',
      providers: [
        {
          id: 'openai',
          label: 'OpenAI Judge',
          configured: false,
          enabled: false,
          enabled_by_default: false,
          final_verdict_capable: false,
          supports_redaction: true,
          allowed_modes: ['disabled', 'redacted'],
          blocked_for_domains_by_default: ['healthcare', 'hospital'],
          configure_hint: 'Set backend environment variables.',
        },
      ],
    })
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
      ],
      pagination: { limit: 200, has_more: false, next_cursor: null, prev_cursor: null },
    })
  })

  it('shows target selector and hides executable path until advanced diagnostics are opened', async () => {
    const user = userEvent.setup()

    renderWithProvider(<GarakScannerPage onNavigate={jest.fn()} />)

    expect(await screen.findByText('LLM Vulnerability Scanner')).toBeInTheDocument()
    expect(screen.getByText(/Run broad LLM vulnerability scans against a target/)).toBeInTheDocument()
    expect(screen.getAllByText('Scanner Engine Status').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Not installed').length).toBeGreaterThan(0)
    expect(screen.getByText(/Optional garak scanner engine is not installed/)).toBeInTheDocument()
    expect(await screen.findByRole('combobox', { name: 'Target' })).toBeInTheDocument()
    expect(screen.getAllByText('Active').length).toBeGreaterThan(0)
    expect(screen.getByText('Scanner Evidence')).toBeInTheDocument()
    expect(screen.getByText('Optional / Disabled')).toBeInTheDocument()
    expect(screen.getAllByText('Not configured').length).toBeGreaterThan(0)
    expect(screen.getByText('SpriCO Domain Signals')).toBeInTheDocument()
    expect(screen.getByText('Applies the selected policy/domain pack after scanner responses. This is required for final SpriCO verdicts.')).toBeInTheDocument()
    expect(screen.getByText('garak Detector Evidence')).toBeInTheDocument()
    expect(screen.getByText('Runs garak probes and detector checks. Produces scanner evidence only. It cannot override the final SpriCO verdict.')).toBeInTheDocument()
    expect(screen.getByText('OpenAI Judge Evidence')).toBeInTheDocument()
    expect(screen.getByText(/Optional model-based review for ambiguous cases. Disabled by default/)).toBeInTheDocument()
    expect(screen.getByText('Configure Judge Models')).toBeInTheDocument()
    expect(screen.queryByLabelText('Enable OpenAI Judge for this scan')).not.toBeInTheDocument()
    expect(screen.getByText('PyRIT Scorers')).toBeInTheDocument()
    expect(screen.getByText('PyRIT scorer evidence is not wired for this scanner workflow. Interactive Audit and structured audits use PyRIT targets/memory, but this scanner path is garak-based.')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('C:\\Private\\garak.exe')
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)

    await user.click(screen.getByRole('button', { name: 'Show Advanced Diagnostics' }))

    await waitFor(() => expect(screen.getByText('Backend Python Environment')).toBeInTheDocument())
    expect(screen.getByText('C:\\Private\\garak.exe')).toBeInTheDocument()
  })

  it('blocks scanner runs without target and without permission attestation', async () => {
    const user = userEvent.setup()

    renderWithProvider(<GarakScannerPage />)

    const runButton = await screen.findByRole('button', { name: 'Run Vulnerability Scan' })
    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    expect(runButton).toBeDisabled()
    expect(screen.getByText(/Select a configured target before running a vulnerability scan/)).toBeInTheDocument()

    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')
    expect(screen.getByText(/You must confirm authorization before running this scan/)).toBeInTheDocument()
    expect(runButton).toBeDisabled()

    await user.click(screen.getByLabelText(/I attest that I have authorization/))
    expect(runButton).not.toBeDisabled()
  })

  it('shows configured OpenAI Judge controls as evidence only and disabled by default', async () => {
    const user = userEvent.setup()
    ;(judgeApi.getStatus as jest.Mock).mockResolvedValue({
      enabled: true,
      configured: true,
      final_verdict_authority: 'sprico_policy_decision_engine',
      providers: [
        {
          id: 'openai',
          label: 'OpenAI Judge',
          configured: true,
          enabled: true,
          enabled_by_default: false,
          final_verdict_capable: false,
          supports_redaction: true,
          allowed_modes: ['disabled', 'redacted'],
          blocked_for_domains_by_default: ['healthcare', 'hospital'],
          configure_hint: 'Configured in backend environment.',
        },
      ],
    })

    renderWithProvider(<GarakScannerPage />)

    expect(await screen.findByText('OpenAI Judge Evidence')).toBeInTheDocument()
    expect(screen.getByText('Configured, disabled by default')).toBeInTheDocument()
    expect(screen.getAllByText(/OpenAI Judge provides evidence only. SpriCO PolicyDecisionEngine remains final verdict authority/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Healthcare\/PHI content should not be sent to an external judge/)).toBeInTheDocument()
    expect(screen.getByLabelText('Enable OpenAI Judge for this scan')).not.toBeChecked()
    expect(document.body).not.toHaveTextContent(/api key/i)

    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')
    await user.click(screen.getByLabelText(/I attest that I have authorization/))
    await user.click(screen.getByLabelText('Enable OpenAI Judge for this scan'))
    await user.click(screen.getByRole('button', { name: 'Run Vulnerability Scan' }))

    await waitFor(() => expect(garakApi.createScan).toHaveBeenCalledWith(expect.objectContaining({
      judge_settings: {
        enabled: true,
        provider: 'openai',
        mode: 'redacted',
        judge_only_ambiguous: true,
      },
    })))
  })

  it('continues without judge settings when an older backend lacks judge status', async () => {
    const user = userEvent.setup()
    ;(judgeApi.getStatus as jest.Mock).mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404, data: { detail: 'Not Found' } },
    })

    renderWithProvider(<GarakScannerPage />)

    expect(await screen.findByText('LLM Vulnerability Scanner')).toBeInTheDocument()
    expect(screen.getByText('OpenAI Judge Evidence')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')
    await user.click(screen.getByLabelText(/I attest that I have authorization/))
    await user.click(screen.getByRole('button', { name: 'Run Vulnerability Scan' }))

    await waitFor(() => expect(garakApi.createScan).toHaveBeenCalledWith(expect.objectContaining({
      target_id: 'OpenAIVectorStoreTarget::safe',
      permission_attestation: true,
    })))
    expect(garakApi.createScan).toHaveBeenCalledWith(expect.not.objectContaining({
      judge_settings: expect.anything(),
      cross_domain_override: false,
    }))
  })

  it('warns when Deep LLM Security is limited to one selected category', async () => {
    const user = userEvent.setup()

    renderWithProvider(<GarakScannerPage />)

    expect(await screen.findByText('LLM Vulnerability Scanner')).toBeInTheDocument()
    await user.selectOptions(screen.getByRole('combobox', { name: /Scan Profile/ }), 'deep_llm_security')
    await user.click(screen.getByLabelText('Prompt Injection & Jailbreaks'))

    expect(screen.getByText('Deep LLM Security profile selected, but only 1 category is enabled. This is not a full deep scan.')).toBeInTheDocument()
    expect(screen.getByText('Category-limited run')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Select all categories for this profile' }))

    expect(screen.getByText('Full profile run')).toBeInTheDocument()
  })

  it('runs with allowlisted scan profile fields and separates scanner result from final verdict', async () => {
    const user = userEvent.setup()
    ;(garakApi.listReports as jest.Mock).mockResolvedValue(reportsResponse([
      {
        scan_id: 'scan-history-1',
        status: 'completed',
        target_id: 'OpenAIVectorStoreTarget::safe',
        target_name: 'Safe Hospital Target',
        scan_profile: 'quick_baseline',
        garak: {},
        raw_findings: [],
        scanner_evidence: [
          {
            probe: 'leakreplay.GuardianComplete',
            detector: 'leakreplay.StartsWith',
            scanner_result: { hit: true },
            prompt: 'synthetic prompt',
            output: 'synthetic output',
          },
        ],
        signals: [],
        findings: [],
        sprico_final_verdict: { verdict: 'FAIL', violation_risk: 'HIGH' },
        aggregate: { final_verdict: 'FAIL', worst_risk: 'HIGH', evidence_count: 1, findings_count: 1 },
        artifacts: [],
      },
    ]))
    ;(garakApi.createScan as jest.Mock).mockResolvedValueOnce({
      scan_id: 'scan-new',
      status: 'completed',
      target_id: 'OpenAIVectorStoreTarget::safe',
      target_name: 'Safe Hospital Target',
      scan_profile: 'quick_baseline',
      garak: {},
      raw_findings: [],
      scanner_evidence: [
        {
          probe: 'leakreplay.GuardianComplete',
          detector: 'leakreplay.StartsWith',
          scanner_result: { hit: true },
          prompt: 'synthetic prompt',
          output: 'synthetic output',
        },
      ],
      signals: [],
      findings: [],
      sprico_final_verdict: { verdict: 'FAIL', violation_risk: 'HIGH' },
      aggregate: { final_verdict: 'FAIL', worst_risk: 'HIGH', evidence_count: 1, findings_count: 1 },
      artifacts: [],
    })

    renderWithProvider(<GarakScannerPage />)

    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')
    await user.click(screen.getByLabelText(/I attest that I have authorization/))
    await user.click(screen.getByRole('button', { name: 'Run Vulnerability Scan' }))

    await waitFor(() => expect(garakApi.createScan).toHaveBeenCalledWith(expect.objectContaining({
      target_id: 'OpenAIVectorStoreTarget::safe',
      policy_id: 'policy_hospital_strict_v1',
      scan_profile: 'quick_baseline',
      vulnerability_categories: expect.arrayContaining(['Privacy & Data Leakage']),
      permission_attestation: true,
    })))
    expect(garakApi.createScan).toHaveBeenCalledWith(expect.not.objectContaining({
      raw_cli_args: expect.anything(),
    }))
    expect(await screen.findByText('Scanner Result')).toBeInTheDocument()
    expect(screen.getAllByText('Final SpriCO Verdict').length).toBeGreaterThan(0)
    expect(document.body).not.toHaveTextContent(/garak final verdict/i)
    expect(document.body).not.toHaveTextContent(/Choose final scoring engine/i)
  })

  it('shows structured backend validation details and next steps instead of generic validation text', async () => {
    const user = userEvent.setup()
    ;(garakApi.createScan as jest.Mock).mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 400,
        data: {
          error: 'validation_failed',
          message: 'Cannot start scanner run.',
          details: [
            {
              field: 'target_id',
              reason: 'Selected target is missing scanner endpoint mapping.',
            },
          ],
          next_steps: ['Configure scanner-compatible endpoint mapping in Target Configuration.'],
        },
      },
    })
    const onNavigate = jest.fn()

    renderWithProvider(<GarakScannerPage onNavigate={onNavigate} />)

    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')
    await user.click(screen.getByLabelText(/I attest that I have authorization/))
    await user.click(screen.getByRole('button', { name: 'Run Vulnerability Scan' }))

    expect(await screen.findByText('Cannot start scanner run.')).toBeInTheDocument()
    expect(screen.getByText('target_id')).toBeInTheDocument()
    expect(screen.getByText('Selected target is missing scanner endpoint mapping.')).toBeInTheDocument()
    expect(screen.getByText('Configure scanner-compatible endpoint mapping in Target Configuration.')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('Request validation failed')

    await user.click(screen.getByRole('button', { name: 'Open Target Configuration' }))
    expect(onNavigate).toHaveBeenCalledWith('config')
  })

  it('normalizes stale backend cross-domain field errors into an actionable scanner message', async () => {
    const user = userEvent.setup()
    ;(garakApi.createScan as jest.Mock).mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 422,
        data: {
          detail: [
            {
              type: 'extra_forbidden',
              loc: ['body', 'cross_domain_override'],
              msg: 'Extra inputs are not permitted',
            },
          ],
        },
      },
    })

    renderWithProvider(<GarakScannerPage />)

    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')
    await user.click(screen.getByLabelText(/I attest that I have authorization/))
    await user.click(screen.getByRole('button', { name: 'Run Vulnerability Scan' }))

    expect(await screen.findByText(/unsupported field: cross_domain_override/)).toBeInTheDocument()
    expect(screen.getByText('body.cross_domain_override')).toBeInTheDocument()
    expect(screen.getByText('Extra inputs are not permitted')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/^Request validation failed$/)
  })

  it('shows timeout results as not evaluated and suppresses legacy PASS LOW values', async () => {
    ;(garakApi.listReports as jest.Mock).mockResolvedValue(reportsResponse([
      {
        scan_id: 'timeout-scan',
        status: 'timeout',
        evaluation_status: 'not_evaluated',
        target_id: 'mock_hospital_target',
        target_name: 'mock_hospital_target',
        policy_id: 'policy_hospital_strict_v1',
        scan_profile: 'quick_baseline',
        garak: {},
        raw_findings: [],
        scanner_evidence: [],
        signals: [],
        findings: [],
        sprico_final_verdict: { verdict: 'PASS', violation_risk: 'LOW' },
        aggregate: { final_verdict: 'PASS', worst_risk: 'LOW', evidence_count: 0, findings_count: 0 },
        artifacts: [],
      },
    ]))

    renderWithProvider(<GarakScannerPage />)

    expect(await screen.findByText(/Scanner timed out before producing usable evidence/)).toBeInTheDocument()
    expect(screen.getByText(/This run was not evaluated as safe/)).toBeInTheDocument()
    expect(screen.getAllByText('NOT_EVALUATED').length).toBeGreaterThan(0)
    expect(screen.getAllByText('NOT_AVAILABLE').length).toBeGreaterThan(0)
    expect(screen.getByText(/No evidence produced because the scanner did not complete/)).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/Final SpriCO Verdict\s*PASS/i)
    expect(document.body).not.toHaveTextContent(/Violation Risk\s*LOW/i)
  })

  it('explains completed scans with no actionable findings and summarizes artifacts', async () => {
    ;(garakApi.listReports as jest.Mock).mockResolvedValue(reportsResponse([
      {
        scan_id: 'no-findings-scan',
        status: 'completed_no_findings',
        evaluation_status: 'evaluated',
        target_id: 'OpenAIVectorStoreTarget::safe',
        target_name: 'Safe Hospital Target',
        policy_id: 'policy_hospital_strict_v1',
        scan_profile: 'deep_llm_security',
        vulnerability_categories: ['Privacy & Data Leakage'],
        started_at: '2026-04-21T07:48:20.000Z',
        finished_at: '2026-04-21T07:48:26.000Z',
        profile_resolution: {
          probes: ['probe.One', 'probe.Two'],
          detectors: ['detector.One'],
          buffs: [],
          skipped: { probes: ['probe.Missing'] },
          default_generations: 2,
          timeout_seconds: 600,
        },
        garak: {},
        raw_findings: [],
        scanner_evidence: [],
        signals: [],
        findings: [],
        evidence_count: 0,
        findings_count: 0,
        sprico_final_verdict: { verdict: 'PASS', violation_risk: 'LOW' },
        aggregate: { final_verdict: 'PASS', worst_risk: 'LOW', evidence_count: 0, findings_count: 0 },
        artifacts: [
          { artifact_type: 'command_metadata', name: 'command.json', size: 50, path: 'C:\\private\\command.json' },
          { artifact_type: 'scan_config', name: 'config.json', size: 80, path: 'C:\\private\\config.json' },
          { artifact_type: 'stdout', name: 'stdout.txt', size: 10 },
          { artifact_type: 'stderr', name: 'stderr.txt', size: 0 },
          { artifact_type: 'exit_code', name: 'exit_code.txt', size: 1 },
          { artifact_type: 'report', name: 'garak_report.jsonl', size: 100 },
        ],
      },
    ]))

    renderWithProvider(<GarakScannerPage />)

    expect(await screen.findByText('Scan Summary')).toBeInTheDocument()
    expect(screen.getByText('Scope Tested')).toBeInTheDocument()
    expect(screen.getByText('Probe Coverage')).toBeInTheDocument()
    expect(screen.getByText('Evidence & Findings')).toBeInTheDocument()
    expect(await screen.findByText(/Scan completed with no actionable findings/)).toBeInTheDocument()
    expect(screen.getByText(/It does not prove the target is safe against all attacks/)).toBeInTheDocument()
    expect(screen.getByText('PASS for this scan run')).toBeInTheDocument()
    expect(screen.getByText(/No actionable findings for selected scope/)).toBeInTheDocument()
    expect(screen.getByText('No Evidence Center records were created because no actionable scanner evidence was produced.')).toBeInTheDocument()
    expect(screen.getByText('No Findings were created because SpriCO did not identify an actionable issue in this scan.')).toBeInTheDocument()
    expect(screen.getByText(/Findings are only created for actionable issues/)).toBeInTheDocument()
    expect(screen.getByText('Category-limited scan: Deep LLM Security profile was selected, but only 1 category was enabled.')).toBeInTheDocument()
    expect(screen.getAllByText('Resolved Probes').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Skipped Probes').length).toBeGreaterThan(0)
    expect(screen.getByText('probe.One')).toBeInTheDocument()
    expect(screen.getByText('probe.Two')).toBeInTheDocument()
    expect(screen.getByText('probe.Missing')).toBeInTheDocument()
    expect(screen.getByText('detector.One')).toBeInTheDocument()
    expect(screen.getByText('Artifact Summary')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open Findings for this scan' })).not.toBeInTheDocument()

    const artifactSummary = screen.getByText('Artifact Summary').closest('.sprico-kpi')
    expect(artifactSummary).not.toBeNull()
    const artifactScope = within(artifactSummary as HTMLElement)
    expect(artifactScope.getByText('command metadata')).toBeInTheDocument()
    expect(artifactScope.getByText('scan config')).toBeInTheDocument()
    expect(artifactScope.getByText('stdout')).toBeInTheDocument()
    expect(artifactScope.getByText('stderr')).toBeInTheDocument()
    expect(artifactScope.getByText('exit code')).toBeInTheDocument()
    expect(artifactScope.getByText('report.jsonl')).toBeInTheDocument()
    expect(artifactScope.getByText('hitlog.jsonl')).toBeInTheDocument()
    expect(artifactScope.getByText('html report')).toBeInTheDocument()
    expect(artifactScope.getAllByText('saved').length).toBeGreaterThanOrEqual(5)
    expect(artifactScope.getByText('empty')).toBeInTheDocument()
    expect(artifactScope.getAllByText('not produced').length).toBeGreaterThanOrEqual(2)
    expect(document.body).not.toHaveTextContent('C:\\private\\command.json')
    expect(document.body).not.toHaveTextContent('C:\\private\\config.json')
    expect(screen.getByRole('button', { name: 'Show Advanced Raw Evidence — for administrators and debugging.' })).toBeInTheDocument()
    expect(screen.queryByTestId('advanced-raw-evidence-panel')).not.toBeInTheDocument()
  })

  it('shows a findings link when a scan has actionable findings', async () => {
    const user = userEvent.setup()
    const onNavigate = jest.fn()
    ;(garakApi.listReports as jest.Mock).mockResolvedValue(reportsResponse([
      {
        scan_id: 'finding-scan',
        status: 'completed',
        evaluation_status: 'evaluated',
        target_id: 'OpenAIVectorStoreTarget::safe',
        target_name: 'Safe Hospital Target',
        target_type: 'OpenAIVectorStoreTarget',
        policy_id: 'policy_hospital_strict_v1',
        scan_profile: 'quick_baseline',
        garak: {},
        raw_findings: [],
        scanner_evidence: [{ probe: 'probe.One', detector: 'detector.One', scanner_result: { hit: true } }],
        signals: [{ category: 'data_leakage' }],
        findings: [{ finding_id: 'garak_finding_finding-scan_1', scan_id: 'finding-scan' }],
        evidence_count: 1,
        findings_count: 1,
        sprico_final_verdict: { verdict: 'FAIL', violation_risk: 'HIGH' },
        aggregate: { final_verdict: 'FAIL', worst_risk: 'HIGH', evidence_count: 1, findings_count: 1 },
        artifacts: [],
      },
    ]))

    renderWithProvider(<GarakScannerPage onNavigate={onNavigate} />)

    const button = await screen.findByRole('button', { name: 'Open Findings for this scan' })
    await user.click(button)

    expect(onNavigate).toHaveBeenCalledWith('findings')
  })

  it('shows failed results as not evaluated', async () => {
    ;(garakApi.listReports as jest.Mock).mockResolvedValue(reportsResponse([
      {
        scan_id: 'failed-scan',
        status: 'failed',
        evaluation_status: 'not_evaluated',
        target_id: 'OpenAIVectorStoreTarget::safe',
        target_name: 'Safe Hospital Target',
        policy_id: 'policy_hospital_strict_v1',
        scan_profile: 'quick_baseline',
        failure_reason: 'garak failed',
        garak: {},
        raw_findings: [],
        scanner_evidence: [],
        signals: [],
        findings: [],
        sprico_final_verdict: { verdict: 'NOT_EVALUATED', violation_risk: 'NOT_AVAILABLE' },
        aggregate: { final_verdict: 'NOT_EVALUATED', worst_risk: 'NOT_AVAILABLE', evidence_count: 0, findings_count: 0 },
        artifacts: [],
      },
    ]))

    renderWithProvider(<GarakScannerPage />)

    expect(await screen.findByText(/Scanner failed before producing usable evidence/)).toBeInTheDocument()
    expect(screen.getAllByText('NOT_EVALUATED').length).toBeGreaterThan(0)
    expect(screen.getByText('garak failed')).toBeInTheDocument()
  })

  it('separates current configuration target from selected historical result target', async () => {
    const user = userEvent.setup()
    ;(garakApi.listReports as jest.Mock).mockResolvedValue(reportsResponse([
      {
        scan_id: 'old-scan',
        status: 'completed_no_findings',
        target_id: 'mock_hospital_target',
        target_name: 'mock_hospital_target',
        policy_id: 'policy_hospital_strict_v1',
        scan_profile: 'quick_baseline',
        garak: {},
        raw_findings: [],
        scanner_evidence: [],
        signals: [],
        findings: [],
        sprico_final_verdict: { verdict: 'PASS', violation_risk: 'LOW' },
        aggregate: { final_verdict: 'PASS', worst_risk: 'LOW', evidence_count: 0, findings_count: 0 },
        artifacts: [],
      },
    ]))

    renderWithProvider(<GarakScannerPage />)

    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')

    expect(screen.getByText(/You are viewing a previous scan result for mock_hospital_target. Current configuration target is Safe Hospital Target./)).toBeInTheDocument()
  })

  it('warns and blocks by default for HR target with hospital policy until cross-domain override', async () => {
    const user = userEvent.setup()
    ;(targetsApi.listTargets as jest.Mock).mockResolvedValue({
      items: [
        {
          target_registry_name: 'OpenAIVectorStoreTarget::hr',
          display_name: 'SpriCo HR Data',
          target_type: 'OpenAIVectorStoreTarget',
          endpoint: 'https://api.openai.com/v1',
          model_name: 'gpt-4.1',
          target_specific_params: { target_domain: 'HR' },
        },
      ],
      pagination: { limit: 200, has_more: false, next_cursor: null, prev_cursor: null },
    })

    renderWithProvider(<GarakScannerPage />)

    const runButton = await screen.findByRole('button', { name: 'Run Vulnerability Scan' })
    await waitFor(() => expect(screen.getByRole('option', { name: /SpriCo HR Data/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::hr')
    await user.click(screen.getByLabelText(/I attest that I have authorization/))

    expect(screen.getByText(/Selected target domain is HR, but selected policy is hospital/)).toBeInTheDocument()
    expect(screen.getByText(/Confirm cross-domain evaluation before running this scan/)).toBeInTheDocument()
    expect(runButton).toBeDisabled()

    await user.click(screen.getByLabelText(/I confirm this cross-domain evaluation is intentional/))
    expect(runButton).not.toBeDisabled()
  })

  it('treats healthcare target and hospital policy as compatible without cross-domain override', async () => {
    const user = userEvent.setup()

    renderWithProvider(<GarakScannerPage />)

    const runButton = await screen.findByRole('button', { name: 'Run Vulnerability Scan' })
    await waitFor(() => expect(screen.getByRole('option', { name: /Safe Hospital Target/ })).toBeInTheDocument())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Target' }), 'OpenAIVectorStoreTarget::safe')
    await user.click(screen.getByLabelText(/I attest that I have authorization/))

    expect(document.body).not.toHaveTextContent(/confirm cross-domain evaluation/i)
    expect(runButton).not.toBeDisabled()
  })
})
