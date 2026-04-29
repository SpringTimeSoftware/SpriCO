import { useEffect, useMemo, useState } from 'react'
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Tooltip,
} from '@fluentui/react-components'
import { InfoRegular } from '@fluentui/react-icons'
import type { AuditFindingsFilters } from '../../App'
import { auditApi, targetsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { AuditExecutionProfileRequest, AuditPromptSourceMode, AuditResultRow, AuditRun, AuditTest, AuditVariant, RetrievalTrace, TargetCapability, TargetInstance } from '../../types'
import { getVisibleParameterHelp, MODE_RECOMMENDATIONS, PARAMETER_HELP, SEED_STRATEGY_HELP, targetSupportsTopK } from './parameterHelp'
import './auditPlatform.css'

const POLL_MS = 2_000
const ALL_FINDINGS_RUNS_VALUE = '__all_runs__'
const FINDING_SEVERITY_OPTIONS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const
const WORKBOOK_IMPORT_INDUSTRIES = ['Hospital', 'HR', 'Legal', 'Support', 'Finance', 'Generic'] as const

interface AuditPageProps {
  initialRunId?: string | null
  initialFilters?: AuditFindingsFilters | null
  forcedWorkspaceView?: AuditWorkspaceView
  backLink?: {
    label: string
    onClick: () => void
  }
  onRunOpened?: () => void
}

type AuditWorkspaceView = 'runner' | 'findings'
type AuditMode = 'COMPLIANCE' | 'ROBUSTNESS' | 'ADVANCED'
type VerdictFilter = 'ALL' | 'FAIL' | 'WARN' | 'PASS'
type AuditFilterOption = { name: string; test_count: number }
type AuditFilterCatalog = {
  industries: AuditFilterOption[]
  categories: AuditFilterOption[]
  has_real_domains: boolean
  domains: AuditFilterOption[]
}
type FindingRecord = AuditResultRow & {
  run_id: string
  run_model_name?: string | null
  run_completed_at?: string | null
}

export default function AuditPage({ initialRunId, initialFilters, forcedWorkspaceView, backLink, onRunOpened }: AuditPageProps) {
  const [workspaceView, setWorkspaceView] = useState<AuditWorkspaceView>(forcedWorkspaceView ?? 'runner')
  const [options, setOptions] = useState<AuditFilterCatalog | null>(null)
  const [tests, setTests] = useState<AuditTest[]>([])
  const [targets, setTargets] = useState<TargetInstance[]>([])
  const [recentRuns, setRecentRuns] = useState<AuditRun[]>([])
  const [selectedIndustries, setSelectedIndustries] = useState<string[]>([])
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [selectedDomains, setSelectedDomains] = useState<string[]>([])
  const [selectedBaseTestIds, setSelectedBaseTestIds] = useState<number[]>([])
  const [selectedVariantIds, setSelectedVariantIds] = useState<number[]>([])
  const [promptSourceMode, setPromptSourceMode] = useState<AuditPromptSourceMode>('base')
  const [selectedTargets, setSelectedTargets] = useState<string[]>([])
  const [selectedLibraryTest, setSelectedLibraryTest] = useState<AuditTest | null>(null)
  const [selectedVariantDetail, setSelectedVariantDetail] = useState<AuditVariant | null>(null)
  const [run, setRun] = useState<AuditRun | null>(null)
  const [comparisonRunIds, setComparisonRunIds] = useState<string[]>([])
  const [comparisonRuns, setComparisonRuns] = useState<AuditRun[]>([])
  const [allFindings, setAllFindings] = useState<FindingRecord[]>([])
  const [selectedFinding, setSelectedFinding] = useState<FindingRecord | null>(null)
  const [selectedFindingRetrievalTraces, setSelectedFindingRetrievalTraces] = useState<RetrievalTrace[]>([])
  const [findingsRunSelection, setFindingsRunSelection] = useState<string>(ALL_FINDINGS_RUNS_VALUE)
  const [variantName, setVariantName] = useState('')
  const [variantPrompt, setVariantPrompt] = useState('')
  const [variantExpectedBehavior, setVariantExpectedBehavior] = useState('')
  const [findingVariantName, setFindingVariantName] = useState('')
  const [findingVariantPrompt, setFindingVariantPrompt] = useState('')
  const [findingVariantExpectedBehavior, setFindingVariantExpectedBehavior] = useState('')
  const [findingVerdictFilter, setFindingVerdictFilter] = useState<VerdictFilter>('ALL')
  const [findingCategoryFilter, setFindingCategoryFilter] = useState('')
  const [findingSeverityFilter, setFindingSeverityFilter] = useState('')
  const [findingSearch, setFindingSearch] = useState('')
  const [auditMode, setAuditMode] = useState<AuditMode>('COMPLIANCE')
  const [temperature, setTemperature] = useState(0)
  const [topP, setTopP] = useState(1)
  const [topK, setTopK] = useState('')
  const [maxTokens, setMaxTokens] = useState('')
  const [fixedSeed, setFixedSeed] = useState(true)
  const [seed, setSeed] = useState(() => defaultSeed())
  const [seedStrategy, setSeedStrategy] = useState<'FIXED' | 'PER_RUN_RANDOM' | 'SEQUENTIAL'>('FIXED')
  const [runCount, setRunCount] = useState(1)
  const [showExecutionParameters, setShowExecutionParameters] = useState(false)
  const [showParameterHelp, setShowParameterHelp] = useState(false)
  const [isParameterHelpDialogOpen, setIsParameterHelpDialogOpen] = useState(false)
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false)
  const [isImportingWorkbook, setIsImportingWorkbook] = useState(false)
  const [importIndustryType, setImportIndustryType] = useState<string>('Hospital')
  const [importSourceLabel, setImportSourceLabel] = useState('')
  const [importWorkbookFile, setImportWorkbookFile] = useState<File | null>(null)
  const [isRunnerSelectionCollapsed, setIsRunnerSelectionCollapsed] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingTests, setIsLoadingTests] = useState(false)
  const [isStartingRun, setIsStartingRun] = useState(false)
  const [isSavingVariant, setIsSavingVariant] = useState(false)
  const [isFindingEditorOpen, setIsFindingEditorOpen] = useState(false)
  const [isSavingFindingVariant, setIsSavingFindingVariant] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [targetCapabilities, setTargetCapabilities] = useState<TargetCapability[]>([])

  const auditableTargets = useMemo(
    () => targets.filter(target => target.target_type !== 'TextTarget' && Boolean(target.endpoint) && Boolean(target.model_name)),
    [targets],
  )

  const selectedTargetInfos = useMemo(
    () => auditableTargets.filter(target => selectedTargets.includes(target.target_registry_name)),
    [auditableTargets, selectedTargets],
  )

  const selectedTargetInfo = useMemo(
    () => selectedTargetInfos[0] ?? null,
    [selectedTargetInfos],
  )
  const supportsTopK = useMemo(
    () => targetSupportsTopK(selectedTargetInfo, targetCapabilities),
    [selectedTargetInfo, targetCapabilities],
  )
  const visibleParameterHelp = useMemo(
    () => getVisibleParameterHelp({ supportsTopK }),
    [supportsTopK],
  )

  const allActiveVariantCountForSelectedTests = useMemo(() => {
    if (!selectedBaseTestIds.length) return 0
    return tests
      .filter(test => selectedBaseTestIds.includes(test.id))
      .reduce((count, test) => count + test.variants.length, 0)
  }, [selectedBaseTestIds, tests])
  const selectedExecutionCount = useMemo(
    () => getExecutionCountForMode(promptSourceMode),
    [
      allActiveVariantCountForSelectedTests,
      promptSourceMode,
      selectedBaseTestIds.length,
      selectedLibraryTest,
      selectedVariantIds.length,
      variantPrompt,
    ],
  )
  const effectiveExecutionCount = selectedExecutionCount * Math.max(1, runCount)
  const activeFindings = useMemo<FindingRecord[]>(
    () => findingsRunSelection === ALL_FINDINGS_RUNS_VALUE
      ? allFindings
      : enrichRunResults(run),
    [allFindings, findingsRunSelection, run],
  )
  const displayedCategoryOptions = useMemo(
    () => selectedIndustries.length ? (options?.categories ?? []) : [],
    [options, selectedIndustries],
  )
  const workbookImportIndustryOptions = useMemo(() => {
    const currentIndustries = (options?.industries ?? []).map(item => item.name)
    return Array.from(new Set([...WORKBOOK_IMPORT_INDUSTRIES, ...currentIndustries]))
  }, [options])
  const findingCategories = useMemo(() => {
    const workbookCategories = (options?.categories ?? []).map(item => item.name)
    const findingCategoriesFromData = activeFindings.map(item => item.category_name)
    return Array.from(new Set([...workbookCategories, ...findingCategoriesFromData]))
  }, [activeFindings, options])
  const findingSeverities = FINDING_SEVERITY_OPTIONS

  const filteredFindings = useMemo(() => {
    return activeFindings.filter(item => {
      const verdict = (item.score_status ?? '').toUpperCase()
      const searchText = [
        item.test_identifier,
        item.attack_type,
        item.test_objective,
        item.category_name,
        item.response_received ?? '',
        item.audit_reasoning ?? '',
        item.score_reason ?? '',
      ].join(' ').toLowerCase()
      if (findingVerdictFilter !== 'ALL' && verdict !== findingVerdictFilter) return false
      if (findingCategoryFilter && item.category_name !== findingCategoryFilter) return false
      if (findingSeverityFilter && item.severity !== findingSeverityFilter) return false
      if (findingSearch && !searchText.includes(findingSearch.toLowerCase())) return false
      return true
    })
  }, [activeFindings, findingCategoryFilter, findingSearch, findingSeverityFilter, findingVerdictFilter])

  const findingsSummary = {
    total: activeFindings.length,
    pass: activeFindings.filter(item => (item.score_status ?? '').toUpperCase() === 'PASS').length,
    warn: activeFindings.filter(item => (item.score_status ?? '').toUpperCase() === 'WARN').length,
    fail: activeFindings.filter(item => (item.score_status ?? '').toUpperCase() === 'FAIL').length,
    errors: activeFindings.filter(item => isErrorResult(item)).length,
    critical: activeFindings.filter(item => item.severity === 'CRITICAL' && ['FAIL', 'WARN'].includes((item.score_status ?? '').toUpperCase())).length,
  }
  const isFocusedFindings = forcedWorkspaceView === 'findings'
  const isRunnerView = !isFocusedFindings && workspaceView === 'runner'
  const isAllFindingsSelection = findingsRunSelection === ALL_FINDINGS_RUNS_VALUE
  const heroTitle = isFocusedFindings ? 'Findings' : 'Audit Workstation'
  const heroSubtitle = isFocusedFindings
    ? 'Run-scoped evidence view with workbook prompts, actual prompts, model responses, reasoning, and variant follow-up actions.'
    : 'Structured workbook tests, saved prompt variants, live target execution, and evidence-backed findings all stay connected to SQLite-backed audit data.'

  useEffect(() => {
    const loadRetrievalTraces = async () => {
      if (!selectedFinding?.stability_run_id) {
        setSelectedFindingRetrievalTraces([])
        return
      }
      try {
        setSelectedFindingRetrievalTraces(await auditApi.getRetrievalTraces(selectedFinding.stability_run_id))
      } catch {
        setSelectedFindingRetrievalTraces([])
      }
    }
    void loadRetrievalTraces()
  }, [selectedFinding?.stability_run_id])

  async function fetchRecentRuns() {
    try {
      setRecentRuns(await auditApi.listRuns(25))
    } catch {
      // Keep the rest of the workstation usable.
    }
  }

  async function fetchAuditCatalog(industryFilters?: string[]) {
    const catalog = await auditApi.getOptions({ industries: industryFilters })
    const normalized = normalizeFilterCatalog(catalog)
    setOptions(normalized)
    setError(null)
    return normalized
  }

  async function loadRun(runId: string, filters?: AuditFindingsFilters | null) {
    try {
      const detailedRun = await auditApi.getFindings(runId)
      setRun(detailedRun)
      setFindingsRunSelection(runId)
      setWorkspaceView('findings')
      setFindingVerdictFilter(filters?.verdict ?? 'ALL')
      setFindingCategoryFilter(filters?.category ?? '')
      setFindingSeverityFilter(filters?.severity ?? '')
      setFindingSearch(filters?.search ?? '')
      setSelectedFinding(enrichRunResults(detailedRun)[0] ?? null)
      onRunOpened?.()
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  async function loadAllFindings(filters?: AuditFindingsFilters | null) {
    try {
      const runs = recentRuns.length > 0 ? recentRuns : await auditApi.listRuns(25)
      if (recentRuns.length === 0) {
        setRecentRuns(runs)
      }
      const detailedRuns = await Promise.all(runs.map(item => auditApi.getFindings(item.job_id)))
      const merged = detailedRuns.flatMap(item => enrichRunResults(item))
      setAllFindings(merged)
      setRun(null)
      setFindingsRunSelection(ALL_FINDINGS_RUNS_VALUE)
      setWorkspaceView('findings')
      setFindingVerdictFilter(filters?.verdict ?? 'ALL')
      setFindingCategoryFilter(filters?.category ?? '')
      setFindingSeverityFilter(filters?.severity ?? '')
      setFindingSearch(filters?.search ?? '')
      setSelectedFinding(merged[0] ?? null)
      onRunOpened?.()
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  useEffect(() => {
    const load = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const [, targetResponse, runs, capabilities] = await Promise.all([
          fetchAuditCatalog(),
          targetsApi.listTargets(),
          auditApi.listRuns(25),
          auditApi.getTargetCapabilities().catch(() => []),
        ])
        setTargets(targetResponse.items)
        setRecentRuns(runs)
        setTargetCapabilities(capabilities)
        const defaultTarget = targetResponse.items.find(
          target => target.is_active && target.target_type !== 'TextTarget' && Boolean(target.endpoint) && Boolean(target.model_name),
        ) ?? targetResponse.items.find(
          target => target.target_type !== 'TextTarget' && Boolean(target.endpoint) && Boolean(target.model_name),
        )
        setSelectedTargets(defaultTarget ? [defaultTarget.target_registry_name] : [])
      } catch (err) {
        setError(toApiError(err).detail)
      } finally {
        setIsLoading(false)
      }
    }
    void load()
  }, [])

  useEffect(() => {
    if (isLoading) return
    void fetchAuditCatalog(selectedIndustries.length ? selectedIndustries : undefined)
  }, [isLoading, selectedIndustries])

  useEffect(() => {
    const loadTests = async () => {
      if (selectedIndustries.length === 0) {
        setTests([])
        setSelectedLibraryTest(null)
        setSelectedVariantDetail(null)
        setIsLoadingTests(false)
        return
      }
      setIsLoadingTests(true)
      try {
        const response = await auditApi.listTests({ industries: selectedIndustries, categories: selectedCategories, domains: selectedDomains })
        setTests(response.tests)
        setOptions(current => mergeFilterCatalogWithTests(current, response.tests))
        setError(null)
        setSelectedLibraryTest(current => {
          if (!current) return response.tests[0] ?? null
          return response.tests.find(item => item.id === current.id) ?? response.tests[0] ?? null
        })
      } catch (err) {
        setError(toApiError(err).detail)
      } finally {
        setIsLoadingTests(false)
      }
    }
    void loadTests()
  }, [selectedIndustries, selectedCategories, selectedDomains])

  useEffect(() => {
    const visibleTestIds = new Set(tests.map(test => test.id))
    const visibleVariantIds = new Set(tests.flatMap(test => test.variants.map(variant => variant.id)))

    setSelectedBaseTestIds(current => current.filter(id => visibleTestIds.has(id)))
    setSelectedVariantIds(current => current.filter(id => visibleVariantIds.has(id)))
    setSelectedVariantDetail(current => (current && visibleVariantIds.has(current.id) ? current : null))
  }, [tests])

  useEffect(() => {
    if (!selectedLibraryTest) {
      setVariantName('')
      setVariantPrompt('')
      setVariantExpectedBehavior('')
      setSelectedVariantDetail(null)
      return
    }
    if (selectedVariantDetail && selectedVariantDetail.parent_test_id === selectedLibraryTest.id) {
      applyVariantEditorState(selectedVariantDetail, selectedLibraryTest)
      return
    }
    if (selectedVariantDetail && selectedVariantDetail.parent_test_id !== selectedLibraryTest.id) {
      setSelectedVariantDetail(null)
    }
    applyBaseEditorState(selectedLibraryTest)
  }, [selectedLibraryTest, selectedVariantDetail])

  useEffect(() => {
    if (selectedIndustries.length === 0) {
      if (selectedCategories.length > 0) setSelectedCategories([])
      if (selectedDomains.length > 0) setSelectedDomains([])
      return
    }
    const allowedCategories = new Set((options?.categories ?? []).map(item => item.name))
    setSelectedCategories(current => {
      const next = current.filter(item => allowedCategories.has(item))
      return areStringArraysEqual(current, next) ? current : next
    })
  }, [options, selectedCategories, selectedDomains, selectedIndustries])

  useEffect(() => {
    if (!selectedFinding) {
      setFindingVariantName('')
      setFindingVariantPrompt('')
      setFindingVariantExpectedBehavior('')
      setIsFindingEditorOpen(false)
      return
    }
    setFindingVariantName(`${String(selectedFinding.attack_type ?? 'Prompt')} Follow-up`)
    setFindingVariantPrompt(String(selectedFinding.actual_prompt_sequence ?? ''))
    setFindingVariantExpectedBehavior(String(selectedFinding.expected_behavior_snapshot ?? ''))
  }, [selectedFinding])

  useEffect(() => {
    if (auditMode === 'COMPLIANCE') {
      setTemperature(0)
      setTopP(1)
      setFixedSeed(true)
      setSeedStrategy('FIXED')
      setRunCount(1)
      setShowParameterHelp(false)
      return
    }
    if (auditMode === 'ROBUSTNESS') {
      setTemperature(0.7)
      setTopP(1)
      setFixedSeed(false)
      setSeedStrategy('PER_RUN_RANDOM')
      setRunCount(current => Math.max(current, 5))
      setShowExecutionParameters(true)
      return
    }
    setShowExecutionParameters(true)
  }, [auditMode])

  useEffect(() => {
    if (!initialRunId) return
    void loadRun(initialRunId, initialFilters)
  }, [initialFilters, initialRunId])

  useEffect(() => {
    if (!forcedWorkspaceView) return
    setWorkspaceView(forcedWorkspaceView)
  }, [forcedWorkspaceView])

  useEffect(() => {
    if (forcedWorkspaceView !== 'findings' || initialRunId || run || recentRuns.length === 0) return
    void loadAllFindings(initialFilters)
  }, [forcedWorkspaceView, initialFilters, initialRunId, recentRuns, run])

  useEffect(() => {
    if (!run || !['pending', 'running'].includes(run.status)) return
    const timer = window.setInterval(async () => {
      try {
        const [statusSnapshot, resultsSnapshot] = await Promise.all([
          auditApi.getStatus(run.job_id),
          auditApi.getFindings(run.job_id),
        ])
        const mergedRun = { ...statusSnapshot, results: resultsSnapshot.results }
        setRun(mergedRun)
        const enriched = enrichRunResults(mergedRun)
        setSelectedFinding(current => enriched.find(item => item.id === current?.id) ?? enriched[0] ?? null)
        if (mergedRun.status === 'completed') void fetchRecentRuns()
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [run])

  useEffect(() => {
    if (comparisonRunIds.length === 0) return
    const timer = window.setInterval(async () => {
      try {
        const statusSnapshots = await Promise.all(comparisonRunIds.map(runId => auditApi.getStatus(runId)))
        setComparisonRuns(statusSnapshots)
        const terminalRuns = statusSnapshots.filter(item => ['completed', 'failed', 'error'].includes(item.status))
        if (terminalRuns.length !== comparisonRunIds.length) {
          return
        }
        const detailedRuns = await Promise.all(comparisonRunIds.map(runId => auditApi.getFindings(runId)))
        const merged = detailedRuns.flatMap(item => enrichRunResults(item))
        setAllFindings(merged)
        setRun(null)
        setFindingsRunSelection(ALL_FINDINGS_RUNS_VALUE)
        setWorkspaceView('findings')
        setSelectedFinding(merged[0] ?? null)
        setComparisonRunIds([])
        setComparisonRuns([])
        void fetchRecentRuns()
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [comparisonRunIds])

  useEffect(() => {
    if (!filteredFindings.length) {
      setSelectedFinding(null)
      return
    }
    setSelectedFinding(current => filteredFindings.find(item => item.id === current?.id) ?? filteredFindings[0] ?? null)
  }, [filteredFindings])

  const toggleIndustry = (value: string) => setSelectedIndustries(current => (
    current.includes(value) ? current.filter(item => item !== value) : [...current, value]
  ))

  const toggleCategory = (value: string) => setSelectedCategories(current => (
    current.includes(value) ? current.filter(item => item !== value) : [...current, value]
  ))

  const toggleDomain = (value: string) => setSelectedDomains(current => (
    current.includes(value) ? current.filter(item => item !== value) : [...current, value]
  ))

  const toggleBaseTest = (testId: number) => setSelectedBaseTestIds(current => (
    current.includes(testId) ? current.filter(item => item !== testId) : [...current, testId]
  ))

  const toggleTarget = (targetRegistryName: string) => setSelectedTargets(current => (
    current.includes(targetRegistryName)
      ? current.filter(item => item !== targetRegistryName)
      : [...current, targetRegistryName]
  ))

  const toggleVariantSelection = (variant: AuditVariant) => {
    const isSelected = selectedVariantIds.includes(variant.id)
    const parentTest = tests.find(test => test.id === variant.parent_test_id) ?? (selectedLibraryTest?.id === variant.parent_test_id ? selectedLibraryTest : null)

    if (parentTest && selectedLibraryTest?.id !== parentTest.id) {
      setSelectedLibraryTest(parentTest)
    }

    if (!isSelected) {
      setSelectedVariantIds(current => [...current, variant.id])
      loadVariantIntoEditor(variant, parentTest)
      return
    }

    const remainingVariantIds = selectedVariantIds.filter(item => item !== variant.id)
    setSelectedVariantIds(remainingVariantIds)

    if (selectedVariantDetail?.id === variant.id) {
      const fallbackVariant = (parentTest?.variants ?? []).find(item => remainingVariantIds.includes(item.id)) ?? null
      if (fallbackVariant) {
        loadVariantIntoEditor(fallbackVariant, parentTest)
        return
      }
      setSelectedVariantDetail(null)
      if (parentTest) {
        applyBaseEditorState(parentTest)
      }
      if (promptSourceMode === 'selected_variant') {
        setPromptSourceMode('base')
      }
    }
  }

  const handleSaveVariant = async () => {
    if (!selectedLibraryTest) return
    setIsSavingVariant(true)
    setError(null)
    try {
      const created = await auditApi.createVariant(selectedLibraryTest.id, {
        variant_name: variantName,
        edited_prompt_sequence: variantPrompt,
        edited_expected_behavior: variantExpectedBehavior,
        created_by: 'Auditor',
      })
      const refreshed = await auditApi.listTests({ industries: selectedIndustries, categories: selectedCategories, domains: selectedDomains })
      setTests(refreshed.tests)
      const updatedTest = refreshed.tests.find(test => test.id === selectedLibraryTest.id) ?? selectedLibraryTest
      const refreshedVariant = updatedTest.variants.find(variant => variant.id === created.id) ?? created
      setSelectedLibraryTest(updatedTest)
      setSelectedVariantDetail(refreshedVariant)
      setSelectedVariantIds(current => (current.includes(created.id) ? current : [...current, created.id]))
      setPromptSourceMode('selected_variant')
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsSavingVariant(false)
    }
  }

  const handleImportWorkbook = async () => {
    if (!importWorkbookFile) {
      setError('Select a workbook file before starting the import.')
      return
    }

    const selectedIndustry = importIndustryType.trim()
    if (!selectedIndustry) {
      setError('Select an Industry Type for the workbook import.')
      return
    }

    setIsImportingWorkbook(true)
    setError(null)
    setStatusMessage(null)
    try {
      const result = await auditApi.importWorkbook({
        file: importWorkbookFile,
        industryType: selectedIndustry,
        sourceLabel: importSourceLabel,
      })
      await fetchAuditCatalog([result.industry_type])
      const response = await auditApi.listTests({
        industries: [result.industry_type],
        categories: [],
        domains: [],
      })
      setSelectedIndustries([result.industry_type])
      setSelectedCategories([])
      setSelectedDomains([])
      setTests(response.tests)
      setOptions(current => mergeFilterCatalogWithTests(current, response.tests))
      setSelectedLibraryTest(response.tests[0] ?? null)
      setSelectedVariantDetail(null)
      setStatusMessage(
        `Imported ${result.imported_rows} workbook rows from ${result.workbook_name} into Industry Type = ${result.industry_type}.`,
      )
      setImportWorkbookFile(null)
      setImportSourceLabel('')
      setIsImportDialogOpen(false)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsImportingWorkbook(false)
    }
  }

  const buildExecutionProfile = (): AuditExecutionProfileRequest => ({
    mode_code: auditMode,
    temperature,
    top_p: topP,
    top_k: topK.trim() ? Number(topK) : null,
    fixed_seed: fixedSeed,
    base_seed: seed,
    seed_strategy: seedStrategy,
    max_tokens: maxTokens.trim() ? Number(maxTokens) : null,
    run_count_requested: Math.max(1, Math.min(Number(runCount) || 1, 25)),
    variability_mode: auditMode === 'ROBUSTNESS' || runCount > 1,
    created_by: 'Auditor',
  })

  const buildRunRequest = (
    targetRegistryName: string,
    modeOverride: AuditPromptSourceMode = promptSourceMode,
  ) => {
    const baseRequest = {
      industries: selectedIndustries,
      categories: selectedCategories,
      domains: selectedDomains,
      target_registry_name: targetRegistryName,
      allow_text_target: false,
      execution_profile: buildExecutionProfile(),
    }
    const exactSelectionRequest = {
      ...baseRequest,
      industries: [],
      categories: [],
      domains: [],
    }

    switch (modeOverride) {
      case 'current_edit':
        if (!selectedLibraryTest) {
          throw new Error('Select a workbook test before running the current edited prompt.')
        }
        if (!variantPrompt.trim()) {
          throw new Error('Current edited prompt runs require a non-empty prompt sequence.')
        }
        return {
          ...exactSelectionRequest,
          test_ids: [],
          variant_ids: [],
          prompt_source_mode: 'current_edit' as const,
          transient_prompt_sequence: variantPrompt,
          transient_expected_behavior: variantExpectedBehavior.trim() ? variantExpectedBehavior : null,
          selected_test_id_for_transient_run: selectedLibraryTest.id,
        }
      case 'selected_variant':
        return {
          ...exactSelectionRequest,
          test_ids: [],
          variant_ids: selectedVariantIds,
          prompt_source_mode: 'selected_variant' as const,
          transient_prompt_sequence: null,
          transient_expected_behavior: null,
          selected_test_id_for_transient_run: null,
        }
      case 'adversarial':
        return {
          ...exactSelectionRequest,
          test_ids: selectedBaseTestIds,
          variant_ids: [],
          prompt_source_mode: 'adversarial' as const,
          transient_prompt_sequence: null,
          transient_expected_behavior: null,
          selected_test_id_for_transient_run: null,
        }
      case 'both':
        return {
          ...exactSelectionRequest,
          test_ids: selectedBaseTestIds,
          variant_ids: [],
          prompt_source_mode: 'both' as const,
          transient_prompt_sequence: null,
          transient_expected_behavior: null,
          selected_test_id_for_transient_run: null,
        }
      case 'base_and_variant':
        return {
          ...exactSelectionRequest,
          test_ids: selectedBaseTestIds,
          variant_ids: selectedVariantIds,
          prompt_source_mode: 'base_and_variant' as const,
          transient_prompt_sequence: null,
          transient_expected_behavior: null,
          selected_test_id_for_transient_run: null,
        }
      case 'all_variants':
        return {
          ...exactSelectionRequest,
          test_ids: selectedBaseTestIds,
          variant_ids: [],
          prompt_source_mode: 'all_variants' as const,
          transient_prompt_sequence: null,
          transient_expected_behavior: null,
          selected_test_id_for_transient_run: null,
        }
      case 'base':
      default:
        return {
          ...exactSelectionRequest,
          test_ids: selectedBaseTestIds,
          variant_ids: [],
          prompt_source_mode: 'base' as const,
          transient_prompt_sequence: null,
          transient_expected_behavior: null,
          selected_test_id_for_transient_run: null,
        }
    }
  }

  const handleRunAudit = async (modeOverride?: AuditPromptSourceMode) => {
    const activeMode = modeOverride ?? promptSourceMode
    const executionCount = getExecutionCountForMode(activeMode)

    if (selectedTargets.length === 0) {
      setError('Select at least one validated target before executing an audit run.')
      return
    }
    if (executionCount === 0) {
      setError('Select the required workbook test or saved variant(s) for the chosen execution scope before executing an audit run.')
      return
    }
    setIsStartingRun(true)
    setError(null)
    try {
      if (activeMode !== promptSourceMode) {
        setPromptSourceMode(activeMode)
      }
      const createdRuns: AuditRun[] = []
      for (const targetRegistryName of selectedTargets) {
        createdRuns.push(await auditApi.createRun(buildRunRequest(targetRegistryName, activeMode)))
      }
      if (createdRuns.length === 1) {
        setComparisonRunIds([])
        setComparisonRuns([])
        setRun(createdRuns[0] ?? null)
        setSelectedFinding(enrichRunResults(createdRuns[0] ?? null)[0] ?? null)
        setWorkspaceView('runner')
      } else {
        setRun(null)
        setSelectedFinding(null)
        setComparisonRuns(createdRuns)
        setComparisonRunIds(createdRuns.map(item => item.job_id))
        setWorkspaceView('runner')
      }
      await fetchRecentRuns()
    } catch (err) {
      setError(err instanceof Error ? err.message : toApiError(err).detail)
    } finally {
      setIsStartingRun(false)
    }
  }

  const handleSaveFindingVariant = async (executeAfterSave: boolean) => {
    if (!selectedFinding) return
    const targetRegistryName = selectedTargets[0] || run?.target_registry_name
    if (executeAfterSave && !targetRegistryName) {
      setError('No validated target is available to execute the saved variant.')
      return
    }
    setIsSavingFindingVariant(true)
    setError(null)
    try {
      const created = await auditApi.createVariant(selectedFinding.test_id, {
        variant_name: findingVariantName,
        edited_prompt_sequence: findingVariantPrompt,
        edited_expected_behavior: findingVariantExpectedBehavior,
        created_by: 'Auditor',
      })
      const refreshed = await auditApi.listTests({ industries: selectedIndustries, categories: selectedCategories, domains: selectedDomains })
      setTests(refreshed.tests)
      setSelectedLibraryTest(refreshed.tests.find(test => test.id === selectedFinding.test_id) ?? null)
      setSelectedVariantDetail(created)
      setSelectedVariantIds(current => (current.includes(created.id) ? current : [...current, created.id]))
      if (executeAfterSave && targetRegistryName) {
        const createdRun = await auditApi.createRun({
          industries: [],
          categories: [],
          domains: [],
          test_ids: [],
          variant_ids: [created.id],
          prompt_source_mode: 'selected_variant',
          transient_prompt_sequence: null,
          transient_expected_behavior: null,
          selected_test_id_for_transient_run: null,
          target_registry_name: targetRegistryName,
          allow_text_target: false,
          execution_profile: buildExecutionProfile(),
        })
        setRun(createdRun)
        setSelectedFinding(enrichRunResults(createdRun)[0] ?? null)
        setWorkspaceView('runner')
        await fetchRecentRuns()
      }
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsSavingFindingVariant(false)
    }
  }

  const summary = {
    total: comparisonRuns.length
      ? comparisonRuns.reduce((count, item) => count + item.total_tests, 0)
      : run?.total_tests ?? (effectiveExecutionCount * Math.max(selectedTargets.length, 1)),
    completed: comparisonRuns.length
      ? comparisonRuns.reduce((count, item) => count + item.completed_tests, 0)
      : run?.completed_tests ?? 0,
    pass: comparisonRuns.length
      ? comparisonRuns.reduce((count, item) => count + item.pass_count, 0)
      : run?.pass_count ?? 0,
    warn: comparisonRuns.length
      ? comparisonRuns.reduce((count, item) => count + item.warn_count, 0)
      : run?.warn_count ?? 0,
    fail: comparisonRuns.length
      ? comparisonRuns.reduce((count, item) => count + item.fail_count, 0)
      : run?.fail_count ?? 0,
    errors: comparisonRuns.length
      ? comparisonRuns.reduce((count, item) => count + item.error_count, 0)
      : run?.error_count ?? 0,
    progress: comparisonRuns.length
      ? (() => {
          const total = comparisonRuns.reduce((count, item) => count + item.total_tests, 0)
          const completed = comparisonRuns.reduce((count, item) => count + item.completed_tests, 0)
          return total ? Math.round((completed / total) * 10000) / 100 : 0
        })()
      : run?.progress_percent ?? 0,
  }

  function getExecutionCountForMode(mode: AuditPromptSourceMode) {
    switch (mode) {
      case 'current_edit':
        return selectedLibraryTest && variantPrompt.trim() ? 1 : 0
      case 'adversarial':
        return selectedBaseTestIds
          .map(testId => tests.find(test => test.id === testId))
          .filter((test): test is AuditTest => Boolean(test?.has_adversarial_prompt))
          .length
      case 'both':
        return selectedBaseTestIds.length + selectedBaseTestIds
          .map(testId => tests.find(test => test.id === testId))
          .filter((test): test is AuditTest => Boolean(test?.has_adversarial_prompt))
          .length
      case 'selected_variant':
        return selectedVariantIds.length
      case 'base_and_variant':
        return selectedBaseTestIds.length + selectedVariantIds.length
      case 'all_variants':
        return allActiveVariantCountForSelectedTests
      case 'base':
      default:
        return selectedBaseTestIds.length
    }
  }

  function applyBaseEditorState(test: AuditTest) {
    setVariantName(`${test.attack_type} Variant`)
    setVariantPrompt(String(test.base_prompt_sequence ?? test.prompt_sequence ?? ''))
    setVariantExpectedBehavior(String(test.expected_behavior ?? ''))
  }

  function applyVariantEditorState(variant: AuditVariant, test: AuditTest) {
    setVariantName(String(variant.variant_name ?? `${test.attack_type} Variant`))
    setVariantPrompt(String(variant.edited_prompt_sequence ?? test.base_prompt_sequence ?? test.prompt_sequence ?? ''))
    setVariantExpectedBehavior(String(variant.edited_expected_behavior ?? test.expected_behavior ?? ''))
  }

  function loadWorkbookBaseIntoEditor() {
    if (!selectedLibraryTest) return
    setSelectedVariantDetail(null)
    applyBaseEditorState(selectedLibraryTest)
    setPromptSourceMode('base')
  }

  function loadVariantIntoEditor(variant: AuditVariant, parentTest?: AuditTest | null) {
    const activeParentTest = parentTest ?? selectedLibraryTest
    if (!activeParentTest) return
    setSelectedVariantDetail(variant)
    applyVariantEditorState(variant, activeParentTest)
    setPromptSourceMode('selected_variant')
  }

  function handleVariantPromptChange(value: string) {
    setVariantPrompt(value)
    if (selectedLibraryTest) {
      setPromptSourceMode('current_edit')
    }
  }

  function handleVariantExpectedBehaviorChange(value: string) {
    setVariantExpectedBehavior(value)
    if (selectedLibraryTest) {
      setPromptSourceMode('current_edit')
    }
  }

  if (isLoading) {
    return (
      <div className="audit-platform">
        <div className="audit-message">Loading workbook-backed audit workspace...</div>
      </div>
    )
  }

  const selectedTestVariants = selectedLibraryTest?.variants ?? []

  return (
    <div className="audit-platform">
      <section className={`audit-hero ${isFocusedFindings ? 'audit-hero-findings' : isRunnerView ? 'audit-hero-runner' : ''}`}>
        <div>
          <div className="audit-hero-title">{heroTitle}</div>
          <div className="audit-hero-subtitle">{heroSubtitle}</div>
        </div>
        <div className={`audit-hero-meta ${isFocusedFindings ? 'audit-hero-meta-findings' : isRunnerView ? 'audit-hero-meta-runner' : ''}`}>
          <div className="audit-meta-card">
            <div className="audit-meta-label">Workspace</div>
            <div className="audit-meta-value">{workspaceView === 'runner' ? 'Runner' : 'Findings'}</div>
          </div>
          <div className="audit-meta-card">
            <div className="audit-meta-label">Selected Target</div>
            <div className="audit-meta-value">
              {selectedTargetInfos.length > 1
                ? `${selectedTargetInfos.length} targets selected`
                : selectedTargetInfo?.model_name ?? run?.model_name ?? 'No target'}
            </div>
          </div>
          <div className="audit-meta-card">
            <div className="audit-meta-label">Loaded Run</div>
            <div className="audit-meta-value">
              {workspaceView === 'findings' && isAllFindingsSelection ? 'All completed runs' : run?.job_id ?? 'Not loaded'}
            </div>
          </div>
        </div>
      </section>

      {isFocusedFindings ? (
        <section className="audit-context-bar">
          {backLink && (
            <button type="button" className="audit-secondary-btn" onClick={backLink.onClick}>
              {backLink.label}
            </button>
          )}
          <div className="audit-note">Focused findings view. Audit Workstation remains available from the main navigation.</div>
        </section>
      ) : workspaceView === 'findings' ? (
        <section className="audit-context-bar">
          <button type="button" className="audit-secondary-btn" onClick={() => setWorkspaceView('runner')}>
            Back To Runner
          </button>
          <div className="audit-note">Findings are also available as a dedicated workspace from the main navigation.</div>
        </section>
      ) : null}

      {error && <div className="audit-message error">{error}</div>}
      {statusMessage && <div className="audit-message">{statusMessage}</div>}

      {workspaceView === 'runner' ? (
        <>
          <section className="audit-panel audit-panel-feature">
            <div className="audit-panel-header">
              <div className="audit-panel-title">Workbook Scope And Target</div>
              <div className="audit-panel-header-actions">
                <button
                  type="button"
                  className="audit-secondary-btn audit-secondary-btn-small"
                  onClick={() => setIsImportDialogOpen(true)}
                >
                  Import Workbook
                </button>
                <div className="audit-note">
                  {isRunnerSelectionCollapsed
                    ? 'Collapsed to bring prompt detail and variants closer to the top of the workstation.'
                    : 'Collapse this section to focus on prompt detail, variants, and live execution.'}
                </div>
                <button
                  type="button"
                  className="audit-parameter-toggle"
                  onClick={() => setIsRunnerSelectionCollapsed(current => !current)}
                >
                  {isRunnerSelectionCollapsed ? 'Expand Selection And Target' : 'Collapse Selection And Target'}
                </button>
              </div>
            </div>

            {!isRunnerSelectionCollapsed && (
              <div className="audit-panel-body audit-panel-body-shell">
                <div className="audit-grid-runner audit-grid-runner-stretch">
                  <div className="audit-runner-filters">
                    <div className="audit-panel audit-panel-stretch">
                      <div className="audit-panel-header">
                        <div className="audit-panel-title">Industry Type</div>
                        <div className="audit-note">{selectedIndustries.length || options?.industries.length || 0} active</div>
                      </div>
                      <div className="audit-panel-body audit-panel-body-stretch">
                        <div className="audit-scroll-list audit-scroll-list-stretch">
                          {(options?.industries ?? []).map(industry => (
                            <label key={industry.name} className="audit-check-item">
                              <input type="checkbox" checked={selectedIndustries.includes(industry.name)} onChange={() => toggleIndustry(industry.name)} />
                              <div className="audit-item-main">
                                <div className="audit-item-title">{industry.name}</div>
                                <div className="audit-item-subtitle">{industry.test_count} workbook rows</div>
                              </div>
                            </label>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="audit-panel audit-panel-stretch">
                      <div className="audit-panel-header">
                        <div className="audit-panel-title">Workbook Categories</div>
                        <div className="audit-note">
                          {selectedIndustries.length === 0
                            ? 'Select an Industry Type first'
                            : `${selectedCategories.length || displayedCategoryOptions.length || 0} active`}
                        </div>
                      </div>
                      <div className="audit-panel-body audit-panel-body-stretch">
                        {selectedIndustries.length === 0 ? (
                          <div className="audit-message compact">Select an Industry Type to unlock workbook category filters.</div>
                        ) : (
                          <div className="audit-scroll-list audit-scroll-list-stretch">
                            {displayedCategoryOptions.map(category => (
                              <label key={category.name} className="audit-check-item">
                                <input type="checkbox" checked={selectedCategories.includes(category.name)} onChange={() => toggleCategory(category.name)} />
                                <div className="audit-item-main">
                                  <div className="audit-item-title">{category.name}</div>
                                  <div className="audit-item-subtitle">{category.test_count} workbook rows</div>
                                </div>
                              </label>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="audit-panel audit-panel-stretch audit-runner-library">
                    <div className="audit-panel-header">
                      <div className="audit-panel-title">Test Library</div>
                      <div className="audit-note">{isLoadingTests ? 'Refreshing...' : `${tests.length} workbook tests`}</div>
                    </div>
                    <div className="audit-panel-body audit-panel-body-stretch">
                      {selectedIndustries.length === 0 ? (
                        <div className="audit-message">Select an Industry Type to view tests.</div>
                      ) : (
                        <>
                          {options?.has_real_domains ? (
                            <>
                              <div className="audit-section-label">Domain Selector</div>
                              <div className="audit-scroll-list" style={{ maxHeight: '160px', marginBottom: '14px' }}>
                                {(options?.domains ?? []).map(domain => (
                                  <label key={domain.name} className="audit-domain-item">
                                    <input type="checkbox" checked={selectedDomains.includes(domain.name)} onChange={() => toggleDomain(domain.name)} />
                                    <div className="audit-item-main">
                                      <div className="audit-item-title">{domain.name}</div>
                                      <div className="audit-item-subtitle">{domain.test_count} tests</div>
                                    </div>
                                  </label>
                                ))}
                              </div>
                            </>
                          ) : (
                            <div className="audit-message">Domain selector hidden: the imported workbook does not contain a native domain column.</div>
                          )}

                          <div className="audit-message compact">
                            Filters only control which workbook rows are visible. Execution runs only the checked workbook rows, selected saved variants, or the current editor prompt based on the chosen Prompt Variant Scope.
                          </div>

                          <div className="audit-table-wrap audit-table-scroll audit-table-wrap-stretch">
                            <table className="audit-table">
                              <thead>
                                <tr>
                                  <th style={{ width: '38px' }}>Use</th>
                                  <th style={{ width: '120px' }}>Test ID</th>
                                  <th>Workbook Objective</th>
                                  <th style={{ width: '110px' }}>Industry</th>
                                  <th style={{ width: '140px' }}>Category</th>
                                  <th style={{ width: '120px' }}>Prompt Variants</th>
                                  <th style={{ width: '96px' }}>Severity</th>
                                  {options?.has_real_domains && <th style={{ width: '120px' }}>Domain</th>}
                                </tr>
                              </thead>
                              <tbody>
                                {tests.map(test => (
                                  <tr
                                    key={test.id}
                                    className={`is-clickable ${selectedLibraryTest?.id === test.id ? 'selected' : ''}`}
                                    onClick={() => {
                                      setSelectedLibraryTest(test)
                                      setSelectedVariantDetail(null)
                                    }}
                                  >
                                    <td onClick={event => event.stopPropagation()}>
                                      <input type="checkbox" checked={selectedBaseTestIds.includes(test.id)} onChange={() => toggleBaseTest(test.id)} />
                                    </td>
                                    <td className="audit-code-cell">{test.test_identifier}</td>
                                    <td>
                                      <div className="audit-test-name">{test.attack_type}</div>
                                      <div className="audit-test-objective">{test.test_objective}</div>
                                    </td>
                                    <td>{renderBadge(test.industry_type, 'info')}</td>
                                    <td>{renderBadge(test.category_name, 'info')}</td>
                                    <td>{test.has_adversarial_prompt ? 'Base + Adversarial' : 'Base only'}</td>
                                    <td>{renderBadge(test.severity, severityTone(test.severity))}</td>
                                    {options?.has_real_domains && <td>{test.domain ?? 'Unspecified'}</td>}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="audit-panel audit-panel-stretch audit-runner-execution">
                    <div className="audit-panel-header">
                      <div className="audit-panel-title">Validated Target</div>
                      <div className="audit-note">
                        {selectedTargetInfos.length > 1
                          ? `${selectedTargetInfos.length} validated targets selected`
                          : selectedTargetInfo?.model_name ?? 'No validated target selected'}
                      </div>
                    </div>
                    <div className="audit-panel-body audit-panel-body-stretch">
                <div className="audit-scroll-list audit-scroll-list-compact">
                  {auditableTargets.map(target => (
                    <label key={target.target_registry_name} className={`audit-target-item ${selectedTargets.includes(target.target_registry_name) ? 'active' : ''}`}>
                      <input
                        type="checkbox"
                        checked={selectedTargets.includes(target.target_registry_name)}
                        onChange={() => toggleTarget(target.target_registry_name)}
                      />
                      <div className="audit-item-main">
                        <div className="audit-item-title">{target.display_name ?? target.target_registry_name}</div>
                        <div className="audit-item-subtitle">{target.model_name}</div>
                        <div className="audit-small-meta">{target.target_type} | {target.endpoint}</div>
                      </div>
                    </label>
                  ))}
                  {auditableTargets.length === 0 && (
                    <div className="audit-message">No validated LLM target is registered. Configure one before running a structured audit.</div>
                  )}
                </div>

                <div className="audit-run-box">
                  <div className="audit-mode-selector">
                    <AuditModeCard
                      mode="COMPLIANCE"
                      title="Compliance Audit"
                      detail="Use for reproducible audit evidence, comparison, and final reporting."
                      activeMode={auditMode}
                      onSelect={setAuditMode}
                    />
                    <AuditModeCard
                      mode="ROBUSTNESS"
                      title="Robustness Audit"
                      detail="Use to discover inconsistent defenses, brittle refusals, and worst-case behavior."
                      activeMode={auditMode}
                      onSelect={setAuditMode}
                    />
                    <AuditModeCard
                      mode="ADVANCED"
                      title="Advanced"
                      detail="Expert controls. Results may be less comparable if parameters change between runs."
                      activeMode={auditMode}
                      onSelect={setAuditMode}
                    />
                  </div>

                  <button
                    type="button"
                    className="audit-parameter-toggle"
                    onClick={() => setShowExecutionParameters(current => !current)}
                  >
                    {showExecutionParameters ? 'Hide Execution Parameters' : 'Show Execution Parameters'}
                  </button>

                  {showExecutionParameters && (
                    <div className="audit-execution-parameters">
                      <label className="audit-form-field">
                        <ParameterFieldLabel helpKey="run_count" />
                        <input type="number" min={1} max={25} value={runCount} onChange={event => setRunCount(Number(event.target.value) || 1)} />
                      </label>
                      <label className="audit-form-field">
                        <ParameterFieldLabel helpKey="temperature" />
                        <input type="number" min={0} max={2} step={0.1} value={temperature} onChange={event => setTemperature(Number(event.target.value))} />
                      </label>
                      <label className="audit-form-field">
                        <ParameterFieldLabel helpKey="top_p" />
                        <input type="number" min={0} max={1} step={0.05} value={topP} onChange={event => setTopP(Number(event.target.value))} />
                      </label>
                      <label className="audit-form-field">
                        <ParameterFieldLabel helpKey="seed_strategy" />
                        <select value={seedStrategy} onChange={event => setSeedStrategy(event.target.value as 'FIXED' | 'PER_RUN_RANDOM' | 'SEQUENTIAL')}>
                          <option value="FIXED">Fixed</option>
                          <option value="PER_RUN_RANDOM">Per-run random</option>
                          <option value="SEQUENTIAL">Sequential</option>
                        </select>
                        <span className="audit-field-hint">{SEED_STRATEGY_HELP[seedStrategy]}</span>
                      </label>
                      <label className="audit-form-field">
                        <ParameterFieldLabel helpKey="seed" />
                        <input type="number" value={seed} onChange={event => setSeed(Number(event.target.value) || defaultSeed())} />
                      </label>
                      <label className="audit-checkbox-field">
                        <input type="checkbox" checked={fixedSeed} onChange={event => setFixedSeed(event.target.checked)} />
                        <ParameterFieldLabel helpKey="fixed_seed" compact />
                      </label>
                      {auditMode === 'ADVANCED' && (
                        <>
                          {supportsTopK && (
                            <label className="audit-form-field">
                              <ParameterFieldLabel helpKey="top_k" />
                              <input type="number" value={topK} onChange={event => setTopK(event.target.value)} placeholder="Optional" />
                            </label>
                          )}
                          <label className="audit-form-field">
                            <ParameterFieldLabel helpKey="max_tokens" />
                            <input type="number" value={maxTokens} onChange={event => setMaxTokens(event.target.value)} placeholder="Optional" />
                          </label>
                        </>
                      )}
                      <div className="audit-message compact">
                        {auditMode === 'COMPLIANCE'
                          ? 'Compliance mode uses deterministic, report-grade defaults: temperature 0, fixed seed, one run.'
                          : auditMode === 'ROBUSTNESS'
                            ? 'Robustness mode repeats each selected test to measure variability, fail rate, and worst-case behavior.'
                            : 'Advanced mode is for expert users. Results may be less comparable if parameters change between runs.'}
                      </div>
                    </div>
                  )}

                  <button
                    type="button"
                    className="audit-parameter-toggle"
                    onClick={() => setShowParameterHelp(current => !current)}
                  >
                    {showParameterHelp ? 'Hide Parameter Help' : 'Show Parameter Help'}
                  </button>

                  {showParameterHelp && (
                    <div className="audit-parameter-help-card">
                      <div className="audit-parameter-help-header">
                        <div>
                          <div className="audit-section-label">Parameter Help</div>
                          <div className="audit-note">
                            These are generation controls, not direct safety controls. The same prompt can still return different outputs if the model version, context, or system prompt changes.
                          </div>
                        </div>
                        <button type="button" className="audit-secondary-btn audit-secondary-btn-small" onClick={() => setIsParameterHelpDialogOpen(true)}>
                          Learn how generation settings work
                        </button>
                      </div>

                      <div className="audit-parameter-thumbnail">
                        <div className="audit-parameter-thumbnail-title">Token Generation Flow</div>
                        <div className="audit-token-flow" aria-hidden="true">
                          <span>Prompt + context</span>
                          <span>Candidate tokens</span>
                          <span>Temperature / Top P / Top K</span>
                          <span>Select next token</span>
                          <span>Repeat loop</span>
                        </div>
                      </div>

                      <div className="audit-parameter-recommendations">
                        <RecommendationCard title="Compliance Audit" items={MODE_RECOMMENDATIONS.COMPLIANCE} />
                        <RecommendationCard title="Robustness Audit" items={MODE_RECOMMENDATIONS.ROBUSTNESS} />
                        <RecommendationCard title="Advanced" items={MODE_RECOMMENDATIONS.ADVANCED} />
                      </div>

                      <div className="audit-parameter-help-grid">
                        {visibleParameterHelp.map(item => (
                          <div key={item.key} className="audit-parameter-help-item">
                            <div className="audit-parameter-help-label">{item.label}</div>
                            <div className="audit-parameter-help-copy">{item.long_help[0]}</div>
                            <div className="audit-parameter-help-copy">{item.long_help[1]}</div>
                            {item.long_help[2] && <div className="audit-parameter-help-copy">{item.long_help[2]}</div>}
                          </div>
                        ))}
                      </div>

                      <div className="audit-parameter-help-notes">
                        <div className="audit-note">Temperature reshapes probabilities. Top P trims the candidate pool. Top K is shown only when the selected target supports it.</div>
                        <div className="audit-note">Token and candidate-token concepts explain how the model generates one token at a time and how these controls affect selection.</div>
                      </div>
                    </div>
                  )}

                  <label className="audit-form-field">
                    <span>Prompt Variant Scope</span>
                    <select value={promptSourceMode} onChange={event => setPromptSourceMode(event.target.value as AuditPromptSourceMode)}>
                      <option value="base">Base Prompt Only</option>
                      <option value="adversarial">Adversarial Prompt Only</option>
                      <option value="both">Base + Adversarial</option>
                      <option value="current_edit">Current Edited Prompt</option>
                      <option value="selected_variant">Selected Saved Variant(s)</option>
                      <option value="base_and_variant">Base Test(s) + Selected Variant(s)</option>
                      <option value="all_variants">All Active Variants for Selected Base Test(s)</option>
                    </select>
                    <span className="audit-field-hint">{describePromptSourceMode(promptSourceMode)}</span>
                  </label>

                  <div className="audit-config-grid">
                    <div className="audit-config-row"><span>Execution Source</span><span>SQLite workbook tests + saved variants</span></div>
                    <div className="audit-config-row"><span>Prompt Source Mode</span><span>{formatPromptSourceMode(promptSourceMode)}</span></div>
                    <div className="audit-config-row"><span>Audit Mode</span><span>{auditMode}</span></div>
                    <div className="audit-config-row"><span>Progress Polling</span><span>Every 2 seconds</span></div>
                    <div className="audit-config-row"><span>TextTarget</span><span>Blocked</span></div>
                    <div className="audit-config-row"><span>Target Validation</span><span>Endpoint + model required</span></div>
                  </div>
                  <div className="audit-run-summary">
                    <strong>{selectedExecutionCount}</strong> checked execution item(s), <strong>{effectiveExecutionCount * Math.max(selectedTargets.length, 1)}</strong> physical run(s) across <strong>{selectedTargetInfos.length || 0}</strong> target(s)
                  </div>
                  <div className="audit-note">Audit Workstation executes the exact checked scope only. Unchecked visible rows are never expanded into a run.</div>
                  <button
                    className="audit-primary-btn"
                    type="button"
                    onClick={() => void handleRunAudit()}
                    disabled={selectedTargets.length === 0 || selectedExecutionCount === 0 || isStartingRun}
                  >
                    {isStartingRun ? 'Starting Audit' : 'Execute Audit'}
                  </button>
                </div>
              </div>
            </div>
                </div>
              </div>
            )}
          </section>

          <section className="audit-panel">
            <div className="audit-panel-header">
              <div className="audit-panel-title">Test Detail And Variants</div>
              <div className="audit-note">{selectedLibraryTest ? `${selectedLibraryTest.test_identifier} selected` : 'Select a workbook test row'}</div>
            </div>
            <div className="audit-panel-body">
              {selectedLibraryTest ? (
                <div className="audit-detail-grid">
                  <DetailCard
                    title="Test Metadata"
                    value={[
                      `Test ID: ${selectedLibraryTest.test_identifier}`,
                      `Industry Type: ${selectedLibraryTest.industry_type}`,
                      `Category: ${selectedLibraryTest.category_name}`,
                      `Severity: ${selectedLibraryTest.severity}`,
                      `Prompt Variants: ${selectedLibraryTest.has_adversarial_prompt ? 'Base + Adversarial' : 'Base only'}`,
                      `Domain: ${selectedLibraryTest.domain ?? 'Unspecified'}`,
                    ].join('\n')}
                  />
                  <DetailCard title="Original Result Guidance" value={selectedLibraryTest.original_result_guidance ?? 'No workbook result guidance provided.'} />
                  <EditableDetailCard
                    title="Base Prompt"
                    value={variantPrompt}
                    onChange={handleVariantPromptChange}
                    note={selectedVariantDetail
                      ? `Loaded from saved variant "${selectedVariantDetail.variant_name}". Editing here switches execution to Current Edited Prompt until you save again.`
                      : 'Editable working copy. Changes here run as Current Edited Prompt when you execute the audit.'}
                  />
                  <DetailCard
                    title="Adversarial Prompt"
                    value={selectedLibraryTest.adversarial_prompt_sequence ?? 'No adversarial prompt saved for this logical workbook row.'}
                  />
                  <EditableDetailCard
                    title="Expected Behavior"
                    value={variantExpectedBehavior}
                    onChange={handleVariantExpectedBehaviorChange}
                    accent="expected"
                    note={selectedVariantDetail
                      ? 'The selected variant expectation is loaded. Edit it here to test a new unsaved version before saving.'
                      : 'Editable expected behavior used for current edited prompt runs.'}
                  />
                  <DetailCard title="Supporting Documents" value={formatSupportingDocuments(selectedLibraryTest.supporting_documents)} full />

                  <div className="audit-detail-card full">
                    <div className="audit-detail-title">Saved Variants</div>
                    <div className="audit-detail-body">
                      <div className="audit-check-item audit-check-item-static">
                        <div className="audit-item-main">
                          <div className="audit-item-title">Workbook Base</div>
                          <div className="audit-item-subtitle">Original imported workbook prompt and expected behavior.</div>
                          <div className="audit-small-meta">Load this to return the editor to the workbook version before running or saving.</div>
                        </div>
                        <button className="audit-secondary-btn audit-secondary-btn-small" type="button" onClick={loadWorkbookBaseIntoEditor}>
                          Load Base
                        </button>
                      </div>
                      <div className="audit-scroll-list" style={{ maxHeight: '180px' }}>
                        {selectedTestVariants.map(variant => (
                          <label key={variant.id} className={`audit-check-item ${selectedVariantDetail?.id === variant.id ? 'active' : ''}`}>
                            <input type="checkbox" checked={selectedVariantIds.includes(variant.id)} onChange={() => toggleVariantSelection(variant)} />
                            <div className="audit-item-main">
                              <div className="audit-item-title">{variant.variant_name}</div>
                              <div className="audit-item-subtitle">{variant.test_label} | {variant.created_by ?? 'Unknown author'} | {formatTimestamp(variant.created_at)}</div>
                              <div className="audit-small-meta">{variant.edited_expected_behavior ?? selectedLibraryTest.expected_behavior}</div>
                            </div>
                          </label>
                        ))}
                        {selectedTestVariants.length === 0 && <div className="audit-muted">No saved variants for this workbook test yet.</div>}
                      </div>
                    </div>
                  </div>

                  {selectedVariantDetail && (
                    <div className="audit-detail-card full">
                      <div className="audit-detail-title">Base vs Variant Comparison</div>
                      <div className="audit-detail-body audit-compare-grid">
                        <div className="audit-compare-card">
                          <div className="audit-section-label">Base Test Prompt</div>
                          <pre className="audit-code-block">{selectedLibraryTest.base_prompt_sequence}</pre>
                        </div>
                        <div className="audit-compare-card">
                          <div className="audit-section-label">Variant Prompt</div>
                          <pre className="audit-code-block accent-actual">{selectedVariantDetail.edited_prompt_sequence}</pre>
                        </div>
                        <div className="audit-compare-card">
                          <div className="audit-section-label">Base Expected Behavior</div>
                          <pre className="audit-code-block accent-expected">{selectedLibraryTest.expected_behavior}</pre>
                        </div>
                        <div className="audit-compare-card">
                          <div className="audit-section-label">Variant Expected Behavior</div>
                          <pre className="audit-code-block accent-response">{selectedVariantDetail.edited_expected_behavior ?? selectedLibraryTest.expected_behavior}</pre>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="audit-detail-card full">
                    <div className="audit-detail-title">Run Current Prompt And Save As Variant</div>
                    <div className="audit-detail-body">
                      <div className="audit-form-grid">
                        <label className="audit-form-field">
                          <span>Variant Name</span>
                          <input value={variantName} onChange={event => setVariantName(event.target.value)} />
                        </label>
                        <div className="audit-message compact">
                          <strong>Current source:</strong>{' '}
                          {promptSourceMode === 'current_edit'
                            ? 'Unsaved edited prompt'
                            : selectedVariantDetail && promptSourceMode === 'selected_variant'
                              ? `Saved variant "${selectedVariantDetail.variant_name}"`
                              : 'Workbook base prompt'}
                        </div>
                      </div>
                      <div className="audit-inline-actions">
                        <button
                          className="audit-secondary-btn"
                          type="button"
                          onClick={loadWorkbookBaseIntoEditor}
                        >
                          Reset to Workbook Base
                        </button>
                        <button
                          className="audit-primary-btn audit-primary-btn-inline"
                          type="button"
                          onClick={() => void handleRunAudit('current_edit')}
                          disabled={!selectedLibraryTest || selectedTargets.length === 0 || !variantPrompt.trim() || isStartingRun}
                        >
                          {isStartingRun && promptSourceMode === 'current_edit' ? 'Starting Audit' : 'Run Current Prompt'}
                        </button>
                        <button className="audit-secondary-btn" type="button" onClick={handleSaveVariant} disabled={isSavingVariant || !variantName.trim() || !variantPrompt.trim()}>
                          {isSavingVariant ? 'Saving Variant' : 'Save As Variant'}
                        </button>
                        <span className="audit-note">
                          {promptSourceMode === 'current_edit'
                            ? 'Execute Audit will run the current editor text as an unsaved prompt.'
                            : selectedVariantDetail
                              ? `Selected variant: ${selectedVariantDetail.variant_name}`
                              : 'Save a variant to persist this editor state.'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="audit-message">Click a workbook test row to open its detail panel, inspect evidence, and save prompt variants.</div>
              )}
            </div>
          </section>

          <section className="audit-panel">
            <div className="audit-panel-header">
              <div className="audit-panel-title">Live Execution</div>
              <div className="audit-note">
                {comparisonRuns.length > 1
                  ? `${comparisonRuns.length} comparison runs in flight`
                  : run ? `Job ${run.job_id}` : 'Awaiting execution'}
              </div>
            </div>
            <div className="audit-panel-body">
              <div className="audit-progress" style={{ marginBottom: '16px' }}>
                <div className="audit-progress-meta">
                  <span>
                    {run || comparisonRuns.length
                      ? `${summary.completed} / ${summary.total} items completed`
                      : 'Select workbook tests or variants and execute against one or more validated targets.'}
                  </span>
                  <span>{summary.progress}%</span>
                </div>
                <div className="audit-progress-track"><div className="audit-progress-fill" style={{ width: `${summary.progress}%` }} /></div>
              </div>
              {comparisonRuns.length > 1 && (
                <div className="audit-scroll-list" style={{ maxHeight: '180px', marginBottom: '16px' }}>
                  {comparisonRuns.map(item => (
                    <div key={item.job_id} className="audit-check-item audit-check-item-static">
                      <div className="audit-item-main">
                        <div className="audit-item-title">{item.model_name ?? item.target_registry_name}</div>
                        <div className="audit-item-subtitle">{item.target_registry_name}</div>
                        <div className="audit-small-meta">{item.status.toUpperCase()} | {item.completed_tests} / {item.total_tests} complete</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="audit-table-wrap">
                <table className="audit-table audit-table-dense">
                  <thead>
                    <tr>
                      <th>Test ID</th>
                      <th>Label</th>
                      <th>Category</th>
                      <th>Severity</th>
                      <th>Verdict</th>
                      <th>Score</th>
                      <th>Risk</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(run?.results ?? []).map(item => (
                      <tr
                        key={item.id}
                        className={`is-clickable ${selectedFinding?.id === item.id ? 'selected' : ''}`}
                        onClick={() => {
                          setSelectedFinding({
                            ...item,
                            run_id: run?.job_id ?? '',
                            run_model_name: run?.model_name ?? run?.target_registry_name,
                            run_completed_at: run?.completed_at ?? run?.updated_at,
                          })
                          setWorkspaceView('findings')
                        }}
                      >
                        <td className="audit-code-cell">{item.test_identifier}</td>
                        <td>{renderBadge(item.result_label, item.result_label === 'Variant' ? 'warn' : 'info')}</td>
                        <td>{item.category_name}</td>
                        <td>{renderBadge(item.severity, severityTone(item.severity))}</td>
                        <td>{renderBadge(displayResultStatus(item), verdictTone(item.score_status ?? item.execution_status))}</td>
                        <td>{item.score_value ?? '-'}</td>
                        <td>{renderBadge(item.risk_level ?? 'N/A', riskTone(item.risk_level))}</td>
                        <td>{item.score_reason ?? (item.execution_status === 'pending' ? 'Queued for execution' : 'Executing audit prompts')}</td>
                      </tr>
                    ))}
                    {(run?.results ?? []).length === 0 && (
                      <tr>
                        <td colSpan={8} className="audit-muted">No structured audit run has been executed yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section className="audit-summary-grid">
            <SummaryCard label="Selected" value={selectedExecutionCount.toString()} />
            <SummaryCard label="Completed" value={summary.completed.toString()} />
            <SummaryCard label="Pass" value={summary.pass.toString()} tone="pass" />
            <SummaryCard label="Warn" value={summary.warn.toString()} tone="warn" />
            <SummaryCard label="Fail" value={summary.fail.toString()} tone="fail" />
            <SummaryCard label="Errors" value={summary.errors.toString()} tone={summary.errors > 0 ? 'critical' : undefined} />
          </section>
        </>
      ) : (
        <section className="audit-findings-shell">
          {findingsRunSelection !== ALL_FINDINGS_RUNS_VALUE && !run ? (
            <div className="audit-empty-state">
              <div className="audit-empty-title">No audit run is loaded</div>
              <div className="audit-empty-copy">Open a recent run from the dashboard, or execute a structured audit to inspect findings here.</div>
              {recentRuns.length > 0 && (
                <div className="audit-empty-actions">
                  {recentRuns.slice(0, 3).map(item => (
                    <button key={item.job_id} className="audit-secondary-btn" type="button" onClick={() => void loadRun(item.job_id)}>
                      Open {item.job_id}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              <section className="audit-panel audit-panel-feature">
                <div className="audit-panel-body audit-findings-header">
                  <div className="audit-findings-title-block">
                    <div className="audit-section-label">Structured Findings</div>
                    <div className="audit-findings-title">{isAllFindingsSelection ? 'All Completed Runs' : `Audit Run ${run?.job_id}`}</div>
                    <div className="audit-findings-subtitle">
                      {isAllFindingsSelection
                        ? `${recentRuns.length} runs | ${activeFindings.length} findings loaded from SQLite`
                        : `${run?.model_name ?? run?.target_registry_name} | ${formatTimestamp(run?.completed_at ?? run?.updated_at ?? '')} | ${run?.endpoint ?? 'Endpoint not recorded'}`}
                    </div>
                  </div>

                    <div className="audit-findings-run-controls">
                      <label className="audit-form-field">
                        <span>Audit Run</span>
                        <select
                          value={findingsRunSelection}
                          onChange={event => {
                            const value = event.target.value
                            setSelectedFinding(null)
                            if (value === ALL_FINDINGS_RUNS_VALUE) {
                              void loadAllFindings()
                            } else {
                              void loadRun(value)
                            }
                          }}
                        >
                          <option value={ALL_FINDINGS_RUNS_VALUE}>All completed runs</option>
                          {recentRuns.map(item => (
                            <option key={item.job_id} value={item.job_id}>
                              {item.job_id} | {item.model_name ?? item.target_registry_name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>

                <div className="audit-panel-body audit-findings-kpis">
                  <FindingChip label="Total Findings" value={findingsSummary.total.toString()} />
                  <FindingChip label="Pass" value={findingsSummary.pass.toString()} tone="pass" />
                  <FindingChip label="Warn" value={findingsSummary.warn.toString()} tone="warn" />
                  <FindingChip label="Fail" value={findingsSummary.fail.toString()} tone="fail" />
                  <FindingChip label="Errors" value={findingsSummary.errors.toString()} tone={findingsSummary.errors > 0 ? 'critical' : 'info'} />
                  <FindingChip label="Critical Severity" value={findingsSummary.critical.toString()} tone="critical" />
                </div>
              </section>

              <section className="audit-panel">
                <div className="audit-panel-body audit-findings-filters">
                  <div className="audit-filter-toggle-group">
                    {(['ALL', 'FAIL', 'WARN', 'PASS'] as VerdictFilter[]).map(filter => (
                      <button
                        key={filter}
                        type="button"
                        className={`audit-filter-chip ${findingVerdictFilter === filter ? 'active' : ''} ${verdictTone(filter)}`}
                        onClick={() => setFindingVerdictFilter(filter)}
                      >
                        {filter}
                      </button>
                    ))}
                  </div>

                  <label className="audit-form-field">
                    <span>Category</span>
                    <select value={findingCategoryFilter} onChange={event => setFindingCategoryFilter(event.target.value)}>
                      <option value="">All categories</option>
                      {findingCategories.map(category => <option key={category} value={category}>{category}</option>)}
                    </select>
                  </label>

                  <label className="audit-form-field">
                    <span>Severity</span>
                    <select value={findingSeverityFilter} onChange={event => setFindingSeverityFilter(event.target.value)}>
                      <option value="">All severities</option>
                      {findingSeverities.map(severity => <option key={severity} value={severity}>{severity}</option>)}
                    </select>
                  </label>

                  <label className="audit-form-field audit-findings-search">
                    <span>Search</span>
                    <input value={findingSearch} onChange={event => setFindingSearch(event.target.value)} placeholder="Search test id, objective, response, reasoning..." />
                  </label>
                </div>
              </section>

              <section className="audit-findings-layout">
                <div className="audit-panel audit-findings-list-panel">
                  <div className="audit-panel-header">
                    <div className="audit-panel-title">Findings List</div>
                    <div className="audit-note">{filteredFindings.length} visible</div>
                  </div>
                  <div className="audit-panel-body audit-findings-list">
                    {filteredFindings.map(item => (
                      <button
                        key={item.id}
                        type="button"
                        className={`audit-finding-row ${selectedFinding?.id === item.id ? 'selected' : ''}`}
                        onClick={() => setSelectedFinding(item)}
                      >
                        <div className="audit-finding-row-top">
                          <span className="audit-code-cell">{item.test_identifier}</span>
                          <div className="audit-finding-badge-stack">
                            {renderBadge(promptSourceDisplayLabel(item), promptSourceTone(item))}
                            {renderBadge(item.category_name, 'info')}
                            {renderBadge(item.severity, severityTone(item.severity))}
                            {renderBadge(displayResultStatus(item), verdictTone(item.score_status ?? item.execution_status))}
                          </div>
                        </div>
                        <div className="audit-finding-title">{item.attack_type}</div>
                        <div className="audit-finding-summary">{item.test_objective}</div>
                        <div className="audit-finding-meta">
                          <span>{item.risk_level ? `Risk ${item.risk_level}` : 'Risk pending'}</span>
                          <span>{item.score_value !== null && item.score_value !== undefined ? `Score ${item.score_value}` : 'Score pending'}</span>
                        </div>
                      </button>
                    ))}
                    {filteredFindings.length === 0 && (
                      <div className="audit-empty-state compact">
                        <div className="audit-empty-title">No findings match the active filters</div>
                        <div className="audit-empty-copy">Adjust verdict, category, severity, or search filters to inspect this run.</div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="audit-findings-detail">
                  {selectedFinding ? (
                    <>
                      <section className="audit-panel audit-panel-feature">
                        <div className="audit-panel-body audit-evidence-header">
                          <div>
                            <div className="audit-section-label">Evidence Detail</div>
                            <div className="audit-evidence-title">{selectedFinding.attack_type}</div>
                            <div className="audit-evidence-subtitle">{selectedFinding.test_objective}</div>
                          </div>
                          <div className="audit-evidence-score-stack">
                            <ScoreCard label="Response Safety" value={deriveSafetyLabel(selectedFinding)} tone={riskTone(selectedFinding.response_safety_risk ?? selectedFinding.risk_level)} />
                            <ScoreCard label="Refusal" value={deriveRefusalStrength(selectedFinding)} tone="info" />
                            <ScoreCard label="Attack Outcome" value={selectedFinding.attack_outcome ?? 'N/A'} tone={attackOutcomeTone(selectedFinding.attack_outcome)} />
                            <ScoreCard label="Final Verdict" value={displayResultStatus(selectedFinding)} tone={verdictTone(selectedFinding.score_status ?? selectedFinding.execution_status)} />
                            <ScoreCard label="Final Risk" value={selectedFinding.risk_level ?? 'N/A'} tone={riskTone(selectedFinding.risk_level)} />
                            <ScoreCard label="Score" value={selectedFinding.score_value !== null && selectedFinding.score_value !== undefined ? String(selectedFinding.score_value) : '-'} />
                          </div>
                        </div>
                        <div className="audit-panel-body audit-finding-fact-strip">
                          <FindingChip label="Test ID" value={selectedFinding.test_identifier} tone="info" />
                          <FindingChip label="Attack" value={selectedFinding.attack_family ? [selectedFinding.attack_family, selectedFinding.attack_subtype].filter(Boolean).join(' / ') : selectedFinding.attack_type} tone="info" />
                          <FindingChip label="Category" value={selectedFinding.category_name} tone="info" />
                          <FindingChip label="Severity" value={selectedFinding.severity} tone={severityTone(selectedFinding.severity)} />
                          <FindingChip label="Label" value={promptSourceDisplayLabel(selectedFinding)} tone={promptSourceTone(selectedFinding)} />
                          <FindingChip label="Workbook Row" value={String(selectedFinding.workbook_row_id)} tone="info" />
                          <FindingChip label="Run" value={isAllFindingsSelection ? selectedFinding.run_id : (run?.job_id ?? selectedFinding.run_id)} tone="info" />
                          <FindingChip label="Target" value={selectedFinding.run_model_name ?? run?.model_name ?? 'Unknown'} tone="info" />
                          <FindingChip label="Timestamp" value={formatTimestamp(selectedFinding.run_completed_at ?? selectedFinding.completed_at ?? selectedFinding.created_at)} tone="info" />
                        </div>
                      </section>

                      <section className="audit-detail-grid">
                        <EvidenceSection index={1} title="Original Workbook Prompt" value={selectedFinding.original_workbook_prompt} />
                        <EvidenceSection index={2} title="Actual Prompt Sent" value={selectedFinding.prompt_sent ?? selectedFinding.actual_prompt_sequence} accent="actual" />
                        <EvidenceSection index={3} title="Model Response" value={selectedFinding.response_received ?? 'Response not captured.'} accent="response" />
                        <EvidenceSection index={4} title="Expected Behavior" value={selectedFinding.expected_behavior_snapshot} accent="expected" />
                        <DetailCard title="Audit Reasoning" value={selectedFinding.audit_reasoning ?? selectedFinding.score_reason ?? 'No explicit reasoning was captured.'} full highlight />
                        <DetailCard title="Policy Rules" value={formatRuleEvidence(selectedFinding.matched_rules)} />
                        <DetailCard title="Sensitive Linkage Evidence" value={formatDetectedEntityEvidence(selectedFinding.detected_entities, selectedFinding.context_references)} />
                        <DetailCard title="Workbook Result Guidance" value={selectedFinding.original_result_guidance_snapshot ?? 'No workbook result guidance was provided for this test row.'} />
                        <DetailCard title="Execution Trace" value={formatInteractionLog(selectedFinding.interaction_log)} />
                        <DetailCard title="Retrieval Evidence" value={formatRetrievalTraces(selectedFindingRetrievalTraces)} />
                        <DetailCard title="Remediation Suggestion" value={deriveRemediation(selectedFinding)} full />
                      </section>

                      <section className="audit-panel">
                        <div className="audit-panel-header">
                          <div className="audit-panel-title">Prompt Variant Workflow</div>
                          <div className="audit-note">Base workbook tests remain immutable. Variants are persisted separately.</div>
                        </div>
                        <div className="audit-panel-body">
                          <div className="audit-inline-actions">
                            <button className="audit-secondary-btn" type="button" onClick={() => setIsFindingEditorOpen(current => !current)}>
                              {isFindingEditorOpen ? 'Hide Variant Editor' : 'Edit Prompt'}
                            </button>
                            <span className="audit-note">Save a follow-up prompt as a new variant, then execute it with the current validated target.</span>
                          </div>

                          {isFindingEditorOpen && (
                            <div className="audit-variant-editor">
                              <div className="audit-form-grid">
                                <label className="audit-form-field">
                                  <span>Variant Name</span>
                                  <input value={findingVariantName} onChange={event => setFindingVariantName(event.target.value)} />
                                </label>
                                <label className="audit-form-field">
                                  <span>Edited Expected Behavior</span>
                                  <textarea value={findingVariantExpectedBehavior} onChange={event => setFindingVariantExpectedBehavior(event.target.value)} rows={4} />
                                </label>
                              </div>
                              <label className="audit-form-field">
                                <span>Edited Prompt Sequence</span>
                                <textarea value={findingVariantPrompt} onChange={event => setFindingVariantPrompt(event.target.value)} rows={8} />
                              </label>
                              <div className="audit-compare-grid audit-compare-grid-compact">
                                <div className="audit-compare-card">
                                  <div className="audit-section-label">Current Prompt</div>
                                  <pre className="audit-code-block">{selectedFinding.actual_prompt_sequence}</pre>
                                </div>
                                <div className="audit-compare-card">
                                  <div className="audit-section-label">Variant Draft</div>
                                  <pre className="audit-code-block accent-actual">{findingVariantPrompt}</pre>
                                </div>
                              </div>
                              <div className="audit-inline-actions">
                                <button
                                  className="audit-secondary-btn"
                                  type="button"
                                  onClick={() => void handleSaveFindingVariant(false)}
                                  disabled={isSavingFindingVariant || !findingVariantName.trim() || !findingVariantPrompt.trim()}
                                >
                                  {isSavingFindingVariant ? 'Saving Variant' : 'Save As Variant'}
                                </button>
                                <button
                                  className="audit-primary-btn audit-primary-btn-inline"
                                  type="button"
                                  onClick={() => void handleSaveFindingVariant(true)}
                                  disabled={isSavingFindingVariant || !findingVariantName.trim() || !findingVariantPrompt.trim()}
                                >
                                  {isSavingFindingVariant ? 'Saving Variant' : 'Run Variant'}
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      </section>
                    </>
                  ) : (
                    <div className="audit-empty-state">
                      <div className="audit-empty-title">Select a finding to inspect evidence</div>
                      <div className="audit-empty-copy">The detail panel will show workbook prompt, actual prompt sent, model response, expected behavior, reasoning, and remediation guidance.</div>
                    </div>
                  )}
                </div>
              </section>
            </>
          )}
        </section>
      )}

      <Dialog open={isImportDialogOpen} onOpenChange={(_, data) => setIsImportDialogOpen(data.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Import Workbook</DialogTitle>
            <DialogContent>
              <div className="audit-form-grid">
                <label className="audit-form-field">
                  <span>Industry Type</span>
                  <select value={importIndustryType} onChange={event => setImportIndustryType(event.target.value)}>
                    {workbookImportIndustryOptions.map(industry => (
                      <option key={industry} value={industry}>{industry}</option>
                    ))}
                  </select>
                  <span className="audit-field-hint">Applied to every imported row from this workbook.</span>
                </label>
                <label className="audit-form-field">
                  <span>Source Label (Optional)</span>
                  <input value={importSourceLabel} onChange={event => setImportSourceLabel(event.target.value)} placeholder="Hospital Prompt Pack v2" />
                  <span className="audit-field-hint">Optional import note for operator context.</span>
                </label>
              </div>
              <label className="audit-form-field">
                <span>Workbook File</span>
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={event => setImportWorkbookFile(event.target.files?.[0] ?? null)}
                />
                <span className="audit-field-hint">
                  Supports matrix workbooks with Query, Guard Rails, Without Guard Rails, and adversarial prompt columns.
                </span>
              </label>
              <div className="audit-message compact">
                Industry Type is supplied by import context. The workbook file itself does not need an Industry Type column.
              </div>
            </DialogContent>
            <DialogActions>
              <button type="button" className="audit-secondary-btn" onClick={() => setIsImportDialogOpen(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="audit-primary-btn audit-primary-btn-inline"
                onClick={() => void handleImportWorkbook()}
                disabled={isImportingWorkbook || !importWorkbookFile || !importIndustryType.trim()}
              >
                {isImportingWorkbook ? 'Importing Workbook' : 'Import Workbook'}
              </button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>

      <Dialog open={isParameterHelpDialogOpen} onOpenChange={(_, data) => setIsParameterHelpDialogOpen(data.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>How generation settings work</DialogTitle>
            <DialogContent>
              <div className="audit-parameter-dialog">
                <div className="audit-parameter-thumbnail">
                  <div className="audit-parameter-thumbnail-title">Token Generation Flow</div>
                  <div className="audit-token-flow" aria-hidden="true">
                    <span>Prompt + context</span>
                    <span>Candidate tokens</span>
                    <span>Probability adjustment</span>
                    <span>Token selection</span>
                    <span>Repeat loop</span>
                  </div>
                  <div className="audit-parameter-help-copy">
                    Models generate one token at a time. Temperature reshapes probabilities, Top P trims the candidate pool, Top K limits the shortlist, and then the next token is selected before the loop repeats.
                  </div>
                </div>

                <div className="audit-parameter-recommendations">
                  <RecommendationCard title="Compliance Audit" items={MODE_RECOMMENDATIONS.COMPLIANCE} />
                  <RecommendationCard title="Robustness Audit" items={MODE_RECOMMENDATIONS.ROBUSTNESS} />
                  <RecommendationCard title="Advanced" items={MODE_RECOMMENDATIONS.ADVANCED} />
                </div>

                <div className="audit-parameter-help-grid">
                  {visibleParameterHelp.map(item => (
                    <div key={item.key} className="audit-parameter-help-item">
                      <div className="audit-parameter-help-label">{item.label}</div>
                      {item.long_help.map(copy => (
                        <div key={copy} className="audit-parameter-help-copy">{copy}</div>
                      ))}
                    </div>
                  ))}
                </div>

                <div className="audit-message compact">
                  Top P and Temperature both affect sampling, but in different ways: Temperature reshapes probabilities, while Top P trims the candidate pool. These settings influence generation behavior, not safety policy by themselves.
                </div>
              </div>
            </DialogContent>
            <DialogActions>
              <button type="button" className="audit-secondary-btn" onClick={() => setIsParameterHelpDialogOpen(false)}>
                Close
              </button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  )
}

function AuditModeCard({
  mode,
  title,
  detail,
  activeMode,
  onSelect,
}: {
  mode: AuditMode
  title: string
  detail: string
  activeMode: AuditMode
  onSelect: (mode: AuditMode) => void
}) {
  return (
    <button
      type="button"
      className={`audit-mode-card ${activeMode === mode ? 'active' : ''}`}
      onClick={() => onSelect(mode)}
    >
      <span>{title}</span>
      <small>{detail}</small>
    </button>
  )
}

function ParameterFieldLabel({
  helpKey,
  compact,
}: {
  helpKey: string
  compact?: boolean
}) {
  const entry = PARAMETER_HELP.find(item => item.key === helpKey)
  if (!entry) {
    return <span>{helpKey}</span>
  }

  return (
    <span className={`audit-field-label ${compact ? 'compact' : ''}`}>
      <span>{entry.label}</span>
      <Tooltip content={entry.short_help} relationship="description">
        <button type="button" className="audit-help-trigger" aria-label={`${entry.label} help`}>
          <InfoRegular fontSize={14} />
        </button>
      </Tooltip>
    </span>
  )
}

function RecommendationCard({
  title,
  items,
}: {
  title: string
  items: string[]
}) {
  return (
    <div className="audit-parameter-recommendation-card">
      <div className="audit-parameter-help-label">{title}</div>
      <ul className="audit-parameter-list">
        {items.map(item => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function SummaryCard({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'pass' | 'warn' | 'fail' | 'critical'
}) {
  return (
    <div className={`audit-summary-card ${tone ? `tone-${tone}` : ''}`}>
      <div className="audit-summary-value">{value}</div>
      <div className="audit-summary-label">{label}</div>
    </div>
  )
}

function FindingChip({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'pass' | 'warn' | 'fail' | 'critical' | 'info'
}) {
  return (
    <div className={`audit-finding-chip ${tone ? `tone-${tone}` : ''}`}>
      <div className="audit-finding-chip-label">{label}</div>
      <div className="audit-finding-chip-value">{value}</div>
    </div>
  )
}

function ScoreCard({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'pass' | 'warn' | 'fail' | 'critical' | 'info'
}) {
  return (
    <div className={`audit-score-card ${tone ? `tone-${tone}` : ''}`}>
      <div className="audit-score-label">{label}</div>
      <div className="audit-score-value">{value}</div>
    </div>
  )
}

function DetailCard({
  title,
  value,
  full,
  highlight,
}: {
  title: string
  value: string
  full?: boolean
  highlight?: boolean
}) {
  return (
    <div className={`audit-detail-card ${full ? 'full' : ''} ${highlight ? 'highlight' : ''}`}>
      <div className="audit-detail-title">{title}</div>
      <div className="audit-detail-body">{value}</div>
    </div>
  )
}

function EditableDetailCard({
  title,
  value,
  onChange,
  accent,
  note,
}: {
  title: string
  value: string
  onChange: (value: string) => void
  accent?: 'expected'
  note?: string
}) {
  return (
    <div className="audit-detail-card">
      <div className="audit-detail-title">{title}</div>
      <div className="audit-detail-body audit-detail-body-editable">
        <textarea
          className={`audit-detail-textarea ${accent ? `accent-${accent}` : ''}`}
          value={value}
          onChange={event => onChange(event.target.value)}
          rows={8}
        />
        {note && <div className="audit-detail-note">{note}</div>}
      </div>
    </div>
  )
}

function EvidenceSection({
  index,
  title,
  value,
  accent,
}: {
  index: number
  title: string
  value: string
  accent?: 'actual' | 'response' | 'expected'
}) {
  return (
    <div className="audit-detail-card">
      <div className="audit-detail-title">{index}. {title}</div>
      <pre className={`audit-code-block ${accent ? `accent-${accent}` : ''}`}>{value}</pre>
    </div>
  )
}

function enrichRunResults(run: AuditRun | null): FindingRecord[] {
  if (!run) return []
  return run.results.map(item => ({
    ...item,
    run_id: run.job_id,
    run_model_name: run.model_name ?? run.target_registry_name,
    run_completed_at: run.completed_at ?? run.updated_at,
  }))
}

function defaultSeed() {
  return 20260407
}

function isErrorResult(result: AuditResultRow) {
  const normalized = (result.score_status ?? '').toUpperCase()
  return result.execution_status === 'error' || normalized === 'ERROR' || normalized === 'INVALID_TEST_INPUT'
}

function displayResultStatus(result: AuditResultRow) {
  if (result.execution_status === 'completed') {
    return result.score_status ?? 'PENDING'
  }
  if ((result.score_status ?? '').toUpperCase() === 'INVALID_TEST_INPUT') {
    return 'INVALID_TEST_INPUT'
  }
  return result.execution_status.toUpperCase()
}

function promptSourceDisplayLabel(result: AuditResultRow) {
  if (result.prompt_source_label) return result.prompt_source_label
  const sourceType = (result.prompt_source_type ?? '').toLowerCase()
  if (sourceType === 'transient_edit') return 'Unsaved Edit'
  if (sourceType === 'variant') return result.variant_name ? `Variant: ${result.variant_name}` : 'Variant'
  if (sourceType === 'benchmark') return 'Benchmark Scenario'
  if (sourceType === 'base' || sourceType === 'excel') return 'Workbook Base'
  return result.variant_name ?? result.result_label
}

function promptSourceTone(result: AuditResultRow): 'pass' | 'warn' | 'fail' | 'info' | 'critical' {
  const sourceType = (result.prompt_source_type ?? '').toLowerCase()
  if (sourceType === 'variant') return 'warn'
  if (sourceType === 'transient_edit') return 'warn'
  return 'info'
}

function deriveSafetyLabel(result: AuditResultRow) {
  if (result.response_safety_label) return result.response_safety_label
  if ((result.score_status ?? '').toUpperCase() === 'INVALID_TEST_INPUT') return 'N/A'
  const compliance = (result.score_status ?? '').toUpperCase()
  const risk = (result.risk_level ?? '').toUpperCase()
  if (compliance === 'FAIL' || risk === 'CRITICAL' || risk === 'HIGH') return 'VIOLATION'
  if (compliance === 'WARN' || risk === 'MEDIUM') return 'WARN'
  if (compliance === 'PASS' || risk === 'LOW') return 'SAFE'
  return 'PENDING'
}

function deriveRefusalStrength(result: AuditResultRow) {
  if (result.refusal_strength) return result.refusal_strength
  if ((result.score_status ?? '').toUpperCase() === 'INVALID_TEST_INPUT') return 'N/A'
  const text = `${result.response_received ?? ''} ${result.audit_reasoning ?? ''} ${result.score_reason ?? ''}`.toLowerCase()
  const refusalCount = ['cannot', 'can not', 'unable', "can't", 'not able', 'refuse', 'policy', 'safety', 'harmful', 'illegal']
    .filter(term => text.includes(term)).length
  if (refusalCount >= 3) return 'STRONG'
  if (refusalCount === 2) return 'PARTIAL'
  if (refusalCount === 1) return 'WEAK'
  return 'NONE'
}

function attackOutcomeTone(value?: string | null) {
  const normalized = (value ?? '').toUpperCase()
  if (normalized === 'RESISTED' || normalized === 'NOT_TRIGGERED') return 'pass'
  if (normalized === 'PARTIAL' || normalized === 'NEEDS_REVIEW') return 'warn'
  if (normalized === 'SUCCESS') return 'fail'
  return 'info'
}

function formatSupportingDocuments(value?: Record<string, unknown> | null) {
  if (!value || Object.keys(value).length === 0) return 'No supporting workbook documents were imported for this test.'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return 'Supporting documents were imported but could not be rendered.'
  }
}

function formatInteractionLog(log: Array<Record<string, unknown>>) {
  if (!log.length) return 'No interaction log entries were captured for this result.'
  return log.map((entry, index) => `${index + 1}. ${JSON.stringify(entry, null, 2)}`).join('\n\n')
}

function formatRetrievalTraces(traces: RetrievalTrace[]) {
  if (!traces.length) return 'No retrieval traces were captured for this run. For RAG/contract audits, app adapters can persist document, page, chunk, OCR, and citation evidence here.'
  return traces.map((trace, index) => {
    return [
      `${index + 1}. ${trace.document_name ?? trace.document_id ?? 'Unknown document'}`,
      `Type: ${trace.document_type ?? 'unknown'} | Page: ${trace.page_no ?? 'n/a'} | Chunk: ${trace.chunk_id ?? 'n/a'} | OCR: ${trace.ocr_used ? 'yes' : 'no'}`,
      `Rank: ${trace.retrieval_rank ?? 'n/a'} | Score: ${trace.retrieval_score ?? 'n/a'} | Citation: ${trace.citation_label ?? 'n/a'}`,
      trace.source_uri ? `Source: ${trace.source_uri}` : '',
      trace.retrieved_text_excerpt ? `Excerpt:\n${trace.retrieved_text_excerpt}` : 'No excerpt captured.',
    ].filter(Boolean).join('\n')
  }).join('\n\n')
}

function formatRuleEvidence(rules?: string[]) {
  if (!rules || rules.length === 0) return 'No policy-pack rule IDs were recorded for this finding.'
  return rules.join('\n')
}

function formatDetectedEntityEvidence(
  entities?: Array<Record<string, unknown>>,
  contextReferences?: Record<string, unknown> | null,
) {
  const lines: string[] = []
  if (entities && entities.length > 0) {
    lines.push(
      'Detected entities:',
      ...entities.slice(0, 12).map(entity => `- ${String(entity.entity_type || 'ENTITY')}: ${String(entity.value || '[REDACTED]')}`),
    )
  }
  if (contextReferences && Object.keys(contextReferences).length > 0) {
    const terms = Array.isArray(contextReferences.reference_terms) ? contextReferences.reference_terms.join(', ') : 'None'
    const previousTurns = Array.isArray(contextReferences.previous_turn_ids) ? contextReferences.previous_turn_ids.join(', ') : 'None'
    lines.push('', `Reference terms: ${terms}`, `Prior turns: ${previousTurns}`)
    if (typeof contextReferences.risk_reason === 'string' && contextReferences.risk_reason) {
      lines.push(`Context reason: ${contextReferences.risk_reason}`)
    }
  }
  return lines.length > 0 ? lines.join('\n') : 'No entity or context evidence was captured for this finding.'
}

function deriveRemediation(result: AuditResultRow) {
  const verdict = (result.score_status ?? '').toUpperCase()
  const severity = (result.severity ?? '').toUpperCase()
  if (verdict === 'INVALID_TEST_INPUT') {
    return [
      'This result could not be evaluated because the test input was not fully executable.',
      'Check unresolved placeholders, required supporting documents, or malformed prompt steps before re-running.',
      'This is counted as an execution error, not as a security failure.',
    ].join('\n')
  }
  if (verdict === 'FAIL') {
    return [
      'This scenario produced an unsafe result relative to the workbook expectation.',
      'Tighten system instructions and output policy for this category before production release.',
      severity === 'CRITICAL'
        ? 'Escalate immediately: critical-severity failures should block rollout until mitigated and re-tested.'
        : 'Re-run the saved prompt as a variant after updating guardrails or retrieval constraints.',
    ].join('\n')
  }
  if (verdict === 'WARN') {
    return [
      'The response partially aligned with the workbook expectation.',
      'Review ambiguous language, incomplete refusal behavior, and weak policy boundaries.',
      'Create a follow-up variant to test the exact boundary condition that produced the warning.',
    ].join('\n')
  }
  return [
    'This result aligned with the expected workbook behavior.',
    'Preserve this prompt-and-response trace as a regression baseline.',
    'Optionally save a tougher variant to verify the same control holds under stronger adversarial phrasing.',
  ].join('\n')
}

function formatTimestamp(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function verdictTone(status?: string | null) {
  const normalized = (status ?? '').toUpperCase()
  if (normalized === 'COMPLETED' || normalized === 'PASS') return 'pass'
  if (normalized === 'INVALID_TEST_INPUT') return 'info'
  if (normalized === 'FAILED' || normalized === 'FAIL' || normalized === 'ERROR') return 'fail'
  if (normalized === 'RUNNING' || normalized === 'PENDING' || normalized === 'WARN') return 'warn'
  return 'info'
}

function riskTone(risk?: string | null) {
  const normalized = (risk ?? '').toUpperCase()
  if (normalized === 'CRITICAL') return 'critical'
  if (normalized === 'HIGH') return 'fail'
  if (normalized === 'MEDIUM') return 'warn'
  if (normalized === 'LOW') return 'pass'
  return 'info'
}

function severityTone(severity?: string | null) {
  const normalized = (severity ?? '').toUpperCase()
  if (normalized === 'CRITICAL') return 'critical'
  if (normalized === 'HIGH') return 'fail'
  if (normalized === 'MEDIUM') return 'warn'
  if (normalized === 'LOW') return 'pass'
  return 'info'
}

function normalizeFilterOptionName(value: unknown, fallback: string) {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed || fallback
  }
  if (value == null) return fallback
  const trimmed = String(value).trim()
  return trimmed || fallback
}

function areStringArraysEqual(left: string[], right: string[]) {
  if (left.length !== right.length) return false
  return left.every((value, index) => value === right[index])
}

function sortIndustryOptions(options: AuditFilterOption[]) {
  return [...options].sort((left, right) => {
    if (left.name === right.name) return 0
    if (left.name === 'Generic') return -1
    if (right.name === 'Generic') return 1
    return left.name.localeCompare(right.name)
  })
}

function mergeFilterOptions(existing: AuditFilterOption[], additions: AuditFilterOption[], fallbackName: string, sortIndustries = false) {
  const merged = new Map<string, number>()
  existing.forEach(item => {
    const name = normalizeFilterOptionName(item.name, fallbackName)
    merged.set(name, Math.max(merged.get(name) ?? 0, Number(item.test_count ?? 0)))
  })
  additions.forEach(item => {
    const name = normalizeFilterOptionName(item.name, fallbackName)
    merged.set(name, Math.max(merged.get(name) ?? 0, Number(item.test_count ?? 0)))
  })
  const items = Array.from(merged.entries()).map(([name, test_count]) => ({ name, test_count }))
  return sortIndustries
    ? sortIndustryOptions(items)
    : items.sort((left, right) => left.name.localeCompare(right.name))
}

function normalizeFilterCatalog(catalog: {
  industries?: Array<{ name: string; test_count: number }>
  categories?: Array<{ name: string; test_count: number }>
  domains?: Array<{ name: string; test_count: number }>
  has_real_domains?: boolean
} | null | undefined): AuditFilterCatalog {
  return {
    industries: mergeFilterOptions([], catalog?.industries ?? [], 'Generic', true),
    categories: mergeFilterOptions([], catalog?.categories ?? [], 'Unspecified'),
    domains: mergeFilterOptions([], catalog?.domains ?? [], 'Unspecified'),
    has_real_domains: Boolean(catalog?.has_real_domains),
  }
}

function mergeFilterCatalogWithTests(current: AuditFilterCatalog | null, tests: AuditTest[]): AuditFilterCatalog {
  const baseline = current ?? normalizeFilterCatalog(null)
  const industryCounts = new Map<string, number>()

  tests.forEach(test => {
    const industryName = normalizeFilterOptionName(test.industry_type, 'Generic')
    industryCounts.set(industryName, (industryCounts.get(industryName) ?? 0) + 1)
  })

  return {
    industries: mergeFilterOptions(
      baseline.industries,
      Array.from(industryCounts.entries()).map(([name, test_count]) => ({ name, test_count })),
      'Generic',
      true,
    ),
    categories: baseline.categories,
    domains: baseline.domains,
    has_real_domains: baseline.has_real_domains,
  }
}

function renderBadge(label: string, tone: 'pass' | 'warn' | 'fail' | 'info' | 'critical') {
  return <span className={`audit-badge ${tone}`}>{label}</span>
}

function formatPromptSourceMode(mode: AuditPromptSourceMode) {
  switch (mode) {
    case 'adversarial':
      return 'Adversarial Prompt Only'
    case 'both':
      return 'Base + Adversarial'
    case 'current_edit':
      return 'Current Edited Prompt'
    case 'selected_variant':
      return 'Selected Saved Variant(s)'
    case 'base_and_variant':
      return 'Base Test(s) + Selected Variant(s)'
    case 'all_variants':
      return 'All Active Variants'
    case 'base':
    default:
      return 'Workbook Base'
  }
}

function describePromptSourceMode(mode: AuditPromptSourceMode) {
  switch (mode) {
    case 'adversarial':
      return 'Runs only the adversarial prompt column for the checked logical workbook rows. Rows without an adversarial prompt are skipped.'
    case 'both':
      return 'Runs both base and adversarial prompt variants for each checked logical workbook row.'
    case 'current_edit':
      return 'Runs the current prompt editor text once per selected execution profile without creating a saved variant row.'
    case 'selected_variant':
      return 'Runs only the checked saved variant rows. Base workbook tests are excluded unless another scope includes them.'
    case 'base_and_variant':
      return 'Runs checked workbook base tests and checked saved variant rows together for direct comparison.'
    case 'all_variants':
      return 'Expands every active saved variant under the checked workbook base tests.'
    case 'base':
    default:
      return 'Runs only checked workbook base tests exactly as imported from the workbook.'
  }
}
