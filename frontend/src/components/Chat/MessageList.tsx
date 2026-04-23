import { useEffect, useRef, useState, useCallback } from 'react'
import {
  Text,
  Avatar,
  tokens,
  MessageBar,
  MessageBarBody,
  Button,
  Tooltip,
  Spinner,
  Badge,
} from '@fluentui/react-components'
import {
  ArrowDownloadRegular,
  ArrowReplyRegular,
  ArrowForwardRegular,
  ChatAddRegular,
  BranchForkRegular,
} from '@fluentui/react-icons'
import type { InteractiveAuditTurn, Message, MessageAttachment } from '../../types'
import { useMessageListStyles } from './MessageList.styles'

interface MessageListProps {
  messages: Message[]
  /** Copy this message to the input box of the current conversation */
  onCopyToInput?: (messageIndex: number) => void
  /** Copy this message to the input box of a brand-new conversation (same attack) */
  onCopyToNewConversation?: (messageIndex: number) => void
  /** Branch conversation up to this point into a new conversation (same attack) */
  onBranchConversation?: (messageIndex: number) => void
  /** Branch conversation up to this point into a new attack */
  onBranchAttack?: (messageIndex: number) => void
  /** True while loading a historical attack's messages */
  isLoading?: boolean
  /** True when the target is single-turn (disables copy-to-input) */
  isSingleTurn?: boolean
  /** True when the current operator doesn't own this attack (disables same-attack actions) */
  isOperatorLocked?: boolean
  /** True when the historical conversation uses a different target (disables current-conv actions) */
  isCrossTarget?: boolean
  /** True when no target is currently selected */
  noTargetSelected?: boolean
  /** Shared backend evaluations keyed by assistant turn number. */
  turnEvaluations?: Record<number, InteractiveAuditTurn>
  /** Hides the deprecated local scoring button for the official Interactive Audit view. */
  disableInlineScoring?: boolean
  /** Opens the normalized Evidence Center when a turn has persisted evidence metadata. */
  onOpenEvidenceCenter?: (evidenceId?: string) => void
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

function safetyColor(label?: string | null): AuditBadgeColor {
  switch ((label || '').toUpperCase()) {
    case 'SAFE':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'VIOLATION':
      return 'danger'
    default:
      return 'informative'
  }
}

function refusalColor(strength?: string | null): AuditBadgeColor {
  switch ((strength || '').toUpperCase()) {
    case 'STRONG':
    case 'ADEQUATE':
      return 'success'
    case 'WEAK':
    case 'PARTIAL':
      return 'warning'
    case 'NONE':
      return 'danger'
    default:
      return 'informative'
  }
}

function outcomeColor(outcome?: string | null): AuditBadgeColor {
  switch ((outcome || '').toUpperCase()) {
    case 'RESISTED':
      return 'success'
    case 'PARTIAL':
      return 'warning'
    case 'SUCCESS':
      return 'danger'
    default:
      return 'informative'
  }
}

function groundingColor(verdict?: string | null): AuditBadgeColor {
  switch ((verdict || '').toUpperCase()) {
    case 'GROUNDED':
      return 'success'
    case 'PARTIAL':
      return 'warning'
    case 'UNSUPPORTED':
    case 'CONTAMINATED':
      return 'danger'
    default:
      return 'informative'
  }
}

function formatRuleList(rules?: string[]): string {
  return rules && rules.length > 0 ? rules.join(', ') : 'None'
}

function formatDetectedEntities(entities?: Array<Record<string, unknown>>): string {
  if (!entities || entities.length === 0) {
    return 'No sensitive entities captured.'
  }
  return entities
    .slice(0, 8)
    .map(entity => `${String(entity.entity_type || 'ENTITY')}: ${String(entity.value || '[REDACTED]')}`)
    .join('\n')
}

function formatContextReferences(context?: Record<string, unknown>): string {
  if (!context || Object.keys(context).length === 0) {
    return 'No prior sensitive context references were detected.'
  }
  const referenceTerms = Array.isArray(context.reference_terms) ? context.reference_terms.join(', ') : 'None'
  const priorTurns = Array.isArray(context.previous_turn_ids) ? context.previous_turn_ids.join(', ') : 'None'
  const reason = typeof context.risk_reason === 'string' && context.risk_reason ? context.risk_reason : 'No explicit context risk reason was recorded.'
  return `Terms: ${referenceTerms}\nPrior turns: ${priorTurns}\nReason: ${reason}`
}

/** Image that shows a spinner while loading. */
function ImageWithSpinner({
  src,
  alt,
  className,
  hiddenClassName,
  containerClassName,
  spinnerClassName,
}: {
  src: string
  alt: string
  className: string
  hiddenClassName: string
  containerClassName: string
  spinnerClassName: string
}) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const onLoad = useCallback(() => setLoaded(true), [])
  const onError = useCallback(() => {
    setError(true)
    setLoaded(true)
  }, [])

  return (
    <div className={containerClassName}>
      {!loaded && <Spinner size="small" className={spinnerClassName} />}
      {error ? (
        <Text size={200} italic>
          Image failed to load
        </Text>
      ) : (
        <img
          src={src}
          alt={alt}
          className={loaded ? className : hiddenClassName}
          onLoad={onLoad}
          onError={onError}
        />
      )}
    </div>
  )
}

function getEvidenceCenterReference(turnEvaluation: InteractiveAuditTurn): string | null {
  if (turnEvaluation.evidence_item_id?.trim()) {
    return turnEvaluation.evidence_item_id.trim()
  }
  const context = turnEvaluation.context_references ?? {}
  const keys = [
    'evidence_item_id',
    'evidence_id',
    'finding_id',
    'normalized_evidence_id',
    'normalized_evidence_item_id',
  ]
  for (const key of keys) {
    const raw = context[key]
    if (typeof raw === 'string' && raw.trim()) {
      return raw.trim()
    }
  }
  return null
}

function MediaWithFallback({ type, src, className }: { type: 'video' | 'audio'; src: string; className?: string }) {
  const [error, setError] = useState(false)
  const handleError = useCallback(() => setError(true), [])

  if (error) {
    return (
      <Text size={200} italic data-testid={`${type}-error`}>
        {type === 'video' ? 'Video' : 'Audio'} failed to load
      </Text>
    )
  }

  if (type === 'video') {
    return <video src={src} controls className={className} onError={handleError} data-testid="video-player" />
  }
  return <audio src={src} controls onError={handleError} data-testid="audio-player" />
}

export default function MessageList({
  messages,
  onCopyToInput,
  onCopyToNewConversation,
  onBranchConversation,
  onBranchAttack,
  isLoading,
  isSingleTurn,
  isOperatorLocked,
  isCrossTarget,
  noTargetSelected,
  turnEvaluations,
  disableInlineScoring,
  onOpenEvidenceCenter,
}: MessageListProps) {
  const styles = useMessageListStyles()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [expandedEvaluations, setExpandedEvaluations] = useState<Record<number, boolean>>({})

  const handleDownload = async (att: MessageAttachment) => {
    try {
      const resp = await fetch(att.url)
      const blob = await resp.blob()
      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = att.name
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(objectUrl)
    } catch {
      window.open(att.url, '_blank')
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (isLoading) {
    return (
      <div className={styles.emptyState} data-testid="loading-state">
        <Spinner size="medium" label="Loading conversation..." />
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className={styles.emptyState}>
        <Text size={500} weight="semibold">
          Welcome to Interactive Audit
        </Text>
        <Text size={300} style={{ color: tokens.colorNeutralForeground3 }}>
          Start a manual conversation with the selected target. Each assistant turn is scored by the same evaluator used for formal audit findings.
        </Text>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      {messages.map((message, index) => {
        const isUser = message.role === 'user'
        const isSimulated = message.role === 'simulated_assistant'
        const timestamp = new Date(message.timestamp).toLocaleTimeString()
        const avatarName = isUser ? 'User' : isSimulated ? 'Simulated' : 'Assistant'
        const turnEvaluation = message.turnNumber != null ? turnEvaluations?.[message.turnNumber] : undefined
        const isEvaluationExpanded = Boolean(
          turnEvaluation && expandedEvaluations[turnEvaluation.assistant_turn_number]
        )
        const evidenceCenterReference = turnEvaluation ? getEvidenceCenterReference(turnEvaluation) : null

        return (
          <div key={index} className={`${styles.message} ${isUser ? styles.userMessage : ''}`}>
            <Avatar name={avatarName} color={isUser ? 'colorful' : isSimulated ? 'steel' : 'brand'} />
            <div className={`${styles.messageContent} ${isUser ? styles.userMessageContent : ''}`}>
              {message.error && (
                <div className={styles.errorContainer}>
                  <MessageBar intent="error">
                    <MessageBarBody>
                      <Text weight="semibold">{message.error.type}</Text>
                      {message.error.description && <Text>: {message.error.description}</Text>}
                    </MessageBarBody>
                  </MessageBar>
                </div>
              )}

              {message.reasoningSummaries && message.reasoningSummaries.length > 0 && (
                <div className={styles.reasoningContainer} data-testid="reasoning-summary">
                  <div className={styles.reasoningLabel}>Reasoning</div>
                  {message.reasoningSummaries.map((summary, reasoningIndex) => (
                    <Text key={reasoningIndex} className={styles.reasoningText} block>
                      {summary}
                    </Text>
                  ))}
                </div>
              )}

              {(message.originalContent || message.originalAttachments) && (
                <div className={styles.originalSection} data-testid="original-section">
                  <div className={styles.sectionLabel}>Original</div>
                  {message.originalContent && (
                    <Text className={styles.originalText}>{message.originalContent}</Text>
                  )}
                  {message.originalAttachments && message.originalAttachments.length > 0 && (
                    <div className={styles.attachmentsContainer}>
                      {message.originalAttachments.map((att, originalIndex) => (
                        <div key={originalIndex}>
                          {att.type === 'image' && (
                            <ImageWithSpinner
                              src={att.url}
                              alt={att.name}
                              className={styles.attachmentPreview}
                              hiddenClassName={styles.attachmentPreviewHidden}
                              containerClassName={styles.imageContainer}
                              spinnerClassName={styles.imageSpinner}
                            />
                          )}
                          {att.type === 'video' && (
                            <MediaWithFallback type="video" src={att.url} className={styles.videoPreview} />
                          )}
                          {att.type === 'audio' && <MediaWithFallback type="audio" src={att.url} />}
                          {att.type === 'file' && (
                            <div className={styles.attachmentFile}>
                              <Text size={200}>File: {att.name}</Text>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {(message.originalContent || message.originalAttachments) && (
                <>
                  <div className={styles.sectionDivider} />
                  <Tooltip content="Only the converted value was sent to the target" relationship="description">
                    <div className={styles.convertedLabel} data-testid="converted-label">
                      Converted
                    </div>
                  </Tooltip>
                </>
              )}

              {message.content && (
                <Text className={message.isLoading ? styles.loadingEllipsis : styles.messageText}>
                  {message.content}
                </Text>
              )}

              {message.attachments && message.attachments.length > 0 && (
                <div className={styles.attachmentsContainer}>
                  {message.attachments.map((att, attIndex) => (
                    <div key={attIndex}>
                      {att.type === 'image' && (
                        <ImageWithSpinner
                          src={att.url}
                          alt={att.name}
                          className={styles.attachmentPreview}
                          hiddenClassName={styles.attachmentPreviewHidden}
                          containerClassName={styles.imageContainer}
                          spinnerClassName={styles.imageSpinner}
                        />
                      )}
                      {att.type === 'video' && (
                        <MediaWithFallback type="video" src={att.url} className={styles.videoPreview} />
                      )}
                      {att.type === 'audio' && <MediaWithFallback type="audio" src={att.url} />}
                      {att.type === 'file' && (
                        <div className={styles.attachmentFile}>
                          <Text size={200}>File: {att.name}</Text>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {turnEvaluation && (
                <div className={styles.evaluationCard} data-testid={`interactive-audit-turn-${turnEvaluation.assistant_turn_number}`}>
                  <div className={styles.evaluationHeader}>
                    <div className={styles.evaluationBadges}>
                      <Badge appearance="filled" color={verdictColor(turnEvaluation.compliance_verdict)}>
                        Verdict: {turnEvaluation.compliance_verdict}
                      </Badge>
                      <Badge appearance="outline" color={riskColor(turnEvaluation.final_risk_level)}>
                        Risk: {turnEvaluation.final_risk_level}
                      </Badge>
                      <Badge appearance="outline" color={safetyColor(turnEvaluation.response_safety_label)}>
                        Safety: {turnEvaluation.response_safety_label || 'UNKNOWN'}
                      </Badge>
                      <Badge appearance="outline" color={refusalColor(turnEvaluation.refusal_strength)}>
                        Refusal: {turnEvaluation.refusal_strength || 'N/A'}
                      </Badge>
                      <Badge appearance="outline" color={outcomeColor(turnEvaluation.attack_outcome)}>
                        Outcome: {turnEvaluation.attack_outcome || 'N/A'}
                      </Badge>
                      {turnEvaluation.grounding_verdict && (
                        <Badge appearance="outline" color={groundingColor(turnEvaluation.grounding_verdict)}>
                          Grounding: {turnEvaluation.grounding_verdict}
                        </Badge>
                      )}
                    </div>
                    <Text className={styles.evaluationTurnLabel}>
                      Score {turnEvaluation.score} | Turn {turnEvaluation.assistant_turn_number}
                    </Text>
                  </div>
                  <Text className={styles.evaluationReason}>{turnEvaluation.short_reason}</Text>
                  <Button
                    appearance="subtle"
                    size="small"
                    className={styles.evaluationDetailsButton}
                    onClick={() => {
                      setExpandedEvaluations(prev => ({
                        ...prev,
                        [turnEvaluation.assistant_turn_number]: !prev[turnEvaluation.assistant_turn_number],
                      }))
                    }}
                  >
                    {isEvaluationExpanded ? 'Hide evidence' : 'Show evidence'}
                  </Button>
                  {isEvaluationExpanded && (
                    <>
                      <div className={styles.evaluationDetails}>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Attack Type</Text>
                          <Text className={styles.evaluationDetailValue}>
                            {turnEvaluation.attack_family || 'None detected'}
                            {turnEvaluation.attack_subtype ? ` / ${turnEvaluation.attack_subtype}` : ''}
                          </Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Attack Intent</Text>
                          <Text className={styles.evaluationDetailValue}>{turnEvaluation.attack_intent || 'none_detected'}</Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Expected Behavior</Text>
                          <Text className={styles.evaluationDetailValue}>{turnEvaluation.expected_behavior_text}</Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Outcome Safety</Text>
                          <Text className={styles.evaluationDetailValue}>{turnEvaluation.outcome_safety || 'safe'}</Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Response Safety</Text>
                          <Text className={styles.evaluationDetailValue}>
                            {(turnEvaluation.response_safety_label || 'UNKNOWN') +
                              (turnEvaluation.response_safety_risk ? ` / ${turnEvaluation.response_safety_risk}` : '')}
                          </Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Refusal Strength</Text>
                          <Text className={styles.evaluationDetailValue}>{turnEvaluation.refusal_strength || 'N/A'}</Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Response Behavior</Text>
                          <Text className={styles.evaluationDetailValue}>{turnEvaluation.response_behavior_class || 'UNKNOWN'}</Text>
                        </div>
                        {turnEvaluation.grounding_verdict && (
                          <div className={styles.evaluationDetailItem}>
                            <Text className={styles.evaluationDetailLabel}>Grounding</Text>
                            <Text className={styles.evaluationDetailValue}>
                              {turnEvaluation.grounding_verdict}
                              {turnEvaluation.grounding_risk ? ` / ${turnEvaluation.grounding_risk}` : ''}
                            </Text>
                          </div>
                        )}
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Full Reason</Text>
                          <Text className={styles.evaluationDetailValue}>{turnEvaluation.full_reason}</Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Matched Rules</Text>
                          <Text className={styles.evaluationDetailValue}>{formatRuleList(turnEvaluation.matched_rules)}</Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Detected Entities</Text>
                          <Text className={styles.evaluationDetailValue}>{formatDetectedEntities(turnEvaluation.detected_entities)}</Text>
                        </div>
                        <div className={styles.evaluationDetailItem}>
                          <Text className={styles.evaluationDetailLabel}>Context References</Text>
                          <Text className={styles.evaluationDetailValue}>{formatContextReferences(turnEvaluation.context_references)}</Text>
                        </div>
                        {turnEvaluation.grounding_reason && (
                          <div className={styles.evaluationDetailItem}>
                            <Text className={styles.evaluationDetailLabel}>Grounding Reason</Text>
                            <Text className={styles.evaluationDetailValue}>{turnEvaluation.grounding_reason}</Text>
                          </div>
                        )}
                      </div>
                      <div className={styles.retrievalEvidenceBlock} data-testid={`retrieval-evidence-${turnEvaluation.assistant_turn_number}`}>
                        <Text className={styles.evaluationDetailLabel}>Retrieved Evidence</Text>
                        {message.retrievalEvidence && message.retrievalEvidence.length > 0 ? (
                          <div className={styles.retrievalEvidenceList}>
                            {message.retrievalEvidence.map((evidence, retrievalIndex) => (
                              <div
                                key={`${turnEvaluation.assistant_turn_number}-${retrievalIndex}-${evidence.fileId || evidence.fileName || evidence.citation || 'evidence'}`}
                                className={styles.retrievalEvidenceItem}
                              >
                                <div className={styles.retrievalEvidenceItemHeader}>
                                  <Text className={styles.retrievalEvidenceTitle}>
                                    {evidence.fileName || evidence.fileId || `Evidence ${retrievalIndex + 1}`}
                                  </Text>
                                  {(evidence.retrievalRank != null || evidence.retrievalScore != null) && (
                                    <Text className={styles.retrievalEvidenceMeta}>
                                      {evidence.retrievalRank != null ? `Rank ${evidence.retrievalRank}` : ''}
                                      {evidence.retrievalRank != null && evidence.retrievalScore != null ? ' | ' : ''}
                                      {evidence.retrievalScore != null ? `Score ${evidence.retrievalScore}` : ''}
                                    </Text>
                                  )}
                                </div>
                                {evidence.fileName && evidence.fileId && evidence.fileName !== evidence.fileId && (
                                  <Text className={styles.retrievalEvidenceMeta}>File ID: {evidence.fileId}</Text>
                                )}
                                {!evidence.fileName && evidence.fileId && (
                                  <Text className={styles.retrievalEvidenceMeta}>File ID: {evidence.fileId}</Text>
                                )}
                                {evidence.citation && (
                                  <Text className={styles.retrievalEvidenceMeta}>Citation: {evidence.citation}</Text>
                                )}
                                {evidence.snippet && (
                                  <Text className={styles.retrievalEvidenceSnippet}>{evidence.snippet}</Text>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <Text className={styles.retrievalEvidenceEmpty}>No retrieval evidence returned</Text>
                        )}
                      </div>
                      <div className={styles.retrievalEvidenceBlock} data-testid={`evidence-center-${turnEvaluation.assistant_turn_number}`}>
                        <Text className={styles.evaluationDetailLabel}>Evidence Center</Text>
                        {evidenceCenterReference ? (
                          <>
                            <Text className={styles.retrievalEvidenceMeta}>
                              Related normalized Evidence Center record: {evidenceCenterReference}
                            </Text>
                            {onOpenEvidenceCenter && (
                              <Button appearance="secondary" size="small" onClick={() => onOpenEvidenceCenter(evidenceCenterReference)}>
                                Open related evidence
                              </Button>
                            )}
                          </>
                        ) : (
                          <Text className={styles.retrievalEvidenceEmpty}>
                            This turn is scored in the interactive audit transcript. No normalized Evidence Center record exists yet.
                          </Text>
                        )}
                      </div>
                      <div className={styles.evaluationMetaRow}>
                        <Text className={styles.evaluationTurnLabel}>
                          Latest user prompt: {turnEvaluation.latest_user_prompt || 'Conversation context'}
                        </Text>
                      </div>
                    </>
                  )}
                </div>
              )}

              {!isUser && !message.isLoading && (
                <div className={styles.messageActions} data-testid={`message-actions-${index}`}>
                  {onCopyToInput &&
                    (() => {
                      const disabled = Boolean(noTargetSelected || isSingleTurn || isOperatorLocked || isCrossTarget)
                      const tip = noTargetSelected
                        ? 'Cannot copy - no target selected'
                        : isSingleTurn
                          ? 'Cannot copy - target is single-turn'
                          : isOperatorLocked
                            ? 'Cannot copy - you are not the operator of this attack'
                            : isCrossTarget
                              ? 'Cannot copy - conversation used a different target'
                              : 'Copy to input box in this conversation'
                      return (
                        <Tooltip content={tip} relationship="label">
                          <Button
                            appearance="subtle"
                            size="small"
                            icon={<ArrowReplyRegular />}
                            disabled={disabled}
                            onClick={() => onCopyToInput(index)}
                            data-testid={`copy-to-input-btn-${index}`}
                            style={{ minWidth: 'auto', padding: '2px' }}
                          />
                        </Tooltip>
                      )
                    })()}

                  {onCopyToNewConversation &&
                    (() => {
                      const disabled = Boolean(noTargetSelected || isOperatorLocked || isCrossTarget)
                      const tip = noTargetSelected
                        ? 'Cannot copy - no target selected'
                        : isOperatorLocked
                          ? 'Cannot add to this attack - you are not the operator'
                          : isCrossTarget
                            ? 'Cannot add to this attack - conversation used a different target'
                            : 'Copy to input box in a new conversation'
                      return (
                        <Tooltip content={tip} relationship="label">
                          <Button
                            appearance="subtle"
                            size="small"
                            icon={<ArrowForwardRegular />}
                            disabled={disabled}
                            onClick={() => onCopyToNewConversation(index)}
                            data-testid={`copy-to-new-conv-btn-${index}`}
                            style={{ minWidth: 'auto', padding: '2px' }}
                          />
                        </Tooltip>
                      )
                    })()}

                  {onBranchConversation &&
                    (() => {
                      const disabled = Boolean(noTargetSelected || isSingleTurn || isOperatorLocked || isCrossTarget)
                      const tip = noTargetSelected
                        ? 'Cannot branch - no target selected'
                        : isSingleTurn
                          ? 'Cannot branch - target is single-turn'
                          : isOperatorLocked
                            ? 'Cannot add to this attack - you are not the operator'
                            : isCrossTarget
                              ? 'Cannot add to this attack - conversation used a different target'
                              : 'Branch into new conversation'
                      return (
                        <Tooltip content={tip} relationship="label">
                          <Button
                            appearance="subtle"
                            size="small"
                            icon={<BranchForkRegular />}
                            disabled={disabled}
                            onClick={() => onBranchConversation(index)}
                            data-testid={`branch-conv-btn-${index}`}
                            style={{ minWidth: 'auto', padding: '2px' }}
                          />
                        </Tooltip>
                      )
                    })()}

                  {(() => {
                    const singleTurnBlock = isSingleTurn && !noTargetSelected
                    if (onBranchAttack && !singleTurnBlock) {
                      return (
                        <Tooltip content="Branch into new attack" relationship="label">
                          <Button
                            appearance="subtle"
                            size="small"
                            icon={<ChatAddRegular />}
                            onClick={() => onBranchAttack(index)}
                            data-testid={`branch-attack-btn-${index}`}
                            style={{ minWidth: 'auto', padding: '2px' }}
                          />
                        </Tooltip>
                      )
                    }
                    const tip = noTargetSelected
                      ? 'Cannot branch - no target selected'
                      : singleTurnBlock
                        ? 'Cannot branch - target is single-turn'
                        : undefined
                    if (!tip) {
                      return null
                    }
                    return (
                      <Tooltip content={tip} relationship="label">
                        <Button
                          appearance="subtle"
                          size="small"
                          icon={<ChatAddRegular />}
                          disabled
                          data-testid={`branch-attack-btn-${index}`}
                          style={{ minWidth: 'auto', padding: '2px' }}
                        />
                      </Tooltip>
                    )
                  })()}

                  {message.attachments &&
                    message.attachments
                      .filter(att => att.type !== 'file')
                      .map((att, mediaIndex) => (
                        <Tooltip key={mediaIndex} content={`Download ${att.name}`} relationship="label">
                          <Button
                            appearance="subtle"
                            size="small"
                            icon={<ArrowDownloadRegular />}
                            onClick={() => handleDownload(att)}
                            data-testid={`download-btn-${index}-${mediaIndex}`}
                            style={{ minWidth: 'auto', padding: '2px' }}
                          />
                        </Tooltip>
                      ))}

                  {!isUser && message.content && !disableInlineScoring && !turnEvaluation && null}
                </div>
              )}

              <div className={styles.messageFooter}>
                <Text className={styles.timestamp}>{timestamp}</Text>
                <Text className={styles.role}>{message.role}</Text>
              </div>
            </div>
          </div>
        )
      })}
      <div ref={messagesEndRef} />
    </div>
  )
}
