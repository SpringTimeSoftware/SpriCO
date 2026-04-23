import { useEffect, useMemo, useState } from 'react'
import { auditApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { TargetCapability } from '../../types'
import './auditPlatform.css'

const CHOOSER = [
  { title: 'I am auditing a chatbot', codes: ['OPENAI_CHAT_TARGET', 'HTTP_TARGET', 'CUSTOM_TARGET'], detail: 'Use chat or HTTP targets depending on whether you audit the base model or deployed app.' },
  { title: 'I am auditing a RAG contract assistant', codes: ['OPENAI_VECTOR_STORE_TARGET', 'HTTP_TARGET', 'BROWSER_TARGET', 'CUSTOM_TARGET'], detail: 'Use the retrieval-backed OpenAI vector store target for direct file_search audits, or app-level adapters when auth, citations, UI state, and workflow behavior must stay in scope.' },
  { title: 'I am auditing a forecasting/analytics AI', codes: ['OPENAI_RESPONSE_TARGET', 'OPENAI_CHAT_TARGET', 'HTTP_TARGET', 'CUSTOM_TARGET'], detail: 'Use response/chat targets for model-level checks and HTTP/custom targets for full app grounding, leakage, and false-confidence behavior.' },
  { title: 'I am auditing a local Ollama tool', codes: ['OPENAI_CHAT_TARGET', 'HTTP_TARGET'], detail: 'OpenAI-compatible local APIs and HTTP wrappers are both supported patterns.' },
  { title: 'I am auditing image generation', codes: ['OPENAI_IMAGE_TARGET', 'CUSTOM_TARGET'], detail: 'Use an image-capable target or a custom adapter that captures image output evidence.' },
  { title: 'I am auditing text-to-speech', codes: ['OPENAI_TTS_TARGET', 'CUSTOM_TARGET'], detail: 'Use an audio/TTS target or wrap the enterprise service creating speech output.' },
  { title: 'I am auditing a browser-based AI copilot', codes: ['BROWSER_TARGET', 'CUSTOM_TARGET'], detail: 'Use browser/custom adapters when UI state, auth, tools, or workflow behavior matter.' },
]

export default function TargetHelpPage() {
  const [capabilities, setCapabilities] = useState<TargetCapability[]>([])
  const [selectedCode, setSelectedCode] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setCapabilities(await auditApi.getTargetCapabilities())
      } catch (err) {
        setError(toApiError(err).detail)
      }
    }
    void load()
  }, [])

  const capabilityByCode = useMemo(() => new Map(capabilities.map(item => [item.target_code, item])), [capabilities])
  const highlighted = selectedCode ? capabilityByCode.get(selectedCode) : null

  return (
    <div className="audit-platform audit-help-shell">
      <section className="audit-hero audit-hero-compact">
        <div>
          <div className="audit-hero-title">Target Help</div>
          <div className="audit-hero-subtitle">
            SpriCo is vendor-agnostic. OpenAI-protocol target classes are convenient built-ins, but audits can also use Azure, Ollama, Claude, Gemini, HTTP, browser, or custom adapters.
          </div>
        </div>
        <div className="audit-hero-meta audit-hero-meta-row">
          <div className="audit-meta-card"><div className="audit-meta-label">Guidance Source</div><div className="audit-meta-value">SQLite catalog</div></div>
          <div className="audit-meta-card"><div className="audit-meta-label">Targets</div><div className="audit-meta-value">{capabilities.length}</div></div>
        </div>
      </section>

      {error && <div className="audit-message error">{error}</div>}

      <section className="audit-panel">
        <div className="audit-panel-header">
          <div><div className="audit-panel-title">Quick Chooser</div><div className="audit-note">Pick the closest enterprise scenario to see recommended target patterns.</div></div>
        </div>
        <div className="audit-panel-body audit-help-chooser">
          {CHOOSER.map(choice => (
            <div key={choice.title} className="audit-help-card">
              <div className="audit-help-title">{choice.title}</div>
              <div className="audit-help-copy">{choice.detail}</div>
              <div className="audit-finding-badge-stack">
                {choice.codes.map(code => (
                  <button key={code} type="button" className="audit-badge info audit-badge-button" onClick={() => setSelectedCode(code)}>
                    {capabilityByCode.get(code)?.display_name ?? code}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {highlighted && (
        <section className="audit-panel audit-panel-feature">
          <div className="audit-panel-header">
            <div><div className="audit-panel-title">Recommended: {highlighted.display_name}</div><div className="audit-note">{highlighted.modality} | {highlighted.api_style}</div></div>
          </div>
          <div className="audit-panel-body audit-detail-grid">
            <DetailCard title="Best Use Cases" value={highlighted.best_for} />
            <DetailCard title="Do Not Use For" value={highlighted.not_suitable_for} />
            <DetailCard title="Example Enterprise Scenario" value={highlighted.example_scenarios} />
            <DetailCard title="Provider Examples" value={highlighted.provider_examples} />
          </div>
        </section>
      )}

      <section className="audit-panel">
        <div className="audit-panel-header"><div className="audit-panel-title">Target Reference</div><div className="audit-note">Loaded from audit_target_capability_catalog.</div></div>
        <div className="audit-panel-body audit-help-grid">
          {capabilities.map(item => (
            <div key={item.target_code} className="audit-help-card">
              <div className="audit-help-title">{item.display_name}</div>
              <div className="audit-finding-badge-stack">
                {renderBadge(item.modality, 'info')}
                {renderBadge(item.api_style, 'info')}
                {item.supports_multi_run && renderBadge('Multi-run', 'pass')}
                {item.supports_temperature && renderBadge('Temperature', 'warn')}
              </div>
              <div className="audit-help-copy"><strong>Best for:</strong> {item.best_for}</div>
              <div className="audit-help-copy"><strong>Avoid for:</strong> {item.not_suitable_for}</div>
              <div className="audit-help-copy"><strong>Example:</strong> {item.example_scenarios}</div>
              <div className="audit-help-copy"><strong>Provider examples:</strong> {item.provider_examples}</div>
              <div className="audit-help-copy"><strong>Determinism:</strong> Seed {item.supports_deterministic_seed ? 'supported when provider honors it' : 'not guaranteed'}; temperature {item.supports_temperature ? 'supported' : 'not exposed by this target type'}.</div>
            </div>
          ))}
        </div>
      </section>

      <section className="audit-panel">
        <div className="audit-panel-header"><div className="audit-panel-title">FAQ</div></div>
        <div className="audit-panel-body audit-help-grid">
          <DetailCard title="How should I audit an Azure/OpenAI chatbot with contracts?" value="Use chat/response targets for base model controls. Use HTTP, browser, or custom targets for full app audits where retrieval, auth, citations, scanned PDFs, and contract data handling matter." />
          <DetailCard title="How should I audit sales or production forecasting?" value="Use response/chat/http targets depending on architecture. Focus on manipulation, grounding, numerical reliability, leakage, unsafe automation, and false confidence, not only jailbreak behavior." />
          <DetailCard title="How should I audit an Ollama/local model app?" value="Use OpenAIChatTarget for direct OpenAI-compatible local endpoints. Use HTTP, browser, or custom target adapters when the deployed app adds prompts, tools, retrieval, or guardrails. Robustness mode is recommended." />
          <DetailCard title="Do OpenAI-named targets only work for OpenAI?" value="No. Some built-ins are OpenAI-protocol-oriented. Many enterprise endpoints expose compatible APIs. HTTP, browser, and custom adapters are often better for app-level audits." />
          <DetailCard title="When should I use HTTP or Browser target?" value="Use HTTP for stable APIs. Use Browser target when authentication, UI state, tool use, or workflow behavior is part of the audit boundary." />
          <DetailCard title="When should I audit the app instead of the base model?" value="Audit the app when retrieval, prompt wrapping, policy middleware, session memory, tools, or business logic can change the final response." />
          <DetailCard title="Why do deterministic and robustness results differ?" value="Compliance mode fixes sampling settings for report evidence. Robustness mode repeats runs to expose brittle refusals and worst-case behavior." />
          <DetailCard title="Why can the same prompt return different answers?" value="Sampling, retrieval results, hidden app state, and target-specific seed support can all introduce variability. Multi-run auditing measures it." />
        </div>
      </section>
    </div>
  )
}

function DetailCard({ title, value }: { title: string; value: string }) {
  return <div className="audit-detail-card"><div className="audit-detail-title">{title}</div><div className="audit-detail-body">{value}</div></div>
}

function renderBadge(label: string, tone: 'pass' | 'warn' | 'fail' | 'info' | 'critical') {
  return <span className={`audit-badge ${tone}`}>{label}</span>
}
