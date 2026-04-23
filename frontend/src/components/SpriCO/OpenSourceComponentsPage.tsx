import { useEffect, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { legalApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { OpenSourceComponent } from '../../types'
import { EmptyMessage, ErrorMessage, LoadingMessage, valueText } from './common'
import './spricoPlatform.css'

export default function OpenSourceComponentsPage() {
  const [components, setComponents] = useState<OpenSourceComponent[]>([])
  const [selected, setSelected] = useState<OpenSourceComponent | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const response = await legalApi.listOpenSourceComponents()
      setComponents(response)
      setSelected(response[0] ?? null)
    } catch (err) {
      setError(toApiError(err).detail)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  if (isLoading) {
    return <div className="sprico-shell"><LoadingMessage label="Loading open-source components" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Open Source Components</div>
          <div className="sprico-subtitle">
            External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.
          </div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <ErrorMessage error={error} />

      <div className="sprico-grid-wide">
        <section className="sprico-panel">
          <div className="sprico-panel-title">Components</div>
          {components.length === 0 && <EmptyMessage>No component metadata found.</EmptyMessage>}
          <div className="sprico-table-wrap">
            <table className="sprico-table">
              <thead>
                <tr><th>Component</th><th>License</th><th>Use</th><th>Links</th></tr>
              </thead>
              <tbody>
                {components.map(component => (
                  <tr key={component.id}>
                    <td>
                      <button className="sprico-link-button" type="button" onClick={() => setSelected(component)}>
                        {component.name}
                      </button>
                      <div className="sprico-row-subtitle">{valueText(component.version, 'version unavailable')}</div>
                    </td>
                    <td>{component.license_id}</td>
                    <td>{component.local_use}</td>
                    <td>
                      <div className="sprico-actions">
                        <a href={component.upstream_url} target="_blank" rel="noreferrer">Upstream</a>
                        <a href={component.license_url} target="_blank" rel="noreferrer">View license</a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="sprico-panel">
          <div className="sprico-panel-title">Selected Notice</div>
          {!selected && <EmptyMessage>Select a component.</EmptyMessage>}
          {selected && (
            <div className="sprico-form">
              <div className="sprico-kpis">
                <Metric label="Component" value={selected.name} />
                <Metric label="License" value={selected.license_name} />
                <Metric label="Local File" value={selected.license_file} />
              </div>
              <div className="sprico-message">
                No endorsement by NVIDIA, garak, Confident AI, DeepTeam, promptfoo, OpenAI, or any upstream project is implied.
              </div>
              <pre className="sprico-pre">{selected.source_notice || 'Source notice unavailable.'}</pre>
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
