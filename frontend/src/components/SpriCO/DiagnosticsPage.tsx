import { useEffect, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { API_BASE_URL, garakApi, storageApi, versionApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { GarakStatus, StorageStatus, VersionInfo } from '../../types'
import { Badge, ErrorMessage, FieldHelp, LoadingMessage, PageHelp, valueText } from './common'
import './spricoPlatform.css'

const FRONTEND_BUILD_TIMESTAMP = __SPRICO_FRONTEND_BUILD_TIMESTAMP__
const FRONTEND_PACKAGE_VERSION = __SPRICO_FRONTEND_PACKAGE_VERSION__
const FRONTEND_BUILD_MARKER = __SPRICO_FRONTEND_BUILD_MARKER__

export default function DiagnosticsPage() {
  const [version, setVersion] = useState<VersionInfo | null>(null)
  const [storage, setStorage] = useState<StorageStatus | null>(null)
  const [garak, setGarak] = useState<GarakStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const [versionResponse, storageResponse, garakResponse] = await Promise.all([
        versionApi.getVersion(),
        storageApi.getStatus(),
        garakApi.getStatus().catch(() => null),
      ])
      setVersion(versionResponse)
      setStorage(storageResponse)
      setGarak(garakResponse)
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
    return <div className="sprico-shell"><LoadingMessage label="Loading diagnostics" /></div>
  }

  const buildMatch = version ? buildVersionMatch(FRONTEND_PACKAGE_VERSION, version.version) : 'Unknown'

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">About / Diagnostics</div>
          <div className="sprico-subtitle">Build, backend, scanner, and storage truth for deployment verification.</div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <PageHelp>
        Use this page after deployment to confirm the browser is running the expected frontend build, the API is the expected backend, and storage points to the intended production data.
      </PageHelp>

      <ErrorMessage error={error} />

      <section className="sprico-panel">
        <div className="sprico-panel-title">Build Truth</div>
        <div className="sprico-kpis">
          <Metric label="Frontend Package Version" value={FRONTEND_PACKAGE_VERSION} />
          <Metric label="Frontend Build Timestamp" value={FRONTEND_BUILD_TIMESTAMP} />
          <Metric label="Frontend Build Marker" value={FRONTEND_BUILD_MARKER} />
          <Metric label="Backend Version" value={valueText(version?.display ?? version?.version, 'unknown')} />
          <Metric label="Backend Commit" value={valueText(version?.commit_hash ?? version?.commit, 'not available')} />
          <Metric label="Backend Build Timestamp" value={valueText(version?.build_timestamp, 'not available')} />
          <Metric label="Backend Startup Timestamp" value={valueText(version?.backend_startup_timestamp, 'not available')} />
          <Metric label="Current API Base URL" value={API_BASE_URL} />
        </div>
        <div className="sprico-message">
          Live build match: <Badge value={buildMatch} /> Frontend and backend versions should be reviewed whenever this says Review or Unknown.
        </div>
      </section>

      <section className="sprico-panel">
        <div className="sprico-panel-title">Storage Diagnostics</div>
        <FieldHelp>These are active backend paths. Do not overwrite production dbdata during normal code deployment.</FieldHelp>
        <div className="sprico-kpis">
          <Metric label="Storage Backend" value={valueText(storage?.storage_backend, 'unknown')} />
          <Metric label="SpriCO SQLite" value={valueText(storage?.sprico_sqlite_path, 'not configured')} />
          <Metric label="PyRIT Memory" value={valueText(storage?.pyrit_memory_path, 'not configured')} />
          <Metric label="Audit DB" value={valueText(storage?.audit_db_path, 'not configured')} />
          <Metric label="Target Config Store" value={valueText(storage?.target_config_store_path, 'not configured')} />
          <Metric label="garak Artifacts" value={valueText(storage?.garak_artifacts_path, 'not configured')} />
        </div>
        {storage && (
          <div className="sprico-table-wrap">
            <table className="sprico-table">
              <thead><tr><th>Record Type</th><th>Count</th></tr></thead>
              <tbody>
                {Object.entries(storage.record_counts).map(([key, count]) => (
                  <tr key={key}><td>{key}</td><td>{count}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="sprico-panel">
        <div className="sprico-panel-title">Scanner Engine Status</div>
        <div className="sprico-kpis">
          <Metric label="garak Installed" value={garak?.available ? 'Yes' : 'No'} />
          <Metric label="garak Version" value={valueText(garak?.version, 'not installed')} />
          <Metric label="Backend Python" value={valueText(garak?.advanced?.python_executable ?? garak?.executable, 'unknown')} />
          <Metric label="Import Error" value={valueText(garak?.advanced?.import_error ?? garak?.import_error, 'none')} />
        </div>
        <div className="sprico-message">
          garak is optional scanner evidence only. SpriCO PolicyDecisionEngine remains the final verdict authority.
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

function buildVersionMatch(frontendVersion: string, backendVersion: string): string {
  if (!frontendVersion || !backendVersion) return 'Unknown'
  const frontend = normalizeVersion(frontendVersion)
  const backend = normalizeVersion(backendVersion)
  if (!frontend || !backend) return 'Unknown'
  return frontend === backend ? 'Match' : 'Review'
}

function normalizeVersion(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, '')
}
