import { useEffect, useMemo, useState } from 'react'
import { targetsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { TargetInstance } from '../../types'
import { Badge, FieldHelp, friendlySourceLabel, valueText } from './common'

type WorkflowId = 'interactive_audit' | 'llm_scanner' | 'red_campaign' | 'shield'

interface UnifiedTargetSelectorProps {
  value: string
  onChange: (targetId: string, target?: TargetInstance | null) => void
  workflow: WorkflowId
  label?: string
  help?: string
  required?: boolean
  disabled?: boolean
}

export default function UnifiedTargetSelector({
  value,
  onChange,
  workflow,
  label = 'Target',
  help = 'Select a configured target from the same SpriCO target registry used by Interactive Audit.',
  required = true,
  disabled = false,
}: UnifiedTargetSelectorProps) {
  const [targets, setTargets] = useState<TargetInstance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const loadTargets = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await targetsApi.listTargets(200)
        if (!cancelled) setTargets(response.items ?? [])
      } catch (err) {
        if (!cancelled) setError(toApiError(err).detail)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    void loadTargets()
    return () => {
      cancelled = true
    }
  }, [])

  const selectedTarget = useMemo(
    () => targets.find(target => target.target_registry_name === value) ?? null,
    [targets, value],
  )
  const metadata = selectedTarget ? describeTarget(selectedTarget) : null

  return (
    <div className="sprico-field">
      <span className="sprico-label">{label}{required ? ' *' : ''}</span>
      <FieldHelp>{help}</FieldHelp>
      {error && <div className="sprico-message sprico-message-error">Could not load configured targets: {error}</div>}
      <select
        className="sprico-select"
        aria-label={label}
        value={value}
        disabled={disabled || isLoading}
        onChange={event => {
          const next = event.target.value
          const target = targets.find(item => item.target_registry_name === next) ?? null
          onChange(next, target)
        }}
      >
        <option value="">{isLoading ? 'Loading targets...' : 'Select configured target'}</option>
        {targets.map(target => {
          const item = describeTarget(target)
          return (
            <option key={target.target_registry_name} value={target.target_registry_name}>
              {item.name} | {target.target_type} | {item.connectionStatus}
            </option>
          )
        })}
      </select>
      {!isLoading && targets.length === 0 && (
        <div className="sprico-message">No configured targets found. Create a target in Settings &gt; Configuration first.</div>
      )}
      {metadata && (
        <div className="sprico-target-summary" data-testid="unified-target-summary">
          <div>
            <span className="sprico-kpi-label">Target Name</span>
            <strong>{metadata.name}</strong>
          </div>
          <div>
            <span className="sprico-kpi-label">Target Type</span>
            <Badge value={selectedTarget?.target_type} />
          </div>
          <div>
            <span className="sprico-kpi-label">Provider</span>
            <span>{metadata.provider}</span>
          </div>
          <div>
            <span className="sprico-kpi-label">Domain</span>
            <span>{metadata.domain}</span>
          </div>
          <div>
            <span className="sprico-kpi-label">Connection Status</span>
            <Badge value={metadata.connectionStatus} />
          </div>
          <div>
            <span className="sprico-kpi-label">Policy Pack</span>
            <span>{metadata.policyPack}</span>
          </div>
          <div className="sprico-target-workflows">
            <span className="sprico-kpi-label">Compatible Workflows</span>
            <span>{compatibleWorkflows(selectedTarget).map(item => friendlySourceLabel(item)).join(', ')}</span>
          </div>
          {!isWorkflowCompatible(selectedTarget, workflow) && (
            <div className="sprico-message sprico-message-error">
              This target is not fully compatible with {workflowLabel(workflow)}. Check endpoint and target configuration before running.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function describeTarget(target: TargetInstance) {
  const params = target.target_specific_params ?? {}
  const name = target.display_name || target.target_registry_name
  const endpoint = valueText(target.endpoint)
  return {
    id: target.target_registry_name,
    name,
    provider: providerForTarget(target),
    domain: domainForTarget(target),
    endpointConfigured: Boolean(endpoint.trim()),
    connectionStatus: endpoint.trim() ? 'Configured' : 'Missing endpoint',
    policyPack: valueText(params.policy_id ?? params.policy_pack ?? params.target_domain ?? domainForTarget(target), 'Not assigned'),
  }
}

export function isWorkflowCompatible(target: TargetInstance | null | undefined, workflow: WorkflowId): boolean {
  if (!target) return false
  if (workflow === 'interactive_audit' || workflow === 'shield') return true
  if (workflow === 'llm_scanner' || workflow === 'red_campaign') {
    return Boolean(valueText(target.endpoint).trim()) && target.target_type !== 'TextTarget'
  }
  return false
}

function compatibleWorkflows(target: TargetInstance | null | undefined): string[] {
  if (!target) return []
  const workflows = ['interactive_audit', 'shield']
  if (isWorkflowCompatible(target, 'llm_scanner')) workflows.push('llm_scanner')
  if (isWorkflowCompatible(target, 'red_campaign')) workflows.push('red_campaign')
  return workflows
}

function workflowLabel(workflow: WorkflowId): string {
  return {
    interactive_audit: 'Interactive Audit',
    llm_scanner: 'LLM Vulnerability Scanner',
    red_campaign: 'Red Team Campaigns',
    shield: 'Shield',
  }[workflow]
}

function providerForTarget(target: TargetInstance): string {
  const type = target.target_type.toLowerCase()
  const endpoint = valueText(target.endpoint).toLowerCase()
  if (type.includes('gemini') || endpoint.includes('generativelanguage.googleapis.com')) return 'Google Gemini'
  if (type.includes('openai') || endpoint.includes('api.openai.com')) return 'OpenAI-compatible'
  if (endpoint.includes('localhost') || endpoint.includes('127.0.0.1') || endpoint.includes('ollama')) return 'Local / OpenAI-compatible'
  if (target.target_type === 'TextTarget') return 'Static text'
  return 'Configured provider'
}

function domainForTarget(target: TargetInstance): string {
  const params = target.target_specific_params ?? {}
  const explicit = valueText(params.target_domain ?? params.domain ?? params.industry ?? params.policy_domain).trim()
  if (explicit) return explicit
  const haystack = `${target.display_name ?? ''} ${target.target_registry_name}`.toLowerCase()
  if (haystack.includes('hospital') || haystack.includes('health') || haystack.includes('clinical')) return 'Healthcare'
  if (haystack.includes('legal')) return 'Legal'
  if (haystack.includes('hr') || haystack.includes('human resources')) return 'HR'
  if (haystack.includes('finance') || haystack.includes('bank')) return 'Financial'
  return 'General AI'
}
