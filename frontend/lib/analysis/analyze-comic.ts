import { getTransitionDescription, type TransitionTypeName } from './transition-types'
import { AnalysisError, type AnalysisResult } from './types'

const MOCK_LATENCY_MS = 2000

/**
 * Analyzes the transition between two comic panels.
 *
 * Temporary mock implementation. To connect a real vision API, replace the body
 * with a request such as:
 *
 *   const body = new FormData()
 *   body.append('first', image1)
 *   body.append('second', image2)
 *   if (question) body.append('question', question)
 *   const res = await fetch('/api/analyze', { method: 'POST', body, signal })
 *   if (!res.ok) throw new AnalysisError()
 *   return (await res.json()) as AnalysisResult
 *
 * The API must always return exactly one `transitionType`.
 */
export async function analyzeComic(
  image1: File,
  image2: File,
  question?: string,
  { signal }: { signal?: AbortSignal } = {},
): Promise<AnalysisResult> {
  await wait(MOCK_LATENCY_MS, signal)

  // Lets the error state be previewed by uploading a file whose name contains "fail".
  if (/fail/i.test(image1.name) || /fail/i.test(image2.name)) {
    throw new AnalysisError()
  }

  const transitionType: TransitionTypeName = 'Action-to-Action'
  const trimmed = question?.trim()

  return {
    transitionType,
    transitionDescription: getTransitionDescription(transitionType),
    whyThisFits:
      'Both panels follow the same character in the same room. In the first she is seated and reading; in the second she has risen from the chair and turned toward the door, with the letter drawn mid-fall. The second panel shows the next stage of a single continuous action — getting up in response to an interruption — rather than a new scene or a shift to another subject.',
    ...(trimmed ? { question: trimmed, questionAnswer: answerQuestion(trimmed) } : {}),
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  }
}

function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    })
  })
}

const QUESTION_ANSWERS: { match: RegExp; answer: string }[] = [
  {
    match: /expression|face|emotion|feel|react|mood/i,
    answer:
      'The character’s expression changes from neutral concentration in the first panel to visible surprise in the second. Her brows lift, her eyes widen, and her mouth opens slightly — a startle reaction rather than fear or anger.',
  },
  {
    match: /\b(action|happen\w*|occur\w*|do|did|event|mov\w*)\b/i,
    answer:
      'Between the panels, the character is interrupted while reading and gets up abruptly. She pushes her chair back, stands, and turns toward the doorway, dropping the letter as she does.',
  },
  {
    match: /background|setting|location|place|room|light|environment|scene/i,
    answer:
      'The setting stays the same office, but the second panel widens the frame to reveal a partly open door on the right. A long shadow now extends across the floor from that doorway, changing the lighting and signalling that someone is outside.',
  },
  {
    match: /dialogue|text|speech|bubble|caption|say|said|word|lettering/i,
    answer:
      'The first panel contains only a time caption, “Tuesday, 11:42 PM.” The second panel drops the caption and introduces a single speech bubble from the character: “Who’s there?” Narration shifts from a neutral, establishing voice to the character’s own reaction.',
  },
  {
    match: /character|she|he|her|him|they|person|woman|man|clothing/i,
    answer:
      'The character goes from calmly reading at her desk to standing alert and facing the door. Her clothing and appearance are unchanged; the difference lies entirely in her posture, expression, and attention.',
  },
]

function answerQuestion(question: string): string {
  return (
    QUESTION_ANSWERS.find((entry) => entry.match.test(question))?.answer ??
    'The most relevant change is the interruption: the character stops reading and turns toward the door, and a shadow from the doorway suggests someone has arrived. Only a moment separates the two panels.'
  )
}
