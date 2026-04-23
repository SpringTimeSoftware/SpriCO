import { useEffect, useMemo, useState } from 'react'
import { auditApi, targetsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { AuditPromptSourceMode, AuditTest, AuditVariant, TargetInstance } from '../../types'
import './auditPlatform.css'

interface PromptVariantsPageProps {
  onOpenRun: (runId: string) => void
}

export default function PromptVariantsPage({ onOpenRun }: PromptVariantsPageProps) {
  const [tests, setTests] = useState<AuditTest[]>([])
  const [targets, setTargets] = useState<TargetInstance[]>([])
  const [selectedTarget, setSelectedTarget] = useState('')
  const [selectedTest, setSelectedTest] = useState<AuditTest | null>(null)
  const [selectedVariant, setSelectedVariant] = useState<AuditVariant | null>(null)
  const [executionScope, setExecutionScope] = useState<AuditPromptSourceMode>('selected_variant')
  const [variantName, setVariantName] = useState('')
  const [variantPrompt, setVariantPrompt] = useState('')
  const [variantExpectedBehavior, setVariantExpectedBehavior] = useState('')
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const auditableTargets = useMemo(
    () => targets.filter(target => target.target_type !== 'TextTarget' && Boolean(target.endpoint) && Boolean(target.model_name)),
    [targets],
  )

  const flatVariants = useMemo(
    () => tests.flatMap(test => test.variants.map(variant => ({ ...variant, parent: test }))),
    [tests],
  )

  const filteredTests = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return tests
    return tests.filter(test => {
      const haystack = [
        test.test_identifier,
        test.attack_type,
        test.test_objective,
        test.category_name,
      ].join(' ').toLowerCase()
      return haystack.includes(query)
    })
  }, [search, tests])

  const selectedTargetInfo = useMemo(
    () => auditableTargets.find(target => target.target_registry_name === selectedTarget) ?? null,
    [auditableTargets, selectedTarget],
  )

  useEffect(() => {
    const load = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const [testResponse, targetResponse] = await Promise.all([
          auditApi.listTests(),
          targetsApi.listTargets(),
        ])
        setTests(testResponse.tests)
        setTargets(targetResponse.items)
        const defaultTarget = targetResponse.items.find(
          target => target.is_active && target.target_type !== 'TextTarget' && Boolean(target.endpoint) && Boolean(target.model_name),
        ) ?? targetResponse.items.find(
          target => target.target_type !== 'TextTarget' && Boolean(target.endpoint) && Boolean(target.model_name),
        )
        setSelectedTarget(defaultTarget?.target_registry_name ?? '')
        setSelectedTest(testResponse.tests[0] ?? null)
      } catch (err) {
        setError(toApiError(err).detail)
      } finally {
        setIsLoading(false)
      }
    }
    void load()
  }, [])

  useEffect(() => {
    if (!selectedTest) {
      setVariantName('')
      setVariantPrompt('')
      setVariantExpectedBehavior('')
      setSelectedVariant(null)
      return
    }
    setVariantName(`${selectedTest.attack_type} Variant`)
    setVariantPrompt(selectedTest.prompt_sequence)
    setVariantExpectedBehavior(selectedTest.expected_behavior)
    setSelectedVariant(selectedTest.variants[0] ?? null)
  }, [selectedTest])

  async function refreshTests(testId?: number, variantId?: number) {
    const refreshed = await auditApi.listTests()
    setTests(refreshed.tests)
    const nextTest = refreshed.tests.find(test => test.id === (testId ?? selectedTest?.id)) ?? refreshed.tests[0] ?? null
    setSelectedTest(nextTest)
    if (variantId && nextTest) {
      setSelectedVariant(nextTest.variants.find(item => item.id === variantId) ?? nextTest.variants[0] ?? null)
    }
  }

  async function handleSaveVariant() {
    if (!selectedTest) return
    setIsSaving(true)
    setError(null)
    try {
      const created = await auditApi.createVariant(selectedTest.id, {
        variant_name: variantName,
        edited_prompt_sequence: variantPrompt,
        edited_expected_behavior: variantExpectedBehavior,
        created_by: 'Auditor',
      })
      await refreshTests(selectedTest.id, created.id)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsSaving(false)
    }
  }

  async function handleRunVariant(variant: AuditVariant | null) {
    if (!variant) {
      setError('Select a saved variant before executing it.')
      return
    }
    if (!selectedTarget) {
      setError('Select a validated target before running a prompt variant.')
      return
    }
    setIsRunning(true)
    setError(null)
    try {
      const run = await auditApi.createRun({
        categories: [],
        domains: [],
        test_ids: executionScope === 'base_and_variant' && selectedTest ? [selectedTest.id] : [],
        variant_ids: [variant.id],
        prompt_source_mode: executionScope,
        transient_prompt_sequence: null,
        transient_expected_behavior: null,
        selected_test_id_for_transient_run: null,
        target_registry_name: selectedTarget,
        allow_text_target: false,
      })
      onOpenRun(run.job_id)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsRunning(false)
    }
  }

  const testsWithVariantsCount = tests.filter(test => test.variants.length > 0).length

  if (isLoading) {
    return <div className="audit-platform"><div className="audit-message">Loading saved prompt variants from SQLite...</div></div>
  }

  return (
    <div className="audit-platform audit-variant-shell">
      <section className="audit-analyst-header audit-variant-header">
        <div className="audit-analyst-brand">
          <div className="audit-analyst-mark">Pv</div>
          <div>
            <div className="audit-analyst-title">Prompt Variants</div>
            <div className="audit-analyst-subtitle">
              Create workbook-derived prompt variants, compare them against the immutable base test, and run saved variants against a validated target.
            </div>
          </div>
        </div>
        <div className="audit-analyst-meta">
          <div className="audit-analyst-chip"><span>Variants</span><strong>{flatVariants.length}</strong></div>
          <div className="audit-analyst-chip"><span>Tests with Variants</span><strong>{testsWithVariantsCount}</strong></div>
          <div className="audit-analyst-chip"><span>Target</span><strong>{selectedTargetInfo?.model_name ?? 'Unset'}</strong></div>
        </div>
      </section>

      {error && <div className="audit-message error">{error}</div>}

      <section className="audit-variant-layout">
        <div className="audit-panel">
          <div className="audit-panel-header">
            <div className="audit-panel-title">Workbook Test Library</div>
            <div className="audit-note">{filteredTests.length} tests</div>
          </div>
          <div className="audit-panel-body">
            <label className="audit-form-field">
              <span>Search Tests</span>
              <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search workbook tests..." />
            </label>
          </div>
          <div className="audit-panel-body audit-findings-list audit-variant-test-list">
            {filteredTests.map(test => (
              <button
                key={test.id}
                type="button"
                className={`audit-finding-row ${selectedTest?.id === test.id ? 'selected' : ''}`}
                onClick={() => setSelectedTest(test)}
              >
                <div className="audit-finding-row-top">
                  <span className="audit-code-cell">{test.test_identifier}</span>
                  <div className="audit-finding-badge-stack">
                    {renderBadge(test.category_name, 'info')}
                    {renderBadge(test.severity, severityTone(test.severity))}
                    {renderBadge(`${test.variants.length} variants`, test.variants.length > 0 ? 'warn' : 'info')}
                  </div>
                </div>
                <div className="audit-finding-title">{test.attack_type}</div>
                <div className="audit-finding-summary">{test.test_objective}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="audit-findings-detail audit-variant-main">
          {selectedTest ? (
            <>
              <section className="audit-panel audit-panel-feature">
                <div className="audit-panel-body audit-evidence-header">
                  <div>
                    <div className="audit-section-label">Variant Studio</div>
                    <div className="audit-evidence-title">{selectedTest.attack_type}</div>
                    <div className="audit-evidence-subtitle">{selectedTest.test_objective}</div>
                  </div>
                  <div className="audit-evidence-score-stack">
                    <ScoreCard label="Test ID" value={selectedTest.test_identifier} tone="info" />
                    <ScoreCard label="Category" value={selectedTest.category_name} tone="info" />
                    <ScoreCard label="Severity" value={selectedTest.severity} tone={severityTone(selectedTest.severity)} />
                  </div>
                </div>
              </section>

              <div className="audit-variant-top-grid">
                <section className="audit-panel">
                  <div className="audit-panel-header">
                    <div className="audit-panel-title">Edit Prompt And Save As Variant</div>
                    <div className="audit-note">Base workbook prompt remains immutable.</div>
                  </div>
                  <div className="audit-panel-body">
                    <div className="audit-form-grid">
                      <label className="audit-form-field">
                        <span>Variant Name</span>
                        <input value={variantName} onChange={event => setVariantName(event.target.value)} />
                      </label>
                      <label className="audit-form-field">
                        <span>Edited Expected Behavior</span>
                        <textarea value={variantExpectedBehavior} onChange={event => setVariantExpectedBehavior(event.target.value)} rows={4} />
                      </label>
                    </div>
                    <label className="audit-form-field">
                      <span>Edited Prompt Sequence</span>
                      <textarea value={variantPrompt} onChange={event => setVariantPrompt(event.target.value)} rows={9} />
                    </label>
                    <div className="audit-inline-actions">
                      <button
                        className="audit-secondary-btn"
                        type="button"
                        onClick={() => void handleSaveVariant()}
                        disabled={isSaving || !variantName.trim() || !variantPrompt.trim()}
                      >
                        {isSaving ? 'Saving Variant' : 'Save As Variant'}
                      </button>
                      {selectedVariant && <span className="audit-note">Selected variant: {selectedVariant.variant_name}</span>}
                    </div>
                  </div>
                </section>

                <section className="audit-panel">
                  <div className="audit-panel-header">
                    <div className="audit-panel-title">Saved Variants And Execution</div>
                    <div className="audit-note">{selectedTest?.variants.length ?? 0} variants</div>
                  </div>
                  <div className="audit-panel-body">
                    <div className="audit-scroll-list audit-variant-saved-list">
                      {(selectedTest?.variants ?? []).map(variant => (
                        <button
                          key={variant.id}
                          type="button"
                          className={`audit-finding-row ${selectedVariant?.id === variant.id ? 'selected' : ''}`}
                          onClick={() => setSelectedVariant(variant)}
                        >
                          <div className="audit-finding-row-top">
                            <span className="audit-code-cell">Variant #{variant.id}</span>
                            <div className="audit-finding-badge-stack">
                              {renderBadge('Variant', 'warn')}
                            </div>
                          </div>
                          <div className="audit-finding-title">{variant.variant_name}</div>
                          <div className="audit-finding-summary">{variant.edited_expected_behavior ?? selectedTest?.expected_behavior}</div>
                          <div className="audit-finding-meta">
                            <span>{variant.created_by ?? 'Unknown author'}</span>
                            <span>{formatTimestamp(variant.created_at)}</span>
                          </div>
                        </button>
                      ))}
                      {(selectedTest?.variants.length ?? 0) === 0 && (
                        <div className="audit-empty-state compact">
                          <div className="audit-empty-title">No saved variants yet</div>
                          <div className="audit-empty-copy">Use the editor to save a workbook-derived prompt variant for this test.</div>
                        </div>
                      )}
                    </div>

                    <div className="audit-run-box">
                      <div className="audit-config-grid">
                        <div className="audit-config-row"><span>Validated Target</span><span>{selectedTargetInfo?.display_name ?? 'No target selected'}</span></div>
                        <div className="audit-config-row"><span>Model</span><span>{selectedTargetInfo?.model_name ?? 'Unset'}</span></div>
                        <div className="audit-config-row"><span>Endpoint</span><span>{selectedTargetInfo?.endpoint ?? 'Unset'}</span></div>
                      </div>
                    <div className="audit-scroll-list" style={{ maxHeight: '180px', marginTop: '12px' }}>
                        {auditableTargets.map(target => (
                          <label key={target.target_registry_name} className={`audit-target-item ${selectedTarget === target.target_registry_name ? 'active' : ''}`}>
                            <input type="radio" name="variant-target" checked={selectedTarget === target.target_registry_name} onChange={() => setSelectedTarget(target.target_registry_name)} />
                            <div className="audit-item-main">
                              <div className="audit-item-title">{target.display_name ?? target.target_registry_name}</div>
                              <div className="audit-item-subtitle">{target.model_name}</div>
                              <div className="audit-small-meta">{target.endpoint}</div>
                            </div>
                          </label>
                        ))}
                      </div>
                      <label className="audit-form-field" style={{ marginTop: '12px' }}>
                        <span>Execution Scope</span>
                        <select value={executionScope} onChange={event => setExecutionScope(event.target.value as AuditPromptSourceMode)}>
                          <option value="selected_variant">Selected Saved Variant</option>
                          <option value="base_and_variant">Base Test + Selected Variant</option>
                        </select>
                      </label>
                      <div className="audit-inline-actions">
                        <button
                          className="audit-primary-btn audit-primary-btn-inline"
                          type="button"
                          onClick={() => void handleRunVariant(selectedVariant)}
                          disabled={!selectedVariant || !selectedTarget || isRunning}
                        >
                          {isRunning ? 'Running Variant' : 'Run Selected Variant'}
                        </button>
                      </div>
                    </div>
                  </div>
                </section>
              </div>

              <section className="audit-detail-grid">
                <EvidenceSection index={1} title="Base Workbook Prompt" value={selectedTest.prompt_sequence} />
                <EvidenceSection index={2} title="Variant Draft" value={variantPrompt} accent="actual" />
                <EvidenceSection index={3} title="Base Expected Behavior" value={selectedTest.expected_behavior} accent="expected" />
                <EvidenceSection index={4} title="Variant Expected Behavior" value={variantExpectedBehavior || selectedTest.expected_behavior} accent="response" />
              </section>
            </>
          ) : (
            <div className="audit-empty-state">
              <div className="audit-empty-title">Select a workbook test to build variants</div>
              <div className="audit-empty-copy">The prompt variant workspace compares the original workbook prompt against the edited variant and executes saved variants through the structured audit runner.</div>
            </div>
          )}
        </div>
      </section>
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

function severityTone(severity?: string | null) {
  const normalized = (severity ?? '').toUpperCase()
  if (normalized === 'CRITICAL') return 'critical'
  if (normalized === 'HIGH') return 'fail'
  if (normalized === 'MEDIUM') return 'warn'
  if (normalized === 'LOW') return 'pass'
  return 'info'
}

function renderBadge(label: string, tone: 'pass' | 'warn' | 'fail' | 'info' | 'critical') {
  return <span className={`audit-badge ${tone}`}>{label}</span>
}
