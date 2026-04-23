import { useState, useEffect, useCallback } from 'react'
import {
  tokens,
  Text,
  Button,
  Spinner,
} from '@fluentui/react-components'
import { AddRegular, ArrowSyncRegular } from '@fluentui/react-icons'
import { targetsApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import type { TargetConfigView, TargetInstance } from '../../types'
import CreateTargetDialog from './CreateTargetDialog'
import TargetTable from './TargetTable'
import ViewTargetDialog from './ViewTargetDialog'
import { useTargetConfigStyles } from './TargetConfig.styles'

interface TargetConfigProps {
  activeTarget: TargetInstance | null
  onSetActiveTarget: (target: TargetInstance | null) => void
  onOpenTargetHelp?: () => void
}

export default function TargetConfig({ activeTarget, onSetActiveTarget, onOpenTargetHelp }: TargetConfigProps) {
  const styles = useTargetConfigStyles()
  const [targets, setTargets] = useState<TargetInstance[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [viewDialogOpen, setViewDialogOpen] = useState(false)
  const [viewLoading, setViewLoading] = useState(false)
  const [viewError, setViewError] = useState<string | null>(null)
  const [viewTargetConfig, setViewTargetConfig] = useState<TargetConfigView | null>(null)

  // Retry fetching targets a few times with backoff. The Vite dev proxy
  // returns 502 while the backend is still starting, so a single failed
  // request on initial page load would show a confusing error to the user.
  const fetchTargets = useCallback(async () => {
    const maxRetries = 3
    setLoading(true)
    setError(null)
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const response = await targetsApi.listTargets(200)
        setTargets(response.items)
        setLoading(false)
        return
      } catch (err) {
        if (attempt < maxRetries) {
          // Wait before retrying (1s, 2s, 3s)
          await new Promise(r => setTimeout(r, (attempt + 1) * 1000))
        } else {
          setError(toApiError(err).detail)
        }
      }
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchTargets()
  }, [fetchTargets])

  useEffect(() => {
    if (activeTarget || targets.length === 0) {
      return
    }
    const persistedActive = targets.find(target => target.is_active)
    if (persistedActive) {
      onSetActiveTarget(persistedActive)
    }
  }, [activeTarget, onSetActiveTarget, targets])

  const handleTargetCreated = async () => {
    setDialogOpen(false)
    await fetchTargets()
  }

  const handleSetActiveTarget = async (target: TargetInstance) => {
    try {
      const activated = await targetsApi.activateTarget(target.target_registry_name)
      onSetActiveTarget(activated)
      await fetchTargets()
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const handleViewTarget = async (target: TargetInstance) => {
    setViewDialogOpen(true)
    setViewLoading(true)
    setViewError(null)
    setViewTargetConfig(null)
    try {
      const config = await targetsApi.getTargetConfig(target.target_registry_name)
      setViewTargetConfig(config)
    } catch (err) {
      setViewError(toApiError(err).detail)
    } finally {
      setViewLoading(false)
    }
  }

  const handleArchiveTarget = async (target: TargetInstance) => {
    const label = target.display_name || target.target_registry_name
    if (!window.confirm(`Archive target "${label}"? It will be hidden from target selection but kept in storage.`)) {
      return
    }
    try {
      await targetsApi.archiveTarget(target.target_registry_name, 'Archived from target configuration')
      if (activeTarget?.target_registry_name === target.target_registry_name) {
        // The backend clears active state. Keep the current page state in sync.
        const remaining = targets.filter(item => item.target_registry_name !== target.target_registry_name)
        const nextActive = remaining.find(item => item.is_active) ?? null
        onSetActiveTarget(nextActive)
      }
      await fetchTargets()
    } catch (err) {
      setError(toApiError(err).detail)
    }
  }

  const handleTargetConfigSaved = async (config: TargetConfigView) => {
    setViewTargetConfig(config)
    await fetchTargets()
  }

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Text size={600} weight="semibold">Target Configuration</Text>
          <Text size={300} style={{ color: tokens.colorNeutralForeground3 }}>
            Manage targets for attack sessions. Select a target to use in the chat view.
          </Text>
        </div>
        <div className={styles.headerActions}>
          <Button
            appearance="subtle"
            onClick={onOpenTargetHelp}
          >
            Which target should I use?
          </Button>
          <Button
            appearance="subtle"
            icon={<ArrowSyncRegular />}
            onClick={fetchTargets}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            appearance="primary"
            icon={<AddRegular />}
            onClick={() => setDialogOpen(true)}
          >
            New Target
          </Button>
        </div>
      </div>

      {loading && (
        <div className={styles.loadingState}>
          <Spinner label="Loading targets..." />
        </div>
      )}

      {error && (
        <div className={styles.errorState}>
          <Text>Error: {error}</Text>
        </div>
      )}

      {!loading && !error && targets.length === 0 && (
        <div className={styles.emptyState}>
          <Text size={500} weight="semibold">No Targets Configured</Text>
          <Text size={300} style={{ color: tokens.colorNeutralForeground3 }}>
            Add a target manually, or configure an initializer in your <code>~/.pyrit/.pyrit_conf</code> file
            to auto-populate targets from your <code>.env</code> and <code>.env.local</code> files.
            For example, add <code>airt</code> to the <code>initializers</code> list to register
            Azure OpenAI targets automatically. See the{' '}
            <a href="https://github.com/Azure/PyRIT/blob/main/.pyrit_conf_example" target="_blank" rel="noopener noreferrer">
              .pyrit_conf_example
            </a>{' '}
            for details.
          </Text>
          <Button
            appearance="primary"
            icon={<AddRegular />}
            onClick={() => setDialogOpen(true)}
          >
            Create First Target
          </Button>
        </div>
      )}

      {!loading && !error && targets.length > 0 && (
        <TargetTable
          targets={targets}
          activeTarget={activeTarget}
          onSetActiveTarget={handleSetActiveTarget}
          onViewTarget={handleViewTarget}
          onArchiveTarget={handleArchiveTarget}
        />
      )}

      <CreateTargetDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={handleTargetCreated}
      />

      <ViewTargetDialog
        open={viewDialogOpen}
        targetConfig={viewTargetConfig}
        loading={viewLoading}
        error={viewError}
        onSaved={handleTargetConfigSaved}
        onClose={() => {
          setViewDialogOpen(false)
          setViewTargetConfig(null)
          setViewError(null)
        }}
      />
    </div>
  )
}
