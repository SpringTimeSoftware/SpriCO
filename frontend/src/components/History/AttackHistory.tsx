import { useState, useEffect, useCallback } from 'react'
import {
  Text,
  Button,
  Spinner,
  MessageBar,
  MessageBarBody,
  Badge,
} from '@fluentui/react-components'
import { ArrowSyncRegular } from '@fluentui/react-icons'
import { attacksApi, auditApi, labelsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { AttackSummary, AuditRun } from '../../types'
import type { HistoryFilters } from './historyFilters'
import type { ViewName } from '../Sidebar/Navigation'
import { useAttackHistoryStyles } from './AttackHistory.styles'
import HistoryFiltersBar from './HistoryFiltersBar'
import AttackTable from './AttackTable'
import HistoryPagination from './HistoryPagination'

interface AttackHistoryProps {
  onOpenAttack: (attackResultId: string) => void
  onOpenSavedInteractiveAudit?: (runId: string) => void
  onOpenAuditRuns?: () => void
  onNavigate?: (view: ViewName) => void
  filters: HistoryFilters
  onFiltersChange: (filters: HistoryFilters) => void
}

export default function AttackHistory({ onOpenAttack, onOpenSavedInteractiveAudit, onOpenAuditRuns, onNavigate, filters, onFiltersChange }: AttackHistoryProps) {
  const styles = useAttackHistoryStyles()
  const [attacks, setAttacks] = useState<AttackSummary[]>([])
  const [savedInteractiveRuns, setSavedInteractiveRuns] = useState<AuditRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filter options
  const [attackClassOptions, setAttackClassOptions] = useState<string[]>([])
  const [converterOptions, setConverterOptions] = useState<string[]>([])
  const [operatorOptions, setOperatorOptions] = useState<string[]>([])
  const [operationOptions, setOperationOptions] = useState<string[]>([])
  const [otherLabelOptions, setOtherLabelOptions] = useState<string[]>([])

  // Pagination
  const [cursor, setCursor] = useState<string | undefined>(undefined)
  const [isLastPage, setIsLastPage] = useState(true)
  const [page, setPage] = useState(0)

  const PAGE_SIZE = 25

  const fetchAttacks = useCallback(async (pageCursor?: string) => {
    setLoading(true)
    setError(null)
    try {
      const labelParams: string[] = []
      if (filters.operator) { labelParams.push(`operator:${filters.operator}`) }
      if (filters.operation) { labelParams.push(`operation:${filters.operation}`) }
      labelParams.push(...filters.otherLabels)

      const [response, interactiveRuns] = await Promise.all([
        attacksApi.listAttacks({
          limit: PAGE_SIZE,
          ...(pageCursor && { cursor: pageCursor }),
          ...(filters.attackClass && { attack_type: filters.attackClass }),
          ...(filters.outcome && { outcome: filters.outcome }),
          ...(filters.converter && { converter_types: [filters.converter] }),
          ...(labelParams.length > 0 && { label: labelParams }),
        }),
        auditApi.listInteractiveRuns(100).catch(() => []),
      ])
      setAttacks(response.items.map(attack => ({ ...attack, labels: attack.labels ?? {} })))
      setSavedInteractiveRuns(interactiveRuns)
      setIsLastPage(!response.pagination.has_more)
      setCursor(response.pagination.next_cursor ?? undefined)
    } catch (err) {
      setAttacks([])
      setSavedInteractiveRuns([])
      setError(toApiError(err).detail)
    } finally {
      setLoading(false)
    }
  }, [filters.attackClass, filters.outcome, filters.converter, filters.operator, filters.operation, filters.otherLabels])

  // Load filter options on mount
  useEffect(() => {
    attacksApi.getAttackOptions()
      .then(resp => setAttackClassOptions(resp.attack_types))
      .catch(() => { /* ignore */ })
    attacksApi.getConverterOptions()
      .then(resp => setConverterOptions(resp.converter_types))
      .catch(() => { /* ignore */ })
    labelsApi.getLabels()
      .then(resp => {
        const operators: string[] = []
        const operations: string[] = []
        const others: string[] = []
        for (const [key, values] of Object.entries(resp.labels)) {
          if (key === 'operator') {
            operators.push(...values)
          } else if (key === 'operation') {
            operations.push(...values)
          } else if (key !== 'source') {
            for (const val of values) {
              others.push(`${key}:${val}`)
            }
          }
        }
        setOperatorOptions(operators.sort())
        setOperationOptions(operations.sort())
        setOtherLabelOptions(others.sort())
      })
      .catch(() => { /* ignore */ })
  }, [])

  // Reload when filters change
  useEffect(() => {
    setPage(0)
    setCursor(undefined)
    fetchAttacks()
  }, [fetchAttacks])

  const handleNextPage = () => {
    if (cursor) {
      setPage(p => p + 1)
      fetchAttacks(cursor)
    }
  }

  const handlePrevPage = () => {
    setPage(0)
    setCursor(undefined)
    fetchAttacks()
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const hasActiveFilters =
    filters.attackClass || filters.outcome || filters.converter ||
    filters.operator || filters.operation || filters.otherLabels.length > 0

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div className={styles.headerRow}>
          <Text size={500} weight="semibold">PyRIT Attack History</Text>
          <Button
            appearance="subtle"
            icon={<ArrowSyncRegular />}
            onClick={() => fetchAttacks()}
            disabled={loading}
            data-testid="refresh-btn"
          >
            Refresh
          </Button>
        </div>
        <HistoryFiltersBar
          filters={filters}
          onFiltersChange={onFiltersChange}
          attackClassOptions={attackClassOptions}
          converterOptions={converterOptions}
          operatorOptions={operatorOptions}
          operationOptions={operationOptions}
          otherLabelOptions={otherLabelOptions}
        />
        <div className={styles.scopeNotice}>
          <Text size={200} className={styles.scopeNoticeText}>
            This page shows PyRIT-backed attack sessions only. Saved Interactive Audit replays from audit.db can appear below when they reference PyRIT-backed interactive runs. Other SpriCO activity lives under Activity History, Audit Runs, Scanner Run Reports, Red Team Campaigns, Shield, Evidence Center, or Findings.
          </Text>
        </div>
        <div className={styles.historyLinks} aria-label="Activity history links">
          <HistoryLink className={styles.historyLinkCard} title="PyRIT Attack Sessions" description="The table below reads PyRIT CentralMemory attack sessions." disabled />
          <HistoryLink className={styles.historyLinkCard} title="Activity History" description="Cross-workflow activity across audit, scanner, campaign, Shield, evidence, and findings stores." onClick={onNavigate ? () => onNavigate('activity-history') : undefined} />
          <HistoryLink className={styles.historyLinkCard} title="Audit Runs" description="Structured and saved interactive audit runs." onClick={onOpenAuditRuns ?? (onNavigate ? () => onNavigate('audit') : undefined)} />
          <HistoryLink className={styles.historyLinkCard} title="Open Scanner Run Reports" description="Every LLM Vulnerability Scanner job, including no-finding runs." onClick={onNavigate ? () => onNavigate('scanner-reports') : undefined} />
          <HistoryLink className={styles.historyLinkCard} title="Red Team Campaigns" description="Objective-driven campaign runs." onClick={onNavigate ? () => onNavigate('red') : undefined} />
          <HistoryLink className={styles.historyLinkCard} title="Shield Events" description="Policy checks are stored as evidence and Shield event records." onClick={onNavigate ? () => onNavigate('evidence') : undefined} />
          <HistoryLink className={styles.historyLinkCard} title="Evidence Center" description="Normalized proof from audits, scanners, Shield, and campaigns." onClick={onNavigate ? () => onNavigate('evidence') : undefined} />
          <HistoryLink className={styles.historyLinkCard} title="Findings" description="Actionable SpriCO outcomes." onClick={onNavigate ? () => onNavigate('findings') : undefined} />
        </div>
      </div>

      <div className={styles.content}>
        {loading ? (
          <div className={styles.emptyState}>
            <Spinner size="medium" label="Loading attacks..." />
          </div>
        ) : error ? (
          <div className={styles.emptyState} data-testid="error-state">
            <MessageBar intent="error">
              <MessageBarBody>{error}</MessageBarBody>
            </MessageBar>
            <Button
              appearance="primary"
              icon={<ArrowSyncRegular />}
              onClick={() => fetchAttacks()}
              disabled={loading}
              data-testid="retry-btn"
            >
              Retry
            </Button>
          </div>
        ) : attacks.length === 0 && savedInteractiveRuns.length === 0 ? (
          <div className={styles.emptyState} data-testid="empty-state">
            <Text size={400}>No PyRIT attack sessions were found in the active backend storage.</Text>
            <Text size={200}>
              {hasActiveFilters
                ? 'Try adjusting your filters.'
                : 'Other SpriCO activity may exist under Audit Runs, Scanner Run Reports, Red Team Campaigns, Shield, Evidence Center, or Findings. Saved Interactive Audit runs appear here when audit.db contains them.'}
            </Text>
          </div>
        ) : (
          <>
            {savedInteractiveRuns.length > 0 && (
              <section className={styles.savedRunSection} aria-labelledby="saved-interactive-audit-heading">
                <div className={styles.savedRunHeader}>
                  <div>
                    <Text id="saved-interactive-audit-heading" size={400} weight="semibold">
                      Saved Interactive Audit Runs
                    </Text>
                    <Text size={200} className={styles.scopeNoticeText}>
                      These records are loaded from audit.db and can be opened as read-only Interactive Audit replays.
                    </Text>
                  </div>
                  <Badge appearance="outline">{savedInteractiveRuns.length} saved</Badge>
                </div>
                <div className={styles.savedRunList} data-testid="saved-interactive-runs">
                  {savedInteractiveRuns.map(run => (
                    <Button
                      key={run.job_id}
                      appearance="secondary"
                      className={styles.savedRunCard}
                      onClick={() => onOpenSavedInteractiveAudit?.(run.job_id)}
                      disabled={!onOpenSavedInteractiveAudit}
                      data-testid={`saved-interactive-run-${run.job_id}`}
                    >
                      <span>
                        <strong>{run.target_registry_name || run.target_id || 'Interactive Audit Run'}</strong>
                        <span className={styles.savedRunMeta}>
                          {formatDate(run.completed_at || run.updated_at || run.created_at)} | {run.target_type || 'Interactive Audit'}
                        </span>
                        <span className={styles.savedRunStats}>
                          Turns {run.completed_tests}/{run.total_tests} | PASS {run.pass_count} | WARN {run.warn_count} | FAIL {run.fail_count}
                        </span>
                      </span>
                    </Button>
                  ))}
                </div>
              </section>
            )}
            {attacks.length > 0 && (
              <section className={styles.savedRunSection} aria-label="PyRIT attack sessions">
                <Text size={400} weight="semibold">PyRIT Attack Sessions</Text>
                <AttackTable attacks={attacks} onOpenAttack={onOpenAttack} formatDate={formatDate} />
              </section>
            )}
          </>
        )}
      </div>

      {!loading && attacks.length > 0 && (
        <HistoryPagination
          page={page}
          isLastPage={isLastPage}
          onPrevPage={handlePrevPage}
          onNextPage={handleNextPage}
        />
      )}
    </div>
  )
}

function HistoryLink({
  title,
  description,
  onClick,
  disabled,
  className,
}: {
  title: string
  description: string
  onClick?: () => void
  disabled?: boolean
  className?: string
}) {
  return (
    <Button
      appearance="secondary"
      className={className}
      disabled={disabled || !onClick}
      onClick={onClick}
    >
      <span>
        <strong>{title}</strong>
        <span>{description}</span>
      </span>
    </Button>
  )
}
