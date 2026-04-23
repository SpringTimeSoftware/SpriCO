import { useEffect, useMemo, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { externalEnginesApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { ExternalEngineEntry, ExternalEngineMatrix } from '../../types'
import { Badge, EmptyMessage, ErrorMessage, LoadingMessage, valueText } from './common'
import './spricoPlatform.css'

type EngineRow = ExternalEngineEntry & {
  row_type: 'attack engine' | 'evidence engine' | 'final verdict authority'
}

export default function ExternalEngineMetadataPage() {
  const [matrix, setMatrix] = useState<ExternalEngineMatrix | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      setMatrix(await externalEnginesApi.getMatrix())
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const rows = useMemo<EngineRow[]>(() => {
    if (!matrix) return []
    const attackRows = matrix.attack_engines.map(item => ({ ...item, row_type: 'attack engine' as const }))
    const evidenceRows = matrix.evidence_engines.map(item => ({ ...item, row_type: 'evidence engine' as const }))
    const authority = matrix.final_verdict_authority ?? {}
    const authorityRow: EngineRow = {
      id: valueText(authority.id, 'sprico_policy_decision_engine'),
      name: valueText(authority.name, 'SpriCO PolicyDecisionEngine'),
      engine_type: 'final_verdict_authority',
      row_type: 'final verdict authority',
      available: Boolean(authority.available ?? true),
      optional: false,
      enabled_by_default: true,
      metadata_only: false,
      final_verdict_capable: true,
      can_generate_attacks: false,
      can_generate_evidence: false,
      can_produce_final_verdict: true,
      license_id: null,
      source_url: null,
      installed_version: valueText(authority.installed_version, 'native'),
      install_hint: valueText(authority.description, 'Locked for regulated-domain audits.'),
    }
    return [...attackRows, ...evidenceRows, authorityRow]
  }, [matrix])

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading external engine metadata" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">External Engine Metadata</div>
          <div className="sprico-subtitle">
            External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.
          </div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <ErrorMessage error={error} />

      <section className="sprico-panel">
        <div className="sprico-panel-title">Final Verdict Authority</div>
        <div className="sprico-kpis">
          <Metric label="Authority" value="SpriCO PolicyDecisionEngine" />
          <Metric label="Final Verdict Authority" value="Yes" />
          <Metric label="Regulated Domain Lock" value={matrix?.regulated_domain_lock?.locked ? 'Locked' : 'Unknown'} />
        </div>
        <div className="sprico-message">
          SpriCO PolicyDecisionEngine is locked for regulated-domain audits. External scanner, judge, assertion, or attack-engine outputs are stored as evidence and cannot override the final verdict.
        </div>
      </section>

      <section className="sprico-panel">
        <div className="sprico-panel-title">Registered Engines</div>
        {rows.length === 0 && <EmptyMessage>No external engine metadata returned.</EmptyMessage>}
        <div className="sprico-table-wrap">
          <table className="sprico-table">
            <thead>
              <tr>
                <th>Engine</th>
                <th>ID</th>
                <th>Type</th>
                <th>Available</th>
                <th>Version</th>
                <th>License</th>
                <th>Source</th>
                <th>Attack</th>
                <th>Evidence</th>
                <th>Final Verdict</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={`${row.row_type}:${row.id}`}>
                  <td>{row.name}</td>
                  <td>{row.id}</td>
                  <td>{row.row_type}</td>
                  <td><Badge value={row.available ? 'available' : row.metadata_only ? 'metadata only' : 'missing'} /></td>
                  <td>{valueText(row.installed_version, row.available ? 'installed' : 'not installed')}</td>
                  <td>{valueText(row.license_id, 'native')}</td>
                  <td>{sourceLabel(row)}</td>
                  <td><Badge value={row.can_generate_attacks ? 'Yes' : 'No'} /></td>
                  <td><Badge value={row.can_generate_evidence ? 'Yes' : 'No'} /></td>
                  <td><Badge value={row.can_produce_final_verdict || row.final_verdict_capable ? 'Yes' : 'No'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="sprico-panel">
        <div className="sprico-panel-title">Optional Engine Notes</div>
        <div className="sprico-list">
          {rows.filter(row => row.optional || row.metadata_only).map(row => (
            <div className="sprico-row" key={`note:${row.id}`}>
              <span className="sprico-row-main">
                <span className="sprico-row-title">{row.name}</span>
                <span className="sprico-row-subtitle">{row.install_hint || 'Optional evidence or attack engine. Not a final verdict authority.'}</span>
              </span>
              <Badge value={row.metadata_only ? 'deferred runtime' : row.available ? 'available' : 'optional'} />
            </div>
          ))}
        </div>
      </section>
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

function sourceLabel(row: EngineRow): string {
  if (row.source_file) return row.source_file
  if (row.source_url) return row.source_url
  return 'native SpriCO'
}
