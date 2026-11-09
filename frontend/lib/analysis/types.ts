import type { TransitionLabel, TransitionTypeName } from './transition-types'

export type PanelImage = {
  file: File
  url: string
}

/** One model prediction for Panel 01 → Panel 02, as returned by the backend (POST /api/analyze). */
export interface ComicAnalysis {
  label: TransitionLabel
  transitionType: TransitionTypeName
  transitionDescription: string
  confidence: number
  /** Probability for each of the six labels (sums to 1). */
  probabilities: Record<TransitionLabel, number>
  warnings: string[]
  method: string
  elapsedMs: number
}

export type AnalysisResult = ComicAnalysis & {
  id: string
  createdAt: string
}

export class AnalysisError extends Error {
  constructor(message = 'The analysis could not be completed. Please try again.') {
    super(message)
    this.name = 'AnalysisError'
  }
}
