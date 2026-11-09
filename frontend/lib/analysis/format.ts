import type { AnalysisResult } from './types'

export function formatAnalysisAsText(result: AnalysisResult): string {
  const lines = [
    'Comic Analyst — Panel 01 → Panel 02',
    '',
    `Transition type: ${result.transitionType}`,
    result.transitionDescription,
    '',
    'Why this fits',
    result.whyThisFits,
  ]

  if (result.question && result.questionAnswer) {
    lines.push('', 'Your question', result.question, '', 'Answer', result.questionAnswer)
  }

  return lines.join('\n')
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const ACCEPTED_TYPES = ['image/png', 'image/jpeg']
const ACCEPTED_EXTENSIONS = /\.(png|jpe?g)$/i

export function isAcceptedImage(file: File): boolean {
  return ACCEPTED_TYPES.includes(file.type) || (!file.type && ACCEPTED_EXTENSIONS.test(file.name))
}
