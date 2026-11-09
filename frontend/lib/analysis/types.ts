import type { TransitionTypeName } from './transition-types'

export type PanelImage = {
  file: File
  url: string
}

export interface ComicAnalysis {
  transitionType: TransitionTypeName
  transitionDescription: string
  whyThisFits: string
  question?: string
  questionAnswer?: string
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
