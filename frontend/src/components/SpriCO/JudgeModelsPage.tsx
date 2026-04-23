import { useEffect, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { judgeApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { JudgeStatus } from '../../types'
import { Badge, ErrorMessage, LoadingMessage, PageHelp, valueText } from './common'
import './spricoPlatform.css'

export default function JudgeModelsPage() {
  const [status, setStatus] = useState<JudgeStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      setStatus(await judgeApi.getStatus())
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
    return <div className="sprico-shell"><LoadingMessage label="Loading judge models" /></div>
  }

  const openai = status?.providers.find(provider => provider.id === 'openai')

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Judge Models</div>
          <div className="sprico-subtitle">
            Optional model-based review can provide evidence for ambiguous cases. SpriCO PolicyDecisionEngine remains the final verdict authority.
          </div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <PageHelp>
        Judge models are optional evidence sources. They are disabled by default, cannot produce final SpriCO verdicts, and must be configured through backend secrets.
      </PageHelp>
      <ErrorMessage error={error} />

      <section className="sprico-panel">
        <div className="sprico-panel-title">OpenAI Judge</div>
        <div className="sprico-kpis">
          <Metric label="Status" value={openai?.configured ? 'Configured' : 'Not configured'} />
          <Metric label="Default" value="Disabled" />
          <Metric label="Final Verdict Capable" value="No" />
          <Metric label="Final Verdict Authority" value="SpriCO PolicyDecisionEngine" />
        </div>
        <div className="sprico-message">
          API keys must be configured on the backend. Do not enter or store API keys in the frontend.
        </div>
        <div className="sprico-message">
          Healthcare/PHI and other regulated data should not be sent to external judge models by default. Redacted mode is required unless backend policy explicitly allows another mode.
        </div>
        <div className="sprico-list">
          <div className="sprico-row">
            <span className="sprico-row-main">
              <span className="sprico-row-title">{valueText(openai?.label, 'OpenAI Judge')}</span>
              <span className="sprico-row-subtitle">{valueText(openai?.configure_hint, 'Set SPRICO_OPENAI_JUDGE_ENABLED, SPRICO_OPENAI_JUDGE_MODEL, and OPENAI_API_KEY in the backend environment.')}</span>
            </span>
            <Badge value={openai?.configured ? 'Configured' : 'Not configured'} />
          </div>
          <div className="sprico-row">
            <span className="sprico-row-main">
              <span className="sprico-row-title">Allowed Modes</span>
              <span className="sprico-row-subtitle">{(openai?.allowed_modes ?? ['disabled', 'redacted']).join(', ')}</span>
            </span>
            <Badge value="Evidence only" />
          </div>
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
