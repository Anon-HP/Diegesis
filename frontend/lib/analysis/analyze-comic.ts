import { findTransition, TRANSITION_TYPES, type TransitionLabel } from './transition-types'
import { AnalysisError, type AnalysisResult } from './types'

/** Requests go to the Next.js server, which proxies /api/* to the Python backend (see next.config.mjs). */
const ANALYZE_URL = '/api/analyze'

type BackendResponse = {
  label: string
  confidence: number
  probabilities: Record<string, number>
  method: string
  warnings?: string[]
  elapsed_ms?: number
}

/**
 * Sends both panels to the trained model and returns its prediction. The backend always returns exactly
 * one of the six McCloud labels; anything else is treated as an error rather than displayed.
 */
export async function analyzeComic(
  image1: File,
  image2: File,
  { signal }: { signal?: AbortSignal } = {},
): Promise<AnalysisResult> {
  const body = new FormData()
  body.append('first', image1)
  body.append('second', image2)

  let res: Response
  try {
    res = await fetch(ANALYZE_URL, { method: 'POST', body, signal })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new AnalysisError('Could not reach the analysis server. Is the backend running (python serve.py)?')
  }

  if (!res.ok) {
    const message = await readErrorMessage(res)
    throw new AnalysisError(message)
  }

  const data = (await res.json()) as BackendResponse
  const transition = findTransition(data.label)
  if (!transition || typeof data.confidence !== 'number') {
    throw new AnalysisError('The server returned an unexpected response.')
  }

  const probabilities = Object.fromEntries(
    TRANSITION_TYPES.map((t) => [t.label, Number(data.probabilities?.[t.label] ?? 0)]),
  ) as Record<TransitionLabel, number>

  return {
    label: transition.label,
    transitionType: transition.name,
    transitionDescription: transition.description,
    confidence: data.confidence,
    probabilities,
    warnings: data.warnings ?? [],
    method: data.method,
    elapsedMs: data.elapsed_ms ?? 0,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  }
}

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.error?.message === 'string') return data.error.message
  } catch {
    // non-JSON body (e.g. proxy error page when the backend is down)
  }
  if (res.status === 500 || res.status === 502 || res.status === 503 || res.status === 504) {
    return 'The analysis server is unavailable. Check that the backend is running (python serve.py).'
  }
  return 'The analysis could not be completed. Please try again.'
}
