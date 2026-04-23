import { useState } from 'react'
import {
  Dialog,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogContent,
  DialogActions,
  Button,
  Input,
  Textarea,
  Label,
  Select,
  tokens,
  Field,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components'
import { targetsApi } from '../../services/api'
import { useCreateTargetDialogStyles } from './CreateTargetDialog.styles'

const SUPPORTED_TARGET_TYPES = [
  'OpenAIChatTarget',
  'OpenAICompletionTarget',
  'OpenAIImageTarget',
  'OpenAIVideoTarget',
  'OpenAITTSTarget',
  'OpenAIResponseTarget',
  'OpenAIVectorStoreTarget',
  'GeminiFileSearchTarget',
] as const

interface CreateTargetDialogProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

export default function CreateTargetDialog({ open, onClose, onCreated }: CreateTargetDialogProps) {
  const styles = useCreateTargetDialogStyles()
  const [displayName, setDisplayName] = useState('')
  const [targetType, setTargetType] = useState('')
  const [endpoint, setEndpoint] = useState('')
  const [modelName, setModelName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [retrievalStoreId, setRetrievalStoreId] = useState('')
  const [systemInstructions, setSystemInstructions] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    targetType?: string
    endpoint?: string
    modelName?: string
    apiKey?: string
    retrievalStoreId?: string
  }>({})

  const isRetrievalTarget = targetType === 'OpenAIVectorStoreTarget' || targetType === 'GeminiFileSearchTarget'
  const endpointPlaceholder = targetType === 'GeminiFileSearchTarget'
    ? 'https://generativelanguage.googleapis.com/v1beta/'
    : 'https://your-resource.openai.azure.com/'
  const retrievalPlaceholder = targetType === 'GeminiFileSearchTarget'
    ? 'fileSearchStores/...'
    : 'vs_...'

  const resetForm = () => {
    setDisplayName('')
    setTargetType('')
    setEndpoint('')
    setModelName('')
    setApiKey('')
    setRetrievalStoreId('')
    setSystemInstructions('')
    setError(null)
    setFieldErrors({})
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  const handleSubmit = async () => {
    const errors: {
      targetType?: string
      endpoint?: string
      modelName?: string
      apiKey?: string
      retrievalStoreId?: string
    } = {}
    if (!targetType) errors.targetType = 'Please select a target type'
    if (!endpoint) errors.endpoint = 'Please provide an endpoint URL'
    if (isRetrievalTarget && !modelName.trim()) errors.modelName = 'Please provide a model name'
    if (isRetrievalTarget && !apiKey.trim()) errors.apiKey = 'Please provide an API key'
    if (isRetrievalTarget && !retrievalStoreId.trim()) errors.retrievalStoreId = 'Please provide a retrieval store ID'
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }
    setFieldErrors({})

    setSubmitting(true)
    setError(null)

    try {
      const params: Record<string, unknown> = {
        endpoint,
      }
      if (modelName) params.model_name = modelName
      if (apiKey) params.api_key = apiKey
      if (isRetrievalTarget) {
        params.retrieval_store_id = retrievalStoreId.trim()
        params.retrieval_mode = 'file_search'
      }
      if (systemInstructions.trim()) params.system_instructions = systemInstructions.trim()

      await targetsApi.createTarget({
        type: targetType,
        display_name: displayName || undefined,
        params,
      })
      resetForm()
      onCreated()
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to create target')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(_, data) => { if (!data.open) handleClose() }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Create New Target</DialogTitle>
          <DialogContent>
            <form className={styles.form} onSubmit={(e) => { e.preventDefault(); handleSubmit() }}>
              {error && (
                <MessageBar intent="error">
                  <MessageBarBody>{error}</MessageBarBody>
                </MessageBar>
              )}

              <Field
                label="Display Name"
              >
                <Input
                  placeholder="Optional label for this target"
                  value={displayName}
                  onChange={(_, data) => setDisplayName(data.value)}
                />
              </Field>

              <Field
                label="Target Type"
                required
                validationMessage={fieldErrors.targetType}
                validationState={fieldErrors.targetType ? 'error' : 'none'}
              >
                <Select
                  value={targetType}
                  onChange={(_, data) => setTargetType(data.value)}
                >
                  <option value="">Select a target type</option>
                  {SUPPORTED_TARGET_TYPES.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </Select>
              </Field>

              <Field
                label="Endpoint URL"
                required
                validationMessage={fieldErrors.endpoint}
                validationState={fieldErrors.endpoint ? 'error' : 'none'}
              >
                <Input
                  placeholder={endpointPlaceholder}
                  value={endpoint}
                  onChange={(_, data) => setEndpoint(data.value)}
                />
              </Field>

              <Field label="Model / Deployment Name">
                <Input
                  placeholder="e.g. gpt-4o, dall-e-3"
                  value={modelName}
                  onChange={(_, data) => setModelName(data.value)}
                  aria-invalid={fieldErrors.modelName ? 'true' : undefined}
                />
              </Field>

              {fieldErrors.modelName && (
                <Label size="small" style={{ color: tokens.colorPaletteRedForeground1 }}>
                  {fieldErrors.modelName}
                </Label>
              )}

              <Field label="API Key">
                <Input
                  type="password"
                  placeholder="API key (encrypted for local persistence)"
                  autoComplete="current-password"
                  value={apiKey}
                  onChange={(_, data) => setApiKey(data.value)}
                  aria-invalid={fieldErrors.apiKey ? 'true' : undefined}
                />
              </Field>

              {fieldErrors.apiKey && (
                <Label size="small" style={{ color: tokens.colorPaletteRedForeground1 }}>
                  {fieldErrors.apiKey}
                </Label>
              )}

              {isRetrievalTarget && (
                <Field
                  label="Retrieval Store ID"
                  required
                  validationMessage={fieldErrors.retrievalStoreId}
                  validationState={fieldErrors.retrievalStoreId ? 'error' : 'none'}
                >
                  <Input
                    placeholder={retrievalPlaceholder}
                    value={retrievalStoreId}
                    onChange={(_, data) => setRetrievalStoreId(data.value)}
                  />
                </Field>
              )}

              {isRetrievalTarget && (
                <Field label="System Instructions">
                  <Textarea
                    placeholder="Optional retrieval-aware instructions for this target"
                    value={systemInstructions}
                    onChange={(_, data) => setSystemInstructions(data.value)}
                    resize="vertical"
                  />
                </Field>
              )}

              <Label size="small" style={{ color: tokens.colorNeutralForeground3 }}>
                Targets can also be auto-populated by adding an initializer (e.g. <code>airt</code>) to your{' '}
                <code>~/.pyrit/.pyrit_conf</code> file, which reads endpoints from your <code>.env</code> and{' '}
                <code>.env.local</code> files. See{' '}
                <a href="https://github.com/Azure/PyRIT/blob/main/.pyrit_conf_example" target="_blank" rel="noopener noreferrer">
                  .pyrit_conf_example
                </a>.
              </Label>
            </form>
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={handleClose} disabled={submitting}>
              Cancel
            </Button>
            <Button appearance="primary" onClick={handleSubmit} disabled={submitting || !targetType || !endpoint}>
              {submitting ? 'Creating...' : 'Create Target'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  )
}
