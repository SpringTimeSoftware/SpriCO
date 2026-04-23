import { useEffect, useMemo, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { spricoEvidenceApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { SpriCOEvidenceItem } from '../../types'
import { Badge, EmptyMessage, ErrorMessage, FieldHelp, LoadingMessage, PageHelp, formatDateTime, redactedJson, valueText, friendlySourceLabel } from './common'
import './spricoPlatform.css'

export default function EvidencePage() {
  const [allItems, setAllItems] = useState<SpriCOEvidenceItem[]>([])
  const [selected, setSelected] = useState<SpriCOEvidenceItem | null>(null)
  const [scanId, setScanId] = useState('')
  const [evidenceId, setEvidenceId] = useState(() => {
    if (typeof window === 'undefined') return ''
    const value = window.sessionStorage.getItem('spricoEvidenceFindingId') ?? ''
    window.sessionStorage.removeItem('spricoEvidenceFindingId')
    return value
  })
  const [engine, setEngine] = useState('')
  const [engineType, setEngineType] = useState('')
  const [policyId, setPolicyId] = useState('')
  const [risk, setRisk] = useState('')
  const [finalVerdict, setFinalVerdict] = useState('')
  const [showAdvancedRaw, setShowAdvancedRaw] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const response = await spricoEvidenceApi.list({
        limit: 250,
        scan_id: scanId || undefined,
        evidence_id: evidenceId || undefined,
        policy_id: policyId || undefined,
        risk: risk || undefined,
        final_verdict: finalVerdict || undefined,
      })
      setAllItems(response)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const items = useMemo(() => {
    return allItems.filter(item => {
      const normalizedEngine = normalizeEvidenceEngine(item).toLowerCase()
      const normalizedType = normalizeEvidenceEngineType(item).toLowerCase()
      const normalizedVerdict = normalizeEvidenceFinalVerdict(item).toLowerCase()
      const engineNeedle = engine.trim().toLowerCase()
      const typeNeedle = engineType.trim().toLowerCase()
      const sourceCandidates = evidenceSourceCandidates(item).map(candidate => candidate.toLowerCase())
      const typeCandidates = evidenceSourceTypeCandidates(item).map(candidate => candidate.toLowerCase())
      return (!engine || sourceCandidates.some(candidate => candidate.includes(engineNeedle)) || normalizedEngine.includes(engineNeedle))
        && (!engineType || typeCandidates.includes(typeNeedle) || normalizedType === typeNeedle)
        && (!finalVerdict || normalizedVerdict === finalVerdict.trim().toLowerCase())
        && (!evidenceId || item.finding_id === evidenceId.trim())
    })
  }, [allItems, engine, engineType, finalVerdict, evidenceId])

  useEffect(() => {
    setSelected(prev => {
      if (prev && items.some(item => item.finding_id === prev.finding_id)) {
        return prev
      }
      return items[0] ?? null
    })
  }, [items])

  const engines = useMemo(() => Array.from(new Set(allItems.flatMap(evidenceSourceCandidates))).filter(Boolean).sort(), [allItems])
  const engineTypes = useMemo(() => Array.from(new Set(allItems.flatMap(evidenceSourceTypeCandidates))).filter(Boolean).sort(), [allItems])
  const verdicts = useMemo(() => Array.from(new Set(allItems.map(normalizeEvidenceFinalVerdict))).filter(Boolean).sort(), [allItems])

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading evidence" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Evidence Center</div>
          <div className="sprico-subtitle">External engine results are evidence only. SpriCO final verdicts are stored separately and redacted by default.</div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <PageHelp>
        Evidence Center stores raw and normalized proof from audits, scanner runs, Shield checks, and Red Team Campaigns. External engine outputs are evidence only. SpriCO final verdicts are shown separately.
      </PageHelp>

      <ErrorMessage error={error} />

      <section className="sprico-panel">
        <div className="sprico-panel-title">Filters</div>
        <div className="sprico-grid">
          <label className="sprico-field">
            <span className="sprico-label">Scan / Session / Conversation</span>
            <FieldHelp>Use this to find evidence created by one audit run, scanner run, Red campaign, Shield check, or interactive conversation.</FieldHelp>
            <input className="sprico-input" value={scanId} onChange={event => setScanId(event.target.value)} />
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Evidence ID</span>
            <FieldHelp>A stable record identifier for one stored evidence item.</FieldHelp>
            <input className="sprico-input" value={evidenceId} onChange={event => setEvidenceId(event.target.value)} />
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Evidence Source</span>
            <FieldHelp>The audit, scanner, Shield, Red campaign, or policy component that produced this proof.</FieldHelp>
            <select className="sprico-select" value={engine} onChange={event => setEngine(event.target.value)}>
              <option value="">All</option>
              {engines.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Source Type</span>
            <FieldHelp>Classifies whether the proof came from scanner evidence, domain signals, a Shield check, or another evidence source.</FieldHelp>
            <select className="sprico-select" value={engineType} onChange={event => setEngineType(event.target.value)}>
              <option value="">All</option>
              {engineTypes.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Policy</span>
            <FieldHelp>Filter by the policy or policy context used to interpret the evidence.</FieldHelp>
            <input className="sprico-input" value={policyId} onChange={event => setPolicyId(event.target.value)} />
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Risk</span>
            <FieldHelp>Violation risk is separate from data sensitivity and depends on policy context.</FieldHelp>
            <select className="sprico-select" value={risk} onChange={event => setRisk(event.target.value)}>
              <option value="">All</option>
              {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="sprico-field">
            <span className="sprico-label">Final SpriCO Verdict</span>
            <FieldHelp>The policy-aware outcome from SpriCO, not a raw scanner decision.</FieldHelp>
            <select className="sprico-select" value={finalVerdict} onChange={event => setFinalVerdict(event.target.value)}>
              <option value="">All</option>
              {verdicts.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
        <div className="sprico-actions">
          <Button appearance="primary" onClick={() => void load()}>Apply</Button>
        </div>
      </section>

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Evidence Items</div>
          <div className="sprico-table-wrap">
            <table className="sprico-table">
              <thead><tr><th>Created</th><th>Evidence Source</th><th>Source Type</th><th>Scan / Session</th><th>Final SpriCO Verdict</th><th>Risk</th></tr></thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.finding_id} onClick={() => setSelected(item)}>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td>{normalizeEvidenceEngine(item)}</td>
                    <td>{normalizeEvidenceEngineType(item)}</td>
                    <td>{valueText(item.scan_id)}</td>
                    <td><Badge value={normalizeEvidenceFinalVerdict(item)} /></td>
                    <td><Badge value={item.violation_risk} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {items.length === 0 && <EmptyMessage>No evidence matched the filters.</EmptyMessage>}
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Selected Evidence</div>
          {!selected && <EmptyMessage>Select an evidence item.</EmptyMessage>}
          {selected && (
            <div className="sprico-form">
              <div className="sprico-kpis">
                <Metric label="Evidence Source" value={normalizeEvidenceEngine(selected)} />
                <Metric label="Source Type" value={normalizeEvidenceEngineType(selected)} />
                <Metric label="License" value={valueText(selected.license_id)} />
                <Metric label="Final SpriCO Verdict" value={normalizeEvidenceFinalVerdict(selected)} />
                <Metric label="Risk" value={valueText(selected.violation_risk)} />
                <Metric label="Data Sensitivity" value={valueText(selected.data_sensitivity)} />
                <Metric label="Target" value={valueText(selected.target_name ?? selected.target_id)} />
                <Metric label="Policy" value={valueText(selected.policy_id)} />
                <Metric label="Scanner Result" value={scannerResultLabel(selected)} />
                <Metric label="Conversation" value={valueText(selected.conversation_id)} />
                <Metric label="Evidence Type" value={valueText(selected.evidence_type)} />
              </div>
              <FieldHelp>Data Sensitivity describes how protected the information is. Risk describes whether disclosure violated the active policy.</FieldHelp>
              <div>
                <div className="sprico-panel-title">Normalized Evidence Summary</div>
                <pre className="sprico-pre">{redactedJson({
                raw_result: selected.raw_result ?? selected.raw_engine_result,
                normalized_signal: selected.normalized_signal ?? selected.matched_signals,
                sprico_final_verdict: selected.sprico_final_verdict,
              })}</pre>
              </div>
              <Button className="sprico-advanced-toggle" appearance="secondary" onClick={() => setShowAdvancedRaw(value => !value)}>
                {showAdvancedRaw ? 'Hide Advanced Raw Evidence' : 'Show Advanced Raw Evidence'}
              </Button>
              {showAdvancedRaw && (
                <div className="sprico-advanced-panel">
                  <FieldHelp>Advanced Raw Evidence is redacted by default and intended for reviewers who need the stored source record.</FieldHelp>
                  <pre className="sprico-pre">{redactedJson(selected)}</pre>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="sprico-kpi">
      <div className="sprico-kpi-label">{label}</div>
      <div className="sprico-kpi-value">{value}</div>
    </div>
  )
}

function normalizeEvidenceEngine(item: SpriCOEvidenceItem): string {
  return evidenceSourceCandidates(item)[0] || friendlySourceLabel(item.engine_name ?? item.engine_id ?? item.engine)
}

function normalizeEvidenceEngineType(item: SpriCOEvidenceItem): string {
  return evidenceSourceTypeCandidates(item)[0] || friendlySourceLabel(item.engine_type || 'evidence')
}

function normalizeEvidenceFinalVerdict(item: SpriCOEvidenceItem): string {
  const verdict = item.final_verdict ?? item.sprico_final_verdict?.verdict
  return valueText(verdict || 'NEEDS_REVIEW')
}

function scannerResultLabel(item: SpriCOEvidenceItem): string {
  const scannerResult = item.scanner_result
  if (scannerResult && typeof scannerResult === 'object' && !Array.isArray(scannerResult)) {
    const hit = (scannerResult as Record<string, unknown>).hit
    if (hit === true) return 'Hit'
    if (hit === false) return 'No hit'
  }
  const rawResult = item.raw_result ?? item.raw_engine_result
  const nestedScanner = readNested(rawResult, 'scanner_result')
  if (nestedScanner && typeof nestedScanner === 'object' && !Array.isArray(nestedScanner)) {
    const hit = (nestedScanner as Record<string, unknown>).hit
    if (hit === true) return 'Hit'
    if (hit === false) return 'No hit'
  }
  return 'Not applicable'
}

function evidenceSourceCandidates(item: SpriCOEvidenceItem): string[] {
  return uniqueFriendly([
    item.engine_id,
    item.engine_name,
    item.engine,
    item.evidence_type,
    readNested(item.raw_result, 'engine_name'),
    readNested(item.raw_result, 'engine_id'),
    readNested(item.raw_engine_result, 'engine_name'),
    readNested(item.raw_engine_result, 'engine_id'),
  ])
}

function evidenceSourceTypeCandidates(item: SpriCOEvidenceItem): string[] {
  const values = uniqueFriendly([
    item.evidence_type,
    item.engine_type,
    readField(item, 'source_type'),
    readNested(item.raw_result, 'source_type'),
    readNested(item.raw_result, 'engine_type'),
    readNested(item.raw_engine_result, 'source_type'),
    readNested(item.raw_engine_result, 'engine_type'),
  ])
  if (values.length > 1) return values.filter(value => value.toLowerCase() !== 'evidence')
  return values
}

function uniqueFriendly(values: unknown[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const value of values) {
    const label = friendlySourceLabel(value).trim()
    if (!label || seen.has(label.toLowerCase())) continue
    seen.add(label.toLowerCase())
    result.push(label)
  }
  return result
}

function readField(item: SpriCOEvidenceItem, key: string): unknown {
  return (item as unknown as Record<string, unknown>)[key]
}

function readNested(value: unknown, key: string): unknown {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  return (value as Record<string, unknown>)[key]
}
