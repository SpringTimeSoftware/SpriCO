import type {
  BackendMessage,
  BackendMessagePiece,
  Message,
  MessageAttachment,
  MessageError,
  MessagePieceRequest,
  RetrievalEvidenceItem,
} from '../types'

/**
 * Read a File and return its contents as a base64-encoded string (no data URI prefix).
 */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // Strip the data:...;base64, prefix
      const base64 = result.split(',')[1] || ''
      resolve(base64)
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

/**
 * Map a frontend MIME type to the backend PromptDataType convention.
 */
export function mimeTypeToDataType(mimeType: string): string {
  if (mimeType.startsWith('image/')) return 'image_path'
  if (mimeType.startsWith('audio/')) return 'audio_path'
  if (mimeType.startsWith('video/')) return 'video_path'
  return 'binary_path'
}

/**
 * Map a backend `converted_value_data_type` to a frontend attachment type.
 */
export function dataTypeToAttachmentType(dataType: string): 'image' | 'audio' | 'video' | 'file' {
  if (dataType.includes('image')) return 'image'
  if (dataType.includes('audio')) return 'audio'
  if (dataType.includes('video')) return 'video'
  return 'file'
}

/**
 * Build a data URI from base64 content and a MIME type.
 */
export function buildDataUri(base64Value: string, mimeType: string): string {
  return `data:${mimeType};base64,${base64Value}`
}

/**
 * Determine a default MIME type for a backend data type when none is provided.
 */
function defaultMimeForDataType(dataType: string): string {
  if (dataType.includes('image')) return 'image/png'
  if (dataType.includes('audio')) return 'audio/wav'
  if (dataType.includes('video')) return 'video/mp4'
  return 'application/octet-stream'
}

/**
 * Check if a backend data type represents non-text media content.
 */
function isMediaDataType(dataType: string): boolean {
  return dataType.includes('image') || dataType.includes('audio') || dataType.includes('video') || dataType.includes('binary')
}

/**
 * Check if a backend data type represents reasoning/thinking content.
 */
function isReasoningDataType(dataType: string): boolean {
  return dataType === 'reasoning'
}

function isToolCallDataType(dataType: string): boolean {
  return dataType === 'tool_call'
}

type JsonRecord = Record<string, unknown>

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function toStringValue(value: unknown): string | undefined {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed ? trimmed : undefined
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return undefined
}

function toNumberValue(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

function firstString(record: JsonRecord, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = toStringValue(record[key])
    if (value) {
      return value
    }
  }
  return undefined
}

function firstNumber(record: JsonRecord, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = toNumberValue(record[key])
    if (value !== undefined) {
      return value
    }
  }
  return undefined
}

function collectTextValues(value: unknown, depth = 0): string[] {
  if (depth > 3 || value == null) {
    return []
  }
  const direct = toStringValue(value)
  if (direct) {
    return [direct]
  }
  if (Array.isArray(value)) {
    return value.flatMap(item => collectTextValues(item, depth + 1))
  }
  if (!isRecord(value)) {
    return []
  }
  const candidates = ['text', 'value', 'snippet', 'excerpt', 'quote', 'content', 'retrieved_text_excerpt']
  const collected: string[] = []
  for (const key of candidates) {
    if (key in value) {
      collected.push(...collectTextValues(value[key], depth + 1))
    }
  }
  return collected
}

function extractSnippet(record: JsonRecord): string | undefined {
  const snippetFields = [
    'snippet',
    'text',
    'excerpt',
    'retrieved_text_excerpt',
    'quote',
    'content',
    'matched_content',
  ]
  for (const field of snippetFields) {
    if (!(field in record)) {
      continue
    }
    const values = collectTextValues(record[field]).filter(Boolean)
    if (values.length > 0) {
      return values.join('\n')
    }
  }
  return undefined
}

function formatCitation(record: JsonRecord): string | undefined {
  const parts: string[] = []
  const type = firstString(record, ['type', 'annotation_type'])
  const label = firstString(record, ['citation_label', 'label'])
  const filename = firstString(record, ['filename', 'file_name', 'document_name'])
  const fileId = firstString(record, ['file_id', 'document_id'])
  const page = firstNumber(record, ['page', 'page_no', 'page_number'])
  const index = firstNumber(record, ['index', 'rank', 'retrieval_rank'])

  if (type) parts.push(type)
  if (label) parts.push(label)
  if (filename) parts.push(filename)
  if (!filename && fileId) parts.push(fileId)
  if (page !== undefined) parts.push(`page ${page}`)
  if (index !== undefined) parts.push(`rank ${index}`)

  const quote = firstString(record, ['quote'])
  if (quote) {
    parts.push(`"${quote}"`)
  }

  return parts.length > 0 ? parts.join(' | ') : undefined
}

function hasRenderableRetrievalEvidence(item: RetrievalEvidenceItem): boolean {
  return Boolean(
    item.fileId ||
      item.fileName ||
      item.snippet ||
      item.citation ||
      item.retrievalRank !== undefined ||
      item.retrievalScore !== undefined,
  )
}

function normalizeRetrievalItem(
  entry: JsonRecord,
  {
    source,
    toolType,
    fallbackToolType,
  }: {
    source: string | undefined
    toolType: string | undefined
    fallbackToolType: string | undefined
  },
): RetrievalEvidenceItem | null {
  const item: RetrievalEvidenceItem = {
    source,
    toolType: toolType || fallbackToolType,
    fileId: firstString(entry, ['file_id', 'document_id', 'id']) ?? null,
    fileName: firstString(entry, ['filename', 'file_name', 'document_name', 'title']) ?? null,
    snippet: extractSnippet(entry) ?? null,
    citation: formatCitation(entry) ?? null,
    retrievalRank: firstNumber(entry, ['retrieval_rank', 'rank', 'index', 'position']) ?? null,
    retrievalScore: firstNumber(entry, ['retrieval_score', 'score', 'similarity', 'relevance_score']) ?? null,
    raw: entry,
  }

  return hasRenderableRetrievalEvidence(item) ? item : null
}

function extractRetrievalEvidenceFromMetadata(metadata?: Record<string, unknown> | null): RetrievalEvidenceItem[] {
  if (!metadata || !isRecord(metadata.retrieval_evidence)) {
    return []
  }

  const retrievalEvidence = metadata.retrieval_evidence
  const source = toStringValue(retrievalEvidence.source)
  const toolType = toStringValue(retrievalEvidence.tool_type)
  const normalized: RetrievalEvidenceItem[] = []

  const rawResults = retrievalEvidence.results
  if (Array.isArray(rawResults)) {
    for (const result of rawResults) {
      if (!isRecord(result)) {
        continue
      }
      const item = normalizeRetrievalItem(result, {
        source,
        toolType,
        fallbackToolType: 'retrieval_result',
      })
      if (item) {
        normalized.push(item)
      }
    }
  }

  const rawAnnotations = retrievalEvidence.response_annotations
  if (Array.isArray(rawAnnotations)) {
    for (const annotation of rawAnnotations) {
      if (!isRecord(annotation)) {
        continue
      }
      const item = normalizeRetrievalItem(annotation, {
        source,
        toolType,
        fallbackToolType: 'response_annotation',
      })
      if (item) {
        normalized.push(item)
      }
    }
  }

  return normalized
}

/**
 * Extract summary texts from a reasoning piece's value.
 * The value is JSON like: {"type": "reasoning", "summary": [{"type": "summary_text", "text": "..."}]}
 * Falls back to displaying content or a placeholder when no summaries are available.
 */
function extractReasoningSummaries(value: string): string[] {
  try {
    const parsed = JSON.parse(value)
    if (parsed?.summary && Array.isArray(parsed.summary)) {
      const texts = parsed.summary
        .filter((s: { type?: string; text?: string }) => s.text)
        .map((s: { text: string }) => s.text)
      if (texts.length > 0) return texts
    }
    // If summaries are empty but there's readable content, show that
    if (typeof parsed?.content === 'string' && parsed.content.trim()) {
      return [parsed.content]
    }
    // Reasoning occurred but content is encrypted or empty
    if (parsed?.type === 'reasoning') {
      return ['(Reasoning was performed but details are not available)']
    }
  } catch {
    // If not valid JSON, use the raw value if non-empty
    if (value.trim()) return [value]
  }
  return []
}

/**
 * Build a frontend MessageAttachment from a backend piece.
 *
 * When `source` is `'converted'` (the default), uses `converted_value*` fields.
 * When `source` is `'original'`, uses `original_value*` fields instead.
 */
function pieceToAttachment(
  piece: BackendMessagePiece,
  source: 'converted' | 'original' = 'converted',
): MessageAttachment | null {
  const isOriginal = source === 'original'
  const dataType = isOriginal ? piece.original_value_data_type : piece.converted_value_data_type
  const value = isOriginal ? piece.original_value : piece.converted_value
  const mimeField = isOriginal ? piece.original_value_mime_type : piece.converted_value_mime_type

  if (!isMediaDataType(dataType) || !value) return null

  const mime = mimeField || defaultMimeForDataType(dataType)
  // Detect base64-encoded content while excluding file paths and URL schemes.
  // Base64 charset includes '/' so naive regex would match relative paths.
  const looksLikePathOrScheme = /^[A-Za-z]:\\/.test(value) || // Windows path
    value.startsWith('/') ||                                   // Unix absolute path
    /^[a-z][a-z0-9+.-]*:/i.test(value)                        // URI scheme (file:, blob:, etc.)
  const isBase64 = !looksLikePathOrScheme &&
    value.length >= 16 && /^[A-Za-z0-9+/=\n]+$/.test(value)
  const url = isBase64 ? buildDataUri(value, mime) : value
  const prefix = isOriginal ? 'original_' : ''
  const filename = isOriginal ? piece.original_filename : piece.converted_filename
  const fallbackName = `${prefix}${dataType}_${piece.piece_id.slice(0, 8)}`

  return {
    type: dataTypeToAttachmentType(dataType),
    name: filename || fallbackName,
    url,
    mimeType: mime,
    size: value.length,
    pieceId: piece.piece_id,
    metadata: piece.prompt_metadata || undefined,
  }
}

/**
 * Extract an error from a backend message piece, if any.
 */
function pieceToError(piece: BackendMessagePiece): MessageError | undefined {
  if (piece.response_error && piece.response_error !== 'none') {
    return {
      type: piece.response_error,
      description: piece.response_error_description || undefined,
    }
  }
  return undefined
}

/**
 * Convert a single backend Message DTO to a frontend Message for rendering.
 */
export function backendMessageToFrontend(msg: BackendMessage): Message {
  const textParts: string[] = []
  const originalTextParts: string[] = []
  const attachments: MessageAttachment[] = []
  const originalAttachments: MessageAttachment[] = []
  const reasoningSummaries: string[] = []
  const retrievalEvidence: RetrievalEvidenceItem[] = []
  let error: MessageError | undefined

  for (const piece of msg.pieces) {
    // Check for errors
    const pieceError = pieceToError(piece)
    if (pieceError && !error) {
      error = pieceError
    }

    retrievalEvidence.push(...extractRetrievalEvidenceFromMetadata(piece.prompt_metadata))

    // Extract reasoning summaries from reasoning-type pieces
    if (isReasoningDataType(piece.converted_value_data_type)) {
      const summaries = extractReasoningSummaries(piece.converted_value)
      reasoningSummaries.push(...summaries)
      continue
    }

    // Tool-call payloads (for example file_search_call results) should not render
    // as the visible assistant response. Their evidence remains available via
    // prompt_metadata and is shown in the existing "Retrieved Evidence" block.
    if (isToolCallDataType(piece.converted_value_data_type) || isToolCallDataType(piece.original_value_data_type)) {
      continue
    }

    // Extract text content from text-type pieces (converted)
    if (!isMediaDataType(piece.converted_value_data_type)) {
      if (piece.converted_value) {
        textParts.push(piece.converted_value)
      }
    }

    // Extract original text content
    if (piece.original_value && !isMediaDataType(piece.original_value_data_type)) {
      originalTextParts.push(piece.original_value)
    }

    // Extract media attachments (converted)
    const att = pieceToAttachment(piece)
    if (att) {
      attachments.push(att)
    }

    // Extract original media attachments
    const origAtt = pieceToAttachment(piece, 'original')
    if (origAtt) {
      originalAttachments.push(origAtt)
    }
  }

  const role = ['simulated_assistant', 'assistant', 'system'].includes(msg.role)
    ? msg.role
    : msg.role === 'developer' ? 'system' : 'user'

  const convertedContent = textParts.join('\n')
  const originalContent = originalTextParts.join('\n')

  // Only include originalContent when it actually differs from converted
  const hasTextDiff = originalContent !== '' && originalContent !== convertedContent
  const hasMediaDiff = originalAttachments.length > 0 &&
    JSON.stringify(originalAttachments.map(a => a.url)) !== JSON.stringify(attachments.map(a => a.url))

  return {
    role: role as Message['role'],
    content: convertedContent,
    timestamp: msg.created_at,
    turnNumber: msg.turn_number,
    attachments: attachments.length > 0 ? attachments : undefined,
    retrievalEvidence: retrievalEvidence.length > 0 ? retrievalEvidence : undefined,
    error,
    reasoningSummaries: reasoningSummaries.length > 0 ? reasoningSummaries : undefined,
    originalContent: hasTextDiff ? originalContent : undefined,
    originalAttachments: hasMediaDiff ? originalAttachments : undefined,
  }
}

/**
 * Convert all backend messages to frontend messages.
 */
export function backendMessagesToFrontend(messages: BackendMessage[]): Message[] {
  return messages.map(backendMessageToFrontend)
}

/**
 * Convert a frontend MessageAttachment (with File) to a backend MessagePieceRequest.
 */
export async function attachmentToMessagePieceRequest(att: MessageAttachment): Promise<MessagePieceRequest> {
  let base64Value = ''
  if (att.file) {
    base64Value = await fileToBase64(att.file)
  } else if (att.url.startsWith('data:')) {
    base64Value = att.url.split(',')[1] || ''
  } else {
    base64Value = att.url
  }

  return {
    data_type: mimeTypeToDataType(att.mimeType),
    original_value: base64Value,
    mime_type: att.mimeType,
    original_prompt_id: att.pieceId,
    prompt_metadata: att.metadata,
  }
}

/**
 * Build the pieces array for an AddMessageRequest from text + attachments.
 */
export async function buildMessagePieces(
  text: string,
  attachments: MessageAttachment[]
): Promise<MessagePieceRequest[]> {
  const pieces: MessagePieceRequest[] = []

  // Check for video_id in video attachments (needed for remix mode)
  const videoId = attachments
    .filter(a => a.type === 'video')
    .map(a => a.metadata?.video_id)
    .find(id => id != null)

  // Add text piece if present
  if (text.trim()) {
    pieces.push({
      data_type: 'text',
      original_value: text,
      prompt_metadata: videoId ? { video_id: videoId } : undefined,
    })
  }

  // Add attachment pieces
  for (const att of attachments) {
    pieces.push(await attachmentToMessagePieceRequest(att))
  }

  return pieces
}
