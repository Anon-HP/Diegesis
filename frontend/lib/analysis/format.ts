import { TRANSITION_TYPES } from './transition-types'
import type { AnalysisResult } from './types'

export function formatPercent(p: number): string {
  return `${Math.round(p * 100)}%`
}

export function formatAnalysisAsText(result: AnalysisResult): string {
  const lines = [
    'Comic Analyst — Panel 01 → Panel 02',
    '',
    `Transition type: ${result.transitionType} (confidence ${formatPercent(result.confidence)})`,
    result.transitionDescription,
    '',
    'Model probabilities',
    ...TRANSITION_TYPES.map((t) => `  ${t.name}: ${formatPercent(result.probabilities[t.label])}`),
  ]
  if (result.warnings.length) lines.push('', 'Notes', ...result.warnings.map((w) => `  - ${w}`))
  return lines.join('\n')
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const ACCEPTED_TYPES = ['image/png', 'image/jpeg']
const ACCEPTED_EXTENSIONS = /\.(png|jpe?g)$/i
export const MAX_FILE_BYTES = 15 * 1024 * 1024

export function isAcceptedImage(file: File): boolean {
  return ACCEPTED_TYPES.includes(file.type) || (!file.type && ACCEPTED_EXTENSIONS.test(file.name))
}
