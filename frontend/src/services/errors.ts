import type { AxiosError } from 'axios'

/**
 * Normalized error from any API call.
 *
 * Callers get a consistent shape regardless of whether the failure was a
 * network timeout, an Axios HTTP error with RFC 7807 JSON body, a proxy
 * returning HTML, or a non-Axios throw.
 */
export interface ApiError {
  /** HTTP status code, or null when the request never reached the server. */
  status: number | null
  /** Human-readable error message extracted from the response or synthesized. */
  detail: string
  /** RFC 7807 `type` URI, if the backend included one. */
  type?: string
  /** Application-specific error code, when a route returns structured errors. */
  code?: string
  /** Field-level validation details, normalized from SpriCO or RFC 7807 payloads. */
  details?: Array<{ field?: string; reason: string }>
  /** Human-readable recovery steps supplied by the backend. */
  nextSteps?: string[]
  /** True when no HTTP response was received (DNS failure, CORS block, etc.). */
  isNetworkError: boolean
  /** True when the request exceeded the configured timeout. */
  isTimeout: boolean
  /** The original thrown value, for advanced callers or logging. */
  raw: unknown
}

/**
 * Convert any caught value into a normalized {@link ApiError}.
 *
 * Handles:
 * - Axios errors with an RFC 7807 JSON body (`response.data.detail`)
 * - Axios errors with a plain-string body (e.g. nginx 502 HTML)
 * - Axios errors with no response at all (network / CORS)
 * - Axios timeout errors (`code === 'ECONNABORTED'`)
 * - Plain `Error` instances
 * - String throws
 * - Anything else (`unknown`)
 */
export function toApiError(err: unknown): ApiError {
  // Axios errors carry an `isAxiosError` flag.
  if (isAxiosError(err)) {
    // Timeout
    if (err.code === 'ECONNABORTED') {
      return {
        status: null,
        detail: 'Request timed out. The server may be busy — please try again.',
        isNetworkError: false,
        isTimeout: true,
        raw: err,
      }
    }

    // No response at all (network error, DNS, CORS, etc.)
    if (!err.response) {
      return {
        status: null,
        detail: 'Network error — check that the backend is running and reachable.',
        isNetworkError: true,
        isTimeout: false,
        raw: err,
      }
    }

    // We have an HTTP response — try to extract RFC 7807 detail
    const { status, data } = err.response
    const { detail, type, code, details, nextSteps } = extractDetail(data)

    return {
      status,
      detail: detail || `Server error (${status})`,
      type,
      code,
      details,
      nextSteps,
      isNetworkError: false,
      isTimeout: false,
      raw: err,
    }
  }

  // Plain Error
  if (err instanceof Error) {
    return {
      status: null,
      detail: err.message || 'An unexpected error occurred.',
      isNetworkError: false,
      isTimeout: false,
      raw: err,
    }
  }

  // String throw
  if (typeof err === 'string') {
    return {
      status: null,
      detail: err,
      isNetworkError: false,
      isTimeout: false,
      raw: err,
    }
  }

  // Unknown throw (null, undefined, number, object, etc.)
  return {
    status: null,
    detail: 'An unexpected error occurred.',
    isNetworkError: false,
    isTimeout: false,
    raw: err,
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Type-guard for Axios errors. */
function isAxiosError(err: unknown): err is AxiosError {
  return typeof err === 'object' && err !== null && (err as AxiosError).isAxiosError === true
}

/**
 * Extract `detail` and `type` from an Axios response body.
 *
 * The body may be:
 * - An RFC 7807 JSON object with `.detail` and optionally `.type`
 * - A plain string (e.g. nginx HTML error page)
 * - Something else entirely (null, number, etc.)
 */
function extractDetail(data: unknown): {
  detail: string | undefined
  type: string | undefined
  code: string | undefined
  details: Array<{ field?: string; reason: string }> | undefined
  nextSteps: string[] | undefined
} {
  if (typeof data === 'string') {
    return { detail: data, type: undefined, code: undefined, details: undefined, nextSteps: undefined }
  }
  if (typeof data === 'object' && data !== null) {
    const obj = data as Record<string, unknown>
    const code = typeof obj.error === 'string' ? obj.error : undefined
    const type = typeof obj.type === 'string' ? obj.type : undefined
    const message = typeof obj.message === 'string' ? obj.message : undefined
    const nextSteps = Array.isArray(obj.next_steps)
      ? obj.next_steps.filter((item): item is string => typeof item === 'string')
      : undefined

    let details: Array<{ field?: string; reason: string }> | undefined
    if (Array.isArray(obj.details)) {
      details = normalizeDetails(obj.details)
    } else if (Array.isArray(obj.errors)) {
      details = normalizeDetails(obj.errors)
    }

    if (Array.isArray(obj.detail)) {
      const detailList = normalizeDetails(obj.detail)
      const unsupportedCrossDomain = detailList.some(detail =>
        (detail.field ?? '').endsWith('cross_domain_override') &&
        detail.reason.toLowerCase().includes('extra')
      )
      return {
        detail: unsupportedCrossDomain
          ? 'Cannot start scanner run. The scanner request included an unsupported field: cross_domain_override. Backend schema has now been updated; retry the scan.'
          : (message ?? 'Request validation failed'),
        type,
        code: code ?? 'validation_failed',
        details: detailList.length ? detailList : details,
        nextSteps,
      }
    }
    if (typeof obj.detail === 'string') {
      return { detail: obj.detail, type, code, details, nextSteps }
    }
    if (typeof obj.detail === 'object' && obj.detail !== null) {
      const detailObj = obj.detail as Record<string, unknown>
      const nestedDetails = Array.isArray(detailObj.details) ? normalizeDetails(detailObj.details) : details
      const nestedSteps = Array.isArray(detailObj.next_steps)
        ? detailObj.next_steps.filter((item): item is string => typeof item === 'string')
        : nextSteps
      return {
        detail: typeof detailObj.message === 'string' ? detailObj.message : message,
        type,
        code: typeof detailObj.error === 'string' ? detailObj.error : code,
        details: nestedDetails,
        nextSteps: nestedSteps,
      }
    }

    return { detail: message, type, code, details, nextSteps }
  }
  return { detail: undefined, type: undefined, code: undefined, details: undefined, nextSteps: undefined }
}

function normalizeDetails(items: unknown[]): Array<{ field?: string; reason: string }> {
  return items
    .map(item => {
      if (typeof item === 'string') {
        return { reason: item }
      }
      if (typeof item === 'object' && item !== null) {
        const obj = item as Record<string, unknown>
        const loc = Array.isArray(obj.loc)
          ? obj.loc.map(segment => String(segment)).join('.')
          : undefined
        const reason = typeof obj.reason === 'string'
          ? obj.reason
          : typeof obj.message === 'string'
            ? obj.message
            : typeof obj.msg === 'string'
              ? obj.msg
            : undefined
        if (!reason) return null
        return {
          field: typeof obj.field === 'string' ? obj.field : loc,
          reason,
        }
      }
      return null
    })
    .filter((item): item is { field?: string; reason: string } => item !== null)
}
