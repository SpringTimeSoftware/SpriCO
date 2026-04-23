import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Button,
  Text,
  Badge,
  Tooltip,
} from '@fluentui/react-components'
import { AddRegular, PanelRightRegular } from '@fluentui/react-icons'
import MessageList from './MessageList'
import ChatInputArea from './ChatInputArea'
import ConversationPanel from './ConversationPanel'
import LabelsBar from '../Labels/LabelsBar'
import type { ChatInputAreaHandle } from './ChatInputArea'
import { attacksApi, auditApi } from '../../services/api'
import { toApiError } from '../../services/errors'
import { buildMessagePieces, backendMessagesToFrontend } from '../../utils/messageMapper'
import type {
  InteractiveAuditConversation,
  Message,
  MessageAttachment,
  TargetInfo,
  TargetInstance,
} from '../../types'
import type { ViewName } from '../Sidebar/Navigation'
import { useChatWindowStyles } from './ChatWindow.styles'

interface ChatWindowProps {
  onNewAttack: () => void
  onOpenStructuredRun?: (runId: string) => void
  activeTarget: TargetInstance | null
  savedInteractiveRunId?: string | null
  attackResultId: string | null
  conversationId: string | null
  activeConversationId: string | null
  onConversationCreated: (attackResultId: string, conversationId: string) => void
  onSelectConversation: (conversationId: string) => void
  labels?: Record<string, string>
  onLabelsChange?: (labels: Record<string, string>) => void
  onNavigate?: (view: ViewName) => void
  attackLabels?: Record<string, string> | null
  attackTarget?: TargetInfo | null
  isLoadingAttack?: boolean
  relatedConversationCount?: number
}

type AuditBadgeColor = 'danger' | 'informative' | 'success' | 'warning'

function verdictColor(verdict?: string | null): AuditBadgeColor {
  switch ((verdict || '').toUpperCase()) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'danger'
    default:
      return 'informative'
  }
}

function riskColor(risk?: string | null): AuditBadgeColor {
  switch ((risk || '').toUpperCase()) {
    case 'LOW':
      return 'success'
    case 'MEDIUM':
      return 'warning'
    case 'HIGH':
    case 'CRITICAL':
      return 'danger'
    default:
      return 'informative'
  }
}

export default function ChatWindow({
  onNewAttack,
  onOpenStructuredRun,
  activeTarget,
  savedInteractiveRunId,
  attackResultId,
  conversationId,
  activeConversationId,
  onConversationCreated,
  onSelectConversation,
  labels,
  onLabelsChange,
  onNavigate,
  attackLabels,
  attackTarget,
  isLoadingAttack,
  relatedConversationCount,
}: ChatWindowProps) {
  const styles = useChatWindowStyles()
  const [messages, setMessages] = useState<Message[]>([])
  const [sendingConversations, setSendingConversations] = useState<Set<string>>(new Set())
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [loadedConversationId, setLoadedConversationId] = useState<string | null>(null)
  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [panelRefreshKey, setPanelRefreshKey] = useState(0)
  const [interactiveAudit, setInteractiveAudit] = useState<InteractiveAuditConversation | null>(null)
  const [isSavingStructuredRun, setIsSavingStructuredRun] = useState(false)
  const inputBoxRef = useRef<ChatInputAreaHandle>(null)
  const activeTargetLabel = activeTarget
    ? (activeTarget.display_name?.trim() || activeTarget.target_type)
    : null
  const activeTargetTooltip = activeTarget
    ? [
        activeTarget.display_name?.trim() || null,
        activeTarget.target_type,
        activeTarget.model_name ? `(${activeTarget.model_name})` : null,
        activeTarget.target_registry_name,
      ]
        .filter(Boolean)
        .join(' ')
    : ''

  const isSending = activeConversationId
    ? sendingConversations.has(activeConversationId)
    : Boolean(sendingConversations.size)
  const isSavedInteractiveReplay = Boolean(savedInteractiveRunId)

  useEffect(() => {
    if (relatedConversationCount && relatedConversationCount > 0) {
      setIsPanelOpen(true)
    }
  }, [attackResultId, relatedConversationCount])

  const viewedConvRef = useRef(activeConversationId ?? conversationId)
  useEffect(() => {
    viewedConvRef.current = activeConversationId ?? conversationId
  }, [activeConversationId, conversationId])

  const sendingConvIdsRef = useRef<Set<string>>(new Set())
  const pendingUserMessagesRef = useRef<Map<string, Message[]>>(new Map())

  useEffect(() => {
    if (!attackResultId && !savedInteractiveRunId) {
      setMessages([])
      setLoadedConversationId(null)
      setInteractiveAudit(null)
    }
  }, [attackResultId, savedInteractiveRunId])

  const loadSavedInteractiveRun = useCallback(async (runId: string) => {
    setIsLoadingMessages(true)
    try {
      const response = await auditApi.getInteractiveAuditRun(runId)
      const replayMessages: Message[] = response.turns.flatMap(turn => {
        const timestamp = new Date().toISOString()
        const userPrompt = (turn.latest_user_prompt || turn.prompt_sequence || '').trim()
        const messagesForTurn: Message[] = []
        if (userPrompt) {
          messagesForTurn.push({
            role: 'user',
            content: userPrompt,
            timestamp,
            turnNumber: turn.assistant_turn_number,
          })
        }
        messagesForTurn.push({
          role: 'assistant',
          content: turn.response_text,
          timestamp,
          turnNumber: turn.assistant_turn_number,
        })
        return messagesForTurn
      })
      setMessages(replayMessages)
      setLoadedConversationId(response.conversation_id)
      setInteractiveAudit(response)
    } catch (err) {
      const apiError = toApiError(err)
      setMessages([{
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        error: {
          type: apiError.isNetworkError ? 'network' : apiError.isTimeout ? 'timeout' : 'unknown',
          description: apiError.detail,
        },
      }])
      setLoadedConversationId(null)
      setInteractiveAudit(null)
    } finally {
      setIsLoadingMessages(false)
    }
  }, [])

  useEffect(() => {
    if (!savedInteractiveRunId) {
      return
    }
    viewedConvRef.current = savedInteractiveRunId
    loadSavedInteractiveRun(savedInteractiveRunId)
  }, [loadSavedInteractiveRun, savedInteractiveRunId])

  const loadInteractiveAudit = useCallback(async (arId: string, convId: string) => {
    try {
      const response = await auditApi.getInteractiveAudit(arId, convId)
      if (viewedConvRef.current !== convId) {
        return
      }
      setInteractiveAudit(response)
    } catch {
      if (viewedConvRef.current !== convId) {
        return
      }
      setInteractiveAudit(null)
    }
  }, [])

  const loadConversation = useCallback(async (arId: string, convId: string) => {
    setIsLoadingMessages(true)
    try {
      const [messageResponse, interactiveResponse] = await Promise.allSettled([
        attacksApi.getMessages(arId, convId),
        auditApi.getInteractiveAudit(arId, convId),
      ])

      if (viewedConvRef.current !== convId) {
        return
      }

      if (messageResponse.status === 'fulfilled') {
        const frontendMessages = backendMessagesToFrontend(messageResponse.value.messages)
        if (sendingConvIdsRef.current.has(convId)) {
          const pending = pendingUserMessagesRef.current.get(convId) ?? []
          frontendMessages.push(...pending)
          frontendMessages.push({
            role: 'assistant',
            content: '...',
            timestamp: new Date().toISOString(),
            isLoading: true,
          })
        }
        setMessages(frontendMessages)
      } else {
        setMessages([])
      }
      setLoadedConversationId(convId)

      if (interactiveResponse.status === 'fulfilled') {
        setInteractiveAudit(interactiveResponse.value)
      } else {
        setInteractiveAudit(null)
      }
    } finally {
      setIsLoadingMessages(false)
    }
  }, [])

  useEffect(() => {
    if (!attackResultId || !activeConversationId) {
      return
    }
    if (sendingConvIdsRef.current.has(activeConversationId)) {
      return
    }
    loadConversation(attackResultId, activeConversationId)
  }, [activeConversationId, attackResultId, loadConversation])

  const awaitingConversationLoad = Boolean(
    activeConversationId &&
      activeConversationId !== loadedConversationId &&
      !sendingConvIdsRef.current.has(activeConversationId)
  )

  const handlePanelSelectConversation = useCallback((convId: string) => {
    onSelectConversation(convId)
    if (convId === activeConversationId && attackResultId) {
      loadConversation(attackResultId, convId)
    }
  }, [attackResultId, activeConversationId, onSelectConversation, loadConversation])

  const handleSend = async (
    originalValue: string,
    _convertedValue: string | undefined,
    attachments: MessageAttachment[],
  ) => {
    if (!activeTarget) {
      return
    }

    let sendConvId = activeConversationId || '__pending__'
    sendingConvIdsRef.current.add(sendConvId)

    const userMessage: Message = {
      role: 'user',
      content: originalValue,
      timestamp: new Date().toISOString(),
      attachments: attachments.length > 0 ? attachments : undefined,
    }
    setMessages(prev => [...prev, userMessage])

    const pending = pendingUserMessagesRef.current.get(sendConvId) ?? []
    pending.push(userMessage)
    pendingUserMessagesRef.current.set(sendConvId, pending)

    setSendingConversations(prev => new Set(prev).add(sendConvId))
    const loadingMessage: Message = {
      role: 'assistant',
      content: '...',
      timestamp: new Date().toISOString(),
      isLoading: true,
    }
    setMessages(prev => [...prev, loadingMessage])

    try {
      const pieces = await buildMessagePieces(originalValue, attachments)

      let currentAttackResultId = attackResultId
      let currentConversationId = conversationId
      let currentActiveConversationId = activeConversationId

      if (!currentAttackResultId) {
        const createResponse = await attacksApi.createAttack({
          target_registry_name: activeTarget.target_registry_name,
          labels: labels,
        })
        currentAttackResultId = createResponse.attack_result_id
        currentConversationId = createResponse.conversation_id
        currentActiveConversationId = currentConversationId
        sendingConvIdsRef.current.delete('__pending__')
        sendingConvIdsRef.current.add(currentConversationId)
        const pendingMsgs = pendingUserMessagesRef.current.get('__pending__')
        if (pendingMsgs) {
          pendingUserMessagesRef.current.delete('__pending__')
          pendingUserMessagesRef.current.set(currentConversationId, pendingMsgs)
        }
        onConversationCreated(currentAttackResultId, currentConversationId)
        viewedConvRef.current = currentConversationId
        setSendingConversations(prev => {
          const next = new Set(prev)
          next.delete('__pending__')
          next.add(currentConversationId!)
          return next
        })
        sendConvId = currentConversationId
      }

      const effectiveConvId = currentActiveConversationId ?? currentConversationId

      const response = await attacksApi.addMessage(currentAttackResultId!, {
        role: 'user',
        pieces,
        send: true,
        target_registry_name: activeTarget.target_registry_name,
        target_conversation_id: effectiveConvId!,
        labels: labels ?? undefined,
      })

      if (viewedConvRef.current === effectiveConvId) {
        const backendMessages = backendMessagesToFrontend(response.messages.messages)
        setMessages(backendMessages)
        setLoadedConversationId(effectiveConvId!)
        await loadInteractiveAudit(currentAttackResultId!, effectiveConvId!)
      }
    } catch (err) {
      if (viewedConvRef.current === sendConvId || viewedConvRef.current === (activeConversationId ?? conversationId)) {
        const apiError = toApiError(err)
        let description: string
        if (apiError.isNetworkError) {
          description = 'Network error - check that the backend is running and reachable.'
        } else if (apiError.isTimeout) {
          description = 'Request timed out. The server may be busy - please try again.'
        } else {
          description = apiError.detail
        }

        const errorMessage: Message = {
          role: 'assistant',
          content: '',
          timestamp: new Date().toISOString(),
          error: {
            type: apiError.isNetworkError ? 'network' : apiError.isTimeout ? 'timeout' : 'unknown',
            description,
          },
        }
        setMessages(prev => {
          if (prev.length > 0 && prev[prev.length - 1].isLoading) {
            return [...prev.slice(0, -1), errorMessage]
          }
          return [...prev, errorMessage]
        })

        if (originalValue && inputBoxRef.current) {
          inputBoxRef.current.setText(originalValue)
        }
      }
    } finally {
      sendingConvIdsRef.current.delete(sendConvId)
      pendingUserMessagesRef.current.delete(sendConvId)
      setSendingConversations(prev => {
        const next = new Set(prev)
        next.delete(sendConvId)
        return next
      })
      setPanelRefreshKey(k => k + 1)
    }
  }

  const handleNewConversation = useCallback(async () => {
    if (!attackResultId) {
      return
    }

    try {
      const response = await attacksApi.createConversation(attackResultId, {})
      onSelectConversation(response.conversation_id)
      setIsPanelOpen(true)
    } catch {
      // Intentionally ignore creation errors here to preserve current flow.
    }
  }, [attackResultId, onSelectConversation])

  const handleCopyToInput = useCallback((messageIndex: number) => {
    const msg = messages[messageIndex]
    if (!msg) {
      return
    }
    if (msg.content) {
      inputBoxRef.current?.setText(msg.content)
    }
    if (msg.attachments) {
      msg.attachments.filter(att => att.type !== 'file').forEach(att => {
        inputBoxRef.current?.addAttachment(att)
      })
    }
  }, [messages])

  const handleCopyToNewConversation = useCallback(async (messageIndex: number) => {
    if (!attackResultId) {
      return
    }
    const msg = messages[messageIndex]
    if (!msg) {
      return
    }

    try {
      const response = await attacksApi.createConversation(attackResultId, {})
      onSelectConversation(response.conversation_id)
      setIsPanelOpen(true)
      setTimeout(() => {
        if (msg.content) {
          inputBoxRef.current?.setText(msg.content)
        }
        if (msg.attachments) {
          msg.attachments.filter(att => att.type !== 'file').forEach(att => {
            inputBoxRef.current?.addAttachment(att)
          })
        }
      }, 100)
    } catch {
      if (msg.content) {
        inputBoxRef.current?.setText(msg.content)
      }
    }
  }, [attackResultId, messages, onSelectConversation])

  const handleBranchConversation = useCallback(async (messageIndex: number) => {
    if (!attackResultId || !activeConversationId) {
      return
    }

    try {
      const response = await attacksApi.createConversation(attackResultId, {
        source_conversation_id: activeConversationId,
        cutoff_index: messageIndex,
      })
      onSelectConversation(response.conversation_id)
      setIsPanelOpen(true)
      await loadConversation(attackResultId, response.conversation_id)
    } catch (err) {
      console.error('Failed to branch into new conversation:', err)
    }
  }, [attackResultId, activeConversationId, onSelectConversation, loadConversation])

  const handleBranchAttack = useCallback(async (messageIndex: number) => {
    if (!activeTarget || !activeConversationId) {
      return
    }

    try {
      const createResponse = await attacksApi.createAttack({
        target_registry_name: activeTarget.target_registry_name,
        labels: labels,
        source_conversation_id: activeConversationId,
        cutoff_index: messageIndex,
      })
      onConversationCreated(createResponse.attack_result_id, createResponse.conversation_id)
      await loadConversation(createResponse.attack_result_id, createResponse.conversation_id)
    } catch (err) {
      console.error('Failed to branch into new attack:', err)
    }
  }, [activeTarget, activeConversationId, labels, onConversationCreated, loadConversation])

  const handleChangeMainConversation = useCallback(async (convId: string) => {
    if (!attackResultId) {
      return
    }

    try {
      await attacksApi.changeMainConversation(attackResultId, convId)
    } catch (err) {
      console.error('Failed to change main conversation:', err)
    }
  }, [attackResultId])

  const singleTurnLimitReached =
    activeTarget?.supports_multi_turn === false && messages.some(message => message.role === 'user')

  const currentOperator = labels?.operator
  const attackOperator = attackLabels?.operator
  const isOperatorLocked = Boolean(
    attackResultId && attackLabels && attackOperator && currentOperator && attackOperator !== currentOperator
  )

  const isCrossTargetLocked = Boolean(
    attackResultId &&
      attackTarget &&
      activeTarget &&
      (
        attackTarget.target_type !== activeTarget.target_type ||
        (attackTarget.endpoint ?? '') !== (activeTarget.endpoint ?? '') ||
        (attackTarget.model_name ?? '') !== (activeTarget.model_name ?? '')
      )
  )

  const handleUseAsTemplate = useCallback(async () => {
    if (!attackResultId || !activeTarget || !activeConversationId) {
      return
    }

    const lastIndex = messages.reduce((acc, message, index) => (message.isLoading ? acc : index), -1)
    if (lastIndex < 0) {
      return
    }

    try {
      const createResponse = await attacksApi.createAttack({
        target_registry_name: activeTarget.target_registry_name,
        labels: labels,
        source_conversation_id: activeConversationId,
        cutoff_index: lastIndex,
      })
      onConversationCreated(createResponse.attack_result_id, createResponse.conversation_id)
      await loadConversation(createResponse.attack_result_id, createResponse.conversation_id)
    } catch (err) {
      console.error('Failed to use as template:', err)
    }
  }, [attackResultId, activeTarget, activeConversationId, messages, labels, onConversationCreated, loadConversation])

  const handleSaveStructuredRun = useCallback(async () => {
    if (interactiveAudit?.structured_run_id) {
      onOpenStructuredRun?.(interactiveAudit.structured_run_id)
      return
    }
    if (!attackResultId) {
      return
    }
    setIsSavingStructuredRun(true)
    try {
      const savedRun = await auditApi.saveInteractiveAudit(attackResultId, activeConversationId || conversationId || undefined)
      onOpenStructuredRun?.(savedRun.job_id)
    } catch (err) {
      console.error('Failed to save Interactive Audit as structured run:', toApiError(err))
    } finally {
      setIsSavingStructuredRun(false)
    }
  }, [activeConversationId, attackResultId, conversationId, interactiveAudit?.structured_run_id, onOpenStructuredRun])

  const turnEvaluations = interactiveAudit
    ? Object.fromEntries(interactiveAudit.turns.map(turn => [turn.assistant_turn_number, turn]))
    : undefined

  return (
    <div className={styles.root}>
      <div className={styles.chatArea}>
        <div className={styles.ribbon}>
          <div className={styles.conversationInfo}>
            <Text>Interactive Audit</Text>
            {isSavedInteractiveReplay && (
              <Badge appearance="outline" color="informative">
                Saved audit replay
              </Badge>
            )}
            {isSavedInteractiveReplay && interactiveAudit?.target_registry_name ? (
              <div className={styles.targetInfo}>
                <Text size={200}>{'->'}</Text>
                <Badge appearance="outline" size="medium">
                  {interactiveAudit.target_registry_name}
                  {interactiveAudit.model_name ? ` (${interactiveAudit.model_name})` : ''}
                </Badge>
              </div>
            ) : activeTarget ? (
              <div className={styles.targetInfo}>
                <Text size={200}>{'->'}</Text>
                <Tooltip content={activeTargetTooltip} relationship="label">
                  <Badge appearance="outline" size="medium">
                    {activeTargetLabel}
                    {activeTarget.model_name ? ` (${activeTarget.model_name})` : ''}
                  </Badge>
                </Tooltip>
              </div>
            ) : (
              <Text size={200} className={styles.noTarget}>
                No target selected
              </Text>
            )}
            {labels && onLabelsChange && (
              <LabelsBar labels={labels} onLabelsChange={onLabelsChange} />
            )}
          </div>
          <div className={styles.ribbonActions}>
            <Tooltip content="Toggle conversations panel" relationship="label">
              <Button
                appearance="subtle"
                icon={<PanelRightRegular />}
                onClick={() => setIsPanelOpen(!isPanelOpen)}
                disabled={!attackResultId || isSavedInteractiveReplay}
                data-testid="toggle-panel-btn"
              />
            </Tooltip>
            <Button
              appearance="primary"
              icon={<AddRegular />}
              onClick={() => {
                setIsPanelOpen(false)
                onNewAttack()
              }}
              disabled={!attackResultId && !isSavedInteractiveReplay}
              data-testid="new-attack-btn"
            >
              New Session
            </Button>
          </div>
        </div>

        <div className={styles.interactiveSummaryBar}>
          <div className={styles.interactiveSummaryMeta}>
            <Text weight="semibold" className={styles.interactiveSummaryTitle}>
              Shared evaluator
            </Text>
            <Text size={200} className={styles.interactiveSummarySubtext}>
              The transcript is scored with the same backend evaluator and aggregation logic used by formal audit findings.
            </Text>
          </div>
          <div className={styles.interactiveSummaryBadges}>
            {interactiveAudit && interactiveAudit.turns.length > 0 ? (
              <>
                <Button
                  appearance="secondary"
                  size="small"
                  onClick={handleSaveStructuredRun}
                  disabled={isSavingStructuredRun || (!attackResultId && !interactiveAudit?.structured_run_id)}
                >
                  {isSavingStructuredRun ? 'Opening...' : 'Open Findings'}
                </Button>
                <Badge appearance="filled" color={verdictColor(interactiveAudit.session_summary.aggregate_verdict)}>
                  Verdict: {interactiveAudit.session_summary.aggregate_verdict}
                </Badge>
                <Badge appearance="outline" color={riskColor(interactiveAudit.session_summary.aggregate_risk_level)}>
                  Risk: {interactiveAudit.session_summary.aggregate_risk_level}
                </Badge>
                <Badge appearance="outline" color="informative">
                  Turns: {interactiveAudit.session_summary.total_assistant_turns}
                </Badge>
                <Badge appearance="outline" color="success">
                  PASS {interactiveAudit.session_summary.pass_count}
                </Badge>
                <Badge appearance="outline" color="warning">
                  WARN {interactiveAudit.session_summary.warn_count}
                </Badge>
                <Badge appearance="outline" color="danger">
                  FAIL {interactiveAudit.session_summary.fail_count}
                </Badge>
              </>
            ) : (
              <Text size={200} className={styles.interactiveSummarySubtext}>
                Per-turn verdicts appear after the assistant responds.
              </Text>
            )}
          </div>
        </div>

        {isSavedInteractiveReplay && (
          <div className={styles.savedReplayBanner} data-testid="saved-interactive-replay-banner">
            <Text size={200}>
              Viewing a saved Interactive Audit run from audit.db. This replay is read-only because the PyRIT attack session is not present in active memory.
            </Text>
          </div>
        )}

        <MessageList
          messages={messages}
          onCopyToInput={handleCopyToInput}
          onCopyToNewConversation={attackResultId ? handleCopyToNewConversation : undefined}
          onBranchConversation={attackResultId && activeConversationId ? handleBranchConversation : undefined}
          onBranchAttack={activeTarget && activeConversationId ? handleBranchAttack : undefined}
          isLoading={isLoadingAttack || isLoadingMessages || awaitingConversationLoad}
          isSingleTurn={activeTarget?.supports_multi_turn === false}
          isOperatorLocked={isOperatorLocked}
          isCrossTarget={isCrossTargetLocked}
          noTargetSelected={!activeTarget}
          turnEvaluations={turnEvaluations}
          disableInlineScoring
          onOpenEvidenceCenter={(evidenceId) => {
            if (evidenceId && typeof window !== 'undefined') {
              window.sessionStorage.setItem('spricoEvidenceFindingId', evidenceId)
            }
            onNavigate?.('evidence')
          }}
        />

        <ChatInputArea
          ref={inputBoxRef}
          onSend={handleSend}
          disabled={isSavedInteractiveReplay || isSending || !activeTarget || singleTurnLimitReached || isOperatorLocked || isCrossTargetLocked}
          activeTarget={activeTarget}
          singleTurnLimitReached={singleTurnLimitReached}
          onNewConversation={attackResultId ? handleNewConversation : undefined}
          operatorLocked={isOperatorLocked}
          crossTargetLocked={isCrossTargetLocked}
          onUseAsTemplate={(isOperatorLocked || isCrossTargetLocked) ? handleUseAsTemplate : undefined}
          attackOperator={isOperatorLocked ? attackOperator ?? undefined : undefined}
          noTargetSelected={!activeTarget}
          onConfigureTarget={!activeTarget ? () => onNavigate?.('config') : undefined}
        />
      </div>

      {isPanelOpen && (
        <ConversationPanel
          attackResultId={attackResultId}
          activeConversationId={activeConversationId}
          onSelectConversation={handlePanelSelectConversation}
          onNewConversation={handleNewConversation}
          onChangeMainConversation={handleChangeMainConversation}
          onClose={() => setIsPanelOpen(false)}
          locked={!activeTarget || isOperatorLocked || isCrossTargetLocked}
          refreshKey={panelRefreshKey}
        />
      )}
    </div>
  )
}
