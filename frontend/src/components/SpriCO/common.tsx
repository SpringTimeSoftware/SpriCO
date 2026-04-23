import type { ReactNode } from 'react'

export function valueText(value: unknown, fallback = ''): string {
  if (value == null) return fallback
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export function formatDateTime(value: unknown, fallback = ''): string {
  const text = valueText(value, fallback).trim()
  if (!text) return fallback
  const date = new Date(text)
  if (Number.isNaN(date.getTime())) return text
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}

export function parseJsonObject(value: string): Record<string, unknown> {
  if (!value.trim()) return {}
  const parsed = JSON.parse(value)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('JSON must be an object')
  }
  return parsed as Record<string, unknown>
}

export function jsonBlock(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2)
}

export function riskClass(value: unknown): string {
  const text = valueText(value).toUpperCase()
  if (text === 'PASS' || text === 'LOW' || text === 'ALLOW') return 'sprico-badge-pass'
  if (text === 'WARN' || text === 'MEDIUM' || text === 'NEEDS_REVIEW') return 'sprico-badge-warn'
  if (text === 'FAIL' || text === 'HIGH' || text === 'CRITICAL' || text === 'BLOCK') return 'sprico-badge-fail'
  return ''
}

export function Badge({ value }: { value: unknown }) {
  const text = valueText(value, 'UNKNOWN')
  return <span className={`sprico-badge ${riskClass(text)}`}>{text}</span>
}

export function JsonView({ value }: { value: unknown }) {
  return <pre className="sprico-pre">{jsonBlock(value)}</pre>
}

export function LoadingMessage({ label = 'Loading' }: { label?: string }) {
  return <div className="sprico-message">{label}</div>
}

export function ErrorMessage({ error }: { error: string | null }) {
  if (!error) return null
  return <div className="sprico-message sprico-message-error">{error}</div>
}

export function EmptyMessage({ children }: { children: ReactNode }) {
  return <div className="sprico-message">{children}</div>
}

export function PageHelp({ children }: { children: ReactNode }) {
  return <div className="sprico-page-help"><strong>What this page does:</strong> {children}</div>
}

export function FieldHelp({ children }: { children: ReactNode }) {
  return <span className="sprico-help">{children}</span>
}

const SENSITIVE_PATTERNS = [
  /\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b/g,
  /\bMRN[- ]?\d{3,}\b/gi,
  /\b\d{1,6}\s+[A-Z0-9][A-Za-z0-9.'-]*(?:\s+[A-Z0-9][A-Za-z0-9.'-]*){0,4}\s+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Parkway|Pkwy)\b/gi,
  /\b\d{3}-\d{2}-\d{4}\b/g,
  /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
]

export function redactSensitiveText(value: unknown): string {
  let text = valueText(value)
  for (const pattern of SENSITIVE_PATTERNS) {
    text = text.replace(pattern, '[REDACTED]')
  }
  return text
}

export function redactedJson(value: unknown): string {
  return redactSensitiveText(jsonBlock(value))
}

const FRIENDLY_SOURCE_LABELS: Record<string, string> = {
  garak: 'LLM Scanner Evidence',
  garak_detector: 'LLM Scanner Evidence',
  external_scanner: 'External Scanner Evidence',
  scanner: 'Scanner Evidence',
  sprico_domain_signals: 'SpriCO Domain Signals',
  sprico_interactive_audit: 'SpriCO Interactive Audit',
  sprico_red_team_campaigns: 'Red Team Campaign Evidence',
  'sprico.shield': 'SpriCO Shield Check',
  sprico_shield: 'SpriCO Shield Check',
  interactive_audit_turn: 'Interactive Audit Turn',
  scanner_evidence: 'LLM Scanner Evidence',
  red_team_turn: 'Red Team Campaign Turn',
  shield_check: 'SpriCO Shield Check',
  pyrit_scorer: 'PyRIT Scorer Evidence',
  openai_judge: 'Optional Judge Evidence',
  deepteam_metric: 'DeepTeam Metadata Evidence',
  promptfoo_assertion: 'promptfoo Assertion Evidence',
  interactive_audit: 'Interactive Audit',
  llm_scanner: 'LLM Vulnerability Scanner',
  red_campaign: 'Red Team Campaigns',
  shield: 'SpriCO Shield',
  evidence: 'Evidence',
}

export function friendlySourceLabel(value: unknown, fallback = ''): string {
  const text = valueText(value, fallback)
  return FRIENDLY_SOURCE_LABELS[text] ?? text.replace(/_/g, ' ')
}
