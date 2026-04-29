import { useEffect, useMemo, useState } from 'react'
import type { ViewName } from '../Sidebar/Navigation'
import { auditApi, targetsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type {
  AuditExecutionProfileRequest,
  BenchmarkCompareResponse,
  BenchmarkLibraryResponse,
  BenchmarkMedia,
  BenchmarkScenario,
  TargetInstance,
} from '../../types'
import AuditSpecWorkbench from './AuditSpecWorkbench'
import './auditPlatform.css'

type BenchmarkTab = 'public_json' | 'internal_pack' | 'imported_pack' | 'gif_case' | 'auditspec'
type ReplayMode = 'COMPLIANCE' | 'ROBUSTNESS' | 'ADVANCED'

const TABS: Array<{ code: BenchmarkTab; label: string; description: string }> = [
  { code: 'public_json', label: 'Public Benchmarks', description: 'Public reference artifacts such as FlipAttack-style result JSONs.' },
  { code: 'internal_pack', label: 'My Packs', description: 'Reusable internal scenario packs curated by auditors.' },
  { code: 'imported_pack', label: 'Imported Packs', description: 'Imported benchmark packs normalized into SQLite.' },
  { code: 'gif_case', label: 'Case Study Gallery', description: 'Visual explainers and GIF/image case studies.' },
  { code: 'auditspec', label: 'AuditSpec', description: 'AuditSpec suites, optional promptfoo runtime, reusable benchmark definitions, and comparison-oriented execution under one library workspace.' },
]

const REFERENCE_NOTICE = 'Public benchmark reference data; not client evidence.'

const HOSPITAL_BENCHMARK_EXAMPLES = [
  'Patient ID + diagnosis leakage',
  'Patient ID + location follow-up',
  'Address list disclosure',
  'Prompt-claimed doctor/admin/auditor',
  'Medication advice boundary',
  'Safe refusal',
  'Public medical statistics',
]

interface BenchmarkLibraryPageProps {
  onOpenRun?: (runId: string) => void
  onNavigate?: (view: ViewName) => void
}

export default function BenchmarkLibraryPage({ onOpenRun, onNavigate }: BenchmarkLibraryPageProps) {
  const [activeTab, setActiveTab] = useState<BenchmarkTab>('public_json')
  const [library, setLibrary] = useState<BenchmarkLibraryResponse | null>(null)
  const [selectedScenario, setSelectedScenario] = useState<BenchmarkScenario | null>(null)
  const [compare, setCompare] = useState<BenchmarkCompareResponse | null>(null)
  const [targets, setTargets] = useState<TargetInstance[]>([])
  const [selectedTarget, setSelectedTarget] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [search, setSearch] = useState('')
  const [replayMode, setReplayMode] = useState<ReplayMode>('COMPLIANCE')
  const [runCount, setRunCount] = useState(1)
  const [temperature, setTemperature] = useState(0)
  const [importJson, setImportJson] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadTargets = async () => {
      try {
        const response = await targetsApi.listTargets(200)
        setTargets(response.items)
        const active = response.items.find(item => item.is_active) ?? response.items[0]
        setSelectedTarget(active?.target_registry_name ?? '')
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }
    void loadTargets()
  }, [])

  useEffect(() => {
    const load = async () => {
      if (activeTab === 'auditspec') {
        setLibrary(null)
        setSelectedScenario(null)
        return
      }
      try {
        const response = await auditApi.getBenchmarkLibrary({
          source_type: activeTab,
          category: categoryFilter || undefined,
          search: search || undefined,
        })
        setLibrary(response)
        setSelectedScenario(previous => {
          if (previous && response.scenarios.some(item => item.id === previous.id)) return previous
          return response.scenarios[0] ?? null
        })
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }
    void load()
  }, [activeTab, categoryFilter, search])

  useEffect(() => {
    const loadCompare = async () => {
      if (activeTab === 'auditspec') {
        setCompare(null)
        return
      }
      if (!selectedScenario) {
        setCompare(null)
        return
      }
      try {
        setCompare(await auditApi.compareBenchmarkScenario(selectedScenario.id))
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }
    void loadCompare()
  }, [selectedScenario])

  useEffect(() => {
    if (replayMode === 'COMPLIANCE') {
      setRunCount(1)
      setTemperature(0)
    } else if (replayMode === 'ROBUSTNESS') {
      setRunCount(count => Math.max(count, 5))
      setTemperature(0.7)
    }
  }, [replayMode])

  const tabInfo = TABS.find(item => item.code === activeTab) ?? TABS[0]
  const taxonomy = library?.taxonomy ?? []
  const scenarios = library?.scenarios ?? []
  const media = library?.media ?? []

  const mediaForTab = useMemo(() => {
    if (activeTab === 'gif_case') return media
    if (!selectedScenario) return media.slice(0, 6)
    return media.filter(item => item.scenario_id === selectedScenario.id).slice(0, 6)
  }, [activeTab, media, selectedScenario])

  async function refresh() {
    setLibrary(await auditApi.getBenchmarkLibrary({
      source_type: activeTab,
      category: categoryFilter || undefined,
      search: search || undefined,
    }))
  }

  async function importPack() {
    setBusy(true)
    setError(null)
    try {
      const parsed = JSON.parse(importJson) as Record<string, unknown>
      await auditApi.importFlipAttackBenchmark({ payload: parsed, source_type: activeTab })
      setImportJson('')
      setShowImport(false)
      await refresh()
    } catch (err) {
      setError(err instanceof SyntaxError ? 'Invalid JSON import payload.' : toApiError(err).detail)
    } finally {
      setBusy(false)
    }
  }

  async function replayScenario() {
    if (!selectedScenario || !selectedTarget) return
    setBusy(true)
    setError(null)
    try {
      const run = await auditApi.replayBenchmarkScenario(selectedScenario.id, {
        target_registry_name: selectedTarget,
        execution_profile: buildExecutionProfile(replayMode, runCount, temperature),
      })
      onOpenRun?.(run.job_id)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="audit-platform audit-benchmark-shell">
      <section className="audit-hero audit-hero-compact">
        <div>
          <div className="audit-hero-title">Benchmark Library</div>
          <div className="audit-hero-subtitle">
            Benchmark Library stores reusable test definitions. Evidence Center stores proof after execution. {REFERENCE_NOTICE}
          </div>
        </div>
        <div className="audit-hero-meta audit-hero-meta-row">
          <div className="audit-meta-card"><div className="audit-meta-label">Data Source</div><div className="audit-meta-value">SQLite</div></div>
          <div className="audit-meta-card"><div className="audit-meta-label">Active Tab</div><div className="audit-meta-value">{tabInfo.label}</div></div>
        </div>
      </section>

      {error && <div className="audit-message error">{error}</div>}

      <section className="audit-panel">
        <div className="audit-panel-header">
          <div>
            <div className="audit-panel-title">What this page does</div>
            <div className="audit-note">
              Benchmark Library stores reusable test definitions. Evidence Center stores proof after execution.
            </div>
          </div>
        </div>
        <div className="audit-panel-body">
          <div className="audit-message compact">
            AuditSpec is SpriCO-native YAML/JSON for repeatable suites, assertions, and comparisons.
          </div>
          <div className="audit-message compact">
            Promptfoo Runtime optionally runs promptfoo plugins, strategies, and custom policies. Results are imported as evidence. SpriCO PolicyDecisionEngine remains final verdict authority.
          </div>
          <div className="audit-message compact">
            Hospital benchmark examples use synthetic prompts only and should not contain real patient IDs, names, or addresses.
          </div>
          <div className="audit-chip-row" aria-label="Hospital benchmark examples">
            {HOSPITAL_BENCHMARK_EXAMPLES.map(example => (
              <span key={example} className="audit-badge info">{example}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="audit-panel">
        <div className="audit-panel-body audit-benchmark-tabs">
          {TABS.map(tab => (
            <button
              key={tab.code}
              type="button"
              className={`audit-mode-card ${activeTab === tab.code ? 'selected' : ''}`}
              onClick={() => {
                setActiveTab(tab.code)
                setCategoryFilter('')
              }}
            >
              <strong>{tab.label}</strong>
              <span>{tab.description}</span>
            </button>
          ))}
        </div>
      </section>

      {activeTab === 'auditspec' && (
        <AuditSpecWorkbench onOpenRun={onOpenRun} onNavigate={onNavigate} />
      )}

      {activeTab !== 'auditspec' && (
      <section className="audit-benchmark-layout">
        <aside className="audit-panel audit-benchmark-taxonomy">
          <div className="audit-panel-header">
            <div>
              <div className="audit-panel-title">Benchmark Taxonomy</div>
              <div className="audit-note">Category / subcategory filters from imported benchmark scenarios.</div>
            </div>
          </div>
          <div className="audit-panel-body audit-benchmark-tree">
            <button type="button" className={`audit-tree-item ${categoryFilter === '' ? 'selected' : ''}`} onClick={() => setCategoryFilter('')}>
              All categories
            </button>
            {taxonomy.map(item => (
              <button
                type="button"
                key={`${item.category_name}-${item.subcategory_name ?? 'root'}`}
                className={`audit-tree-item ${categoryFilter === item.category_name ? 'selected' : ''}`}
                onClick={() => setCategoryFilter(item.category_name)}
              >
                <strong>{item.category_name}</strong>
                <span>{item.subcategory_name ?? 'All'} | {item.scenario_count} scenario(s)</span>
              </button>
            ))}
            {taxonomy.length === 0 && <div className="audit-muted">No benchmark taxonomy has been imported yet.</div>}
          </div>
        </aside>

        <main className="audit-benchmark-main">
          <section className="audit-panel">
            <div className="audit-panel-header">
              <div>
                <div className="audit-panel-title">{tabInfo.label}</div>
                <div className="audit-note">{tabInfo.description}</div>
              </div>
              <button type="button" className="audit-secondary-btn" onClick={() => setShowImport(value => !value)}>
                {showImport ? 'Close Import' : 'Import JSON Pack'}
              </button>
            </div>
            <div className="audit-panel-body audit-benchmark-controls">
              <label className="audit-form-field">
                <span>Search</span>
                <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search scenario, code, objective, prompt..." />
              </label>
              <label className="audit-form-field">
                <span>Replay Target</span>
                <select value={selectedTarget} onChange={event => setSelectedTarget(event.target.value)}>
                  <option value="">Select target</option>
                  {targets.map(target => (
                    <option key={target.target_registry_name} value={target.target_registry_name}>
                      {target.display_name ?? target.model_name ?? target.target_registry_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="audit-form-field">
                <span>Replay Mode</span>
                <select value={replayMode} onChange={event => setReplayMode(event.target.value as ReplayMode)}>
                  <option value="COMPLIANCE">Compliance</option>
                  <option value="ROBUSTNESS">Robustness</option>
                  <option value="ADVANCED">Advanced</option>
                </select>
              </label>
              <label className="audit-form-field">
                <span>Runs</span>
                <input type="number" min={1} max={25} value={runCount} onChange={event => setRunCount(Number(event.target.value) || 1)} />
              </label>
              <label className="audit-form-field">
                <span>Temperature</span>
                <input type="number" min={0} max={2} step={0.1} value={temperature} onChange={event => setTemperature(Number(event.target.value) || 0)} />
              </label>
            </div>
            {showImport && (
              <div className="audit-panel-body audit-benchmark-import">
                <div className="audit-message compact">
                  Paste a normalized benchmark pack JSON with <code>source</code>, <code>scenarios</code>, and optional <code>media</code>. Public references remain labeled as reference data.
                </div>
                <textarea value={importJson} onChange={event => setImportJson(event.target.value)} placeholder={importPlaceholder(activeTab)} />
                <button type="button" className="audit-primary-btn" onClick={() => void importPack()} disabled={busy || !importJson.trim()}>
                  {busy ? 'Importing...' : 'Import Pack'}
                </button>
              </div>
            )}
          </section>

          {activeTab === 'gif_case' ? (
            <CaseGallery media={mediaForTab} onReplayScenario={(scenarioId) => {
              const scenario = scenarios.find(item => item.id === scenarioId)
              if (scenario) setSelectedScenario(scenario)
            }} />
          ) : (
            <section className="audit-panel">
              <div className="audit-panel-header">
                <div className="audit-panel-title">Scenario Library</div>
                <div className="audit-note">{scenarios.length} scenario(s). Rows are benchmark references, not client evidence.</div>
              </div>
              <div className="audit-panel-body audit-table-wrap">
                <table className="audit-table audit-table-dense">
                  <thead>
                    <tr>
                      <th>Scenario</th>
                      <th>Category</th>
                      <th>Modality</th>
                      <th>Severity</th>
                      <th>Replay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scenarios.map(scenario => (
                      <tr key={scenario.id} className={`is-clickable ${selectedScenario?.id === scenario.id ? 'selected' : ''}`} onClick={() => setSelectedScenario(scenario)}>
                        <td>
                          <div className="audit-code-cell">{scenario.scenario_code}</div>
                          <div className="audit-test-name">{scenario.title}</div>
                          <div className="audit-test-objective">{scenario.objective_text ?? scenario.source_title ?? 'No objective text provided.'}</div>
                        </td>
                        <td>{scenario.category_name}{scenario.subcategory_name ? ` / ${scenario.subcategory_name}` : ''}</td>
                        <td>{renderBadge(scenario.modality, 'info')}</td>
                        <td>{renderBadge(scenario.severity_hint ?? 'N/A', severityTone(scenario.severity_hint))}</td>
                        <td>{scenario.replay_supported ? renderBadge('Supported', 'pass') : renderBadge('Reference Only', 'warn')}</td>
                      </tr>
                    ))}
                    {scenarios.length === 0 && <tr><td colSpan={5} className="audit-muted">No scenarios are available for this tab/filter yet.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="audit-benchmark-detail-grid">
            <ScenarioDetail scenario={selectedScenario} compare={compare} />
            <section className="audit-panel audit-panel-feature">
              <div className="audit-panel-header">
                <div>
                  <div className="audit-panel-title">Compare And Replay</div>
                  <div className="audit-note">Replay clones the selected public reference scenario into a structured audit run.</div>
                </div>
              </div>
              <div className="audit-panel-body audit-benchmark-replay">
                <DetailLine label="Selected Scenario" value={selectedScenario?.title ?? 'None'} />
                <DetailLine label="Target" value={targets.find(item => item.target_registry_name === selectedTarget)?.display_name ?? (selectedTarget || 'None')} />
                <DetailLine label="Mode" value={`${replayMode} | ${runCount} run(s) | temp ${temperature}`} />
                <DetailLine label="Delta" value={compare?.delta ?? 'Select a scenario to compare public reference and client replay results.'} />
                <button
                  type="button"
                  className="audit-primary-btn"
                  onClick={() => void replayScenario()}
                  disabled={busy || !selectedScenario?.replay_supported || !selectedTarget}
                >
                  {busy ? 'Starting Replay...' : 'Replay Scenario'}
                </button>
              </div>
            </section>
          </section>
        </main>
      </section>
      )}
    </div>
  )
}

function ScenarioDetail({ scenario, compare }: { scenario: BenchmarkScenario | null; compare: BenchmarkCompareResponse | null }) {
  if (!scenario) {
    return (
      <section className="audit-panel">
        <div className="audit-panel-header"><div className="audit-panel-title">Scenario Detail</div></div>
        <div className="audit-panel-body audit-muted">Select a benchmark scenario to inspect reference data, prompt text, expected behavior, and replay comparison.</div>
      </section>
    )
  }
  return (
    <section className="audit-panel">
      <div className="audit-panel-header">
        <div>
          <div className="audit-panel-title">{scenario.title}</div>
          <div className="audit-note">{scenario.source_name ?? 'Benchmark source'} | {REFERENCE_NOTICE}</div>
        </div>
        {renderBadge(scenario.replay_supported ? 'Replayable' : 'Reference Only', scenario.replay_supported ? 'pass' : 'warn')}
      </div>
      <div className="audit-panel-body audit-detail-grid">
        <DetailBlock title="Scenario Objective" value={scenario.objective_text ?? 'No objective text provided.'} />
        <DetailBlock title="Public Reference Metadata" value={JSON.stringify(compare?.public_model_result ?? scenario.source_metadata ?? {}, null, 2)} />
        <DetailBlock title="Prompt Text" value={scenario.prompt_text ?? 'No replayable prompt stored for this scenario.'} code />
        <DetailBlock title="Expected Behavior" value={scenario.expected_behavior_text ?? 'No expected behavior provided by the benchmark source.'} code />
      </div>
      <div className="audit-panel-body">
        <div className="audit-panel-title">Client Replay Results</div>
        <div className="audit-note">{compare?.client_target_results.length ?? 0} replay result(s) found for this scenario.</div>
      </div>
    </section>
  )
}

function CaseGallery({ media, onReplayScenario }: { media: BenchmarkMedia[]; onReplayScenario: (scenarioId: number) => void }) {
  return (
    <section className="audit-panel">
      <div className="audit-panel-header">
        <div>
          <div className="audit-panel-title">Case Study Gallery</div>
          <div className="audit-note">GIF/image/video assets are visual explainers only unless replayable scenario text is attached.</div>
        </div>
      </div>
      <div className="audit-panel-body audit-benchmark-gallery">
        {media.map(item => (
          <article key={item.id} className="audit-benchmark-media-card">
            {item.media_type === 'gif' || item.media_type === 'image' ? (
              <img src={item.thumbnail_uri ?? item.media_uri} alt={item.caption ?? item.scenario_title ?? item.source_name ?? 'Benchmark media'} />
            ) : (
              <div className="audit-benchmark-media-placeholder">{item.media_type.toUpperCase()}</div>
            )}
            <div className="audit-help-title">{item.scenario_title ?? item.source_name ?? 'Case Study'}</div>
            <div className="audit-help-copy"><strong>Category:</strong> {item.category_name ?? 'Unspecified'}</div>
            <div className="audit-help-copy"><strong>Why this matters:</strong> {item.caption ?? item.objective_text ?? REFERENCE_NOTICE}</div>
            {item.scenario_id && (
              <button type="button" className="audit-secondary-btn audit-secondary-btn-small" onClick={() => onReplayScenario(item.scenario_id!)}>
                Select For Replay
              </button>
            )}
          </article>
        ))}
        {media.length === 0 && <div className="audit-muted">No case study media has been imported yet.</div>}
      </div>
    </section>
  )
}

function DetailBlock({ title, value, code = false }: { title: string; value: string; code?: boolean }) {
  return (
    <div className="audit-code-panel">
      <div className="audit-code-title">{title}</div>
      <pre className={code ? undefined : 'audit-text-block'}>{value}</pre>
    </div>
  )
}

function DetailLine({ label, value }: { label: string; value: string }) {
  return <div className="audit-detail-line"><span>{label}</span><strong>{value}</strong></div>
}

function renderBadge(label: string, tone: 'pass' | 'warn' | 'fail' | 'info' | 'critical') {
  return <span className={`audit-badge ${tone}`}>{label}</span>
}

function severityTone(severity?: string | null): 'pass' | 'warn' | 'fail' | 'info' | 'critical' {
  const value = (severity ?? '').toUpperCase()
  if (value === 'CRITICAL') return 'critical'
  if (value === 'HIGH') return 'fail'
  if (value === 'MEDIUM') return 'warn'
  if (value === 'LOW') return 'pass'
  return 'info'
}

function buildExecutionProfile(mode: ReplayMode, runCount: number, temperature: number): AuditExecutionProfileRequest {
  return {
    mode_code: mode,
    temperature,
    top_p: 1,
    fixed_seed: mode === 'COMPLIANCE',
    base_seed: mode === 'COMPLIANCE' ? 20260407 : undefined,
    seed_strategy: mode === 'ROBUSTNESS' ? 'PER_RUN_RANDOM' : mode === 'ADVANCED' ? 'SEQUENTIAL' : 'FIXED',
    run_count_requested: Math.max(1, Math.min(25, runCount)),
    variability_mode: mode !== 'COMPLIANCE',
    created_by: 'benchmark-library',
  }
}

function importPlaceholder(activeTab: BenchmarkTab) {
  return JSON.stringify({
    source: {
      source_name: 'FlipAttack Reference Pack',
      source_type: activeTab,
      benchmark_family: 'FlipAttack',
      title: 'Public FlipAttack-style scenarios',
      description: REFERENCE_NOTICE,
      metadata: { reference_data_notice: REFERENCE_NOTICE },
    },
    scenarios: [
      {
        scenario_code: 'flipattack-001',
        title: 'Reference prompt transformation case',
        category_name: 'Jailbreak',
        objective_text: 'Replay a public benchmark scenario against a selected client target.',
        prompt_text: 'Paste public benchmark prompt text here.',
        expected_behavior_text: 'Target should follow applicable safety policy and avoid unsafe completion.',
        modality: 'text',
        recommended_target_types: ['OpenAIChatTarget', 'HTTP_TARGET', 'CUSTOM_TARGET'],
        tags: ['public-reference'],
        severity_hint: 'HIGH',
        replay_supported: true,
      },
    ],
    media: [],
  }, null, 2)
}
