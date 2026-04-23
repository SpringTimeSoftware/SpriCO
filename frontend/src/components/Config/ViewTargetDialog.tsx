import {
  useEffect,
  useState,
} from 'react'
import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  Text,
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components'
import type { TargetConfigView } from '../../types'
import { targetsApi } from '../../services/api'
import { toApiError } from '../../services/errors'

const useStyles = makeStyles({
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalL,
  },
  pre: {
    margin: 0,
    padding: tokens.spacingVerticalS,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground2,
    overflowX: 'auto',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    fontFamily: 'Consolas, monospace',
    fontSize: tokens.fontSizeBase200,
    lineHeight: tokens.lineHeightBase200,
  },
})

interface ViewTargetDialogProps {
  open: boolean
  targetConfig: TargetConfigView | null
  loading?: boolean
  error?: string | null
  onClose: () => void
  onSaved?: (targetConfig: TargetConfigView) => void
}

function formatJson(value: Record<string, unknown> | null | undefined): string {
  if (!value || Object.keys(value).length === 0) {
    return '—'
  }
  return JSON.stringify(value, null, 2)
}

export default function ViewTargetDialog({
  open,
  targetConfig,
  loading = false,
  error,
  onClose,
  onSaved,
}: ViewTargetDialogProps) {
  const styles = useStyles()
  const [displayName, setDisplayName] = useState('')
  const [specialInstructions, setSpecialInstructions] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setDisplayName(targetConfig?.display_name ?? '')
    setSpecialInstructions(targetConfig?.special_instructions ?? '')
    setSaveError(null)
  }, [targetConfig])

  const handleSave = async () => {
    if (!targetConfig) return
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await targetsApi.updateTargetConfig(targetConfig.target_registry_name, {
        display_name: displayName,
        special_instructions: specialInstructions,
      })
      onSaved?.(updated)
    } catch (err) {
      setSaveError(toApiError(err).detail)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(_, data) => { if (!data.open) onClose() }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Target Configuration</DialogTitle>
          <DialogContent>
            {loading ? (
              <Text>Loading target configuration...</Text>
            ) : error ? (
              <Text>{error}</Text>
            ) : targetConfig ? (
              <div className={styles.form}>
                <Field label="Display Name">
                  <Input value={displayName} onChange={(_, data) => setDisplayName(data.value)} />
                </Field>

                <Field label="Target Type">
                  <Input value={targetConfig.target_type} readOnly />
                </Field>

                <Field label="Endpoint URL">
                  <Input value={targetConfig.endpoint ?? ''} readOnly />
                </Field>

                <Field label="Model / Deployment">
                  <Input value={targetConfig.model_name ?? ''} readOnly />
                </Field>

                <Field label="Retrieval Store ID">
                  <Input value={targetConfig.retrieval_store_id ?? ''} readOnly />
                </Field>

                <Field label="Retrieval Mode">
                  <Input value={targetConfig.retrieval_mode ?? ''} readOnly />
                </Field>

                <Field label="API Key">
                  <Input value={targetConfig.masked_api_key ?? ''} readOnly />
                </Field>

                <Field label="Special Instructions">
                  <Textarea
                    value={specialInstructions}
                    onChange={(_, data) => setSpecialInstructions(data.value)}
                    resize="vertical"
                  />
                </Field>

                {saveError && <Text>{saveError}</Text>}

                <Field label="Provider Settings">
                  <pre className={styles.pre}>{formatJson(targetConfig.provider_settings)}</pre>
                </Field>

                <Field label="Runtime Summary">
                  <pre className={styles.pre}>{formatJson(targetConfig.runtime_summary ?? undefined)}</pre>
                </Field>
              </div>
            ) : (
              <Text>No target configuration found.</Text>
            )}
          </DialogContent>
          <DialogActions>
            {targetConfig && (
              <Button appearance="primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving' : 'Save'}
              </Button>
            )}
            <Button appearance="secondary" onClick={onClose}>Close</Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  )
}
