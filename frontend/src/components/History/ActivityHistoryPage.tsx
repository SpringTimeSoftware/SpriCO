import { useEffect, useState } from 'react'
import { Button } from '@fluentui/react-components'
import { activityApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { ActivityHistoryCategory } from '../../types'
import type { ViewName } from '../Sidebar/Navigation'
import { Badge, EmptyMessage, ErrorMessage, LoadingMessage, PageHelp, formatDateTime, valueText } from '../SpriCO/common'
import '../SpriCO/spricoPlatform.css'

interface ActivityHistoryPageProps {
  onNavigate?: (view: ViewName) => void
}

export default function ActivityHistoryPage({ onNavigate }: ActivityHistoryPageProps = {}) {
  const [categories, setCategories] = useState<ActivityHistoryCategory[]>([])
  const [scopeNote, setScopeNote] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const response = await activityApi.getHistory(5)
      setCategories(response.categories)
      setScopeNote(response.scope_note)
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
    return <div className="sprico-shell"><LoadingMessage label="Loading activity history" /></div>
  }

  return (
    <div className="sprico-shell">
      <header className="sprico-header">
        <div>
          <div className="sprico-title">Activity History</div>
          <div className="sprico-subtitle">Cross-workflow ledger for audits, scanner runs, campaigns, Shield, evidence, and findings.</div>
        </div>
        <Button appearance="secondary" onClick={() => void load()}>Refresh</Button>
      </header>

      <PageHelp>
        Activity History shows where SpriCO activity is stored across workflows. PyRIT Attack History remains a scoped PyRIT memory view, not the whole product history.
      </PageHelp>

      {scopeNote && <div className="sprico-message">{scopeNote}</div>}
      <ErrorMessage error={error} />

      <section className="sprico-panel">
        <div className="sprico-panel-title">Activity Categories</div>
        <div className="sprico-kpis">
          {categories.map(category => (
            <div className="sprico-kpi" key={category.key}>
              <div className="sprico-kpi-label">{category.title}</div>
              <div className="sprico-kpi-value">{category.count}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="sprico-grid-wide">
        {categories.map(category => (
          <section className="sprico-panel" key={category.key}>
            <div className="sprico-panel-title">{category.title}</div>
            <div className="sprico-row-subtitle">{category.description}</div>
            <div className="sprico-actions">
              <Badge value={`${category.count} records`} />
              {onNavigate && isKnownView(category.navigation_view) && (
                <Button appearance="secondary" onClick={() => onNavigate(category.navigation_view as ViewName)}>
                  Open {category.title}
                </Button>
              )}
            </div>
            <div className="sprico-list">
              {category.items.length === 0 && <EmptyMessage>No recent records in this category.</EmptyMessage>}
              {category.items.map(item => (
                <div className="sprico-row" key={`${category.key}:${item.id}:${item.created_at}`}>
                  <span className="sprico-row-main">
                    <span className="sprico-row-title">{valueText(item.title, item.id || category.title)}</span>
                    <span className="sprico-row-subtitle">
                      {valueText(item.subtitle)} {item.created_at ? `| ${formatDateTime(item.created_at)}` : ''}
                    </span>
                  </span>
                  <Badge value={valueText(item.status, 'recorded')} />
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}

function isKnownView(value: string): value is ViewName {
  return [
    'chat',
    'history',
    'config',
    'audit',
    'dashboard',
    'heatmap-dashboard',
    'stability-dashboard',
    'findings',
    'prompt-variants',
    'target-help',
    'benchmark-library',
    'garak-scanner',
    'scanner-reports',
    'shield',
    'policy',
    'red',
    'evidence',
    'conditions',
    'open-source-components',
    'external-engines',
    'judge-models',
    'diagnostics',
    'activity-history',
    'landing',
  ].includes(value)
}
