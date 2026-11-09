'use client'

import { useEffect, useRef, useState } from 'react'
import { analyzeComic } from '@/lib/analysis/analyze-comic'
import type { AnalysisResult as Result, PanelImage } from '@/lib/analysis/types'
import { AnalysisLoading } from './analysis-loading'
import { AnalysisResult } from './analysis-result'
import { AnalyzeButton } from './analyze-button'
import { ComicPanelUploader } from './comic-panel-uploader'
import { FormMessage } from './form-message'
import { QuestionField } from './question-field'
import { TransitionIndicator } from './transition-indicator'

type Status = 'idle' | 'loading' | 'success' | 'error'
type Slot = 'first' | 'second'

const MESSAGES = {
  missingPanels: 'Please upload both panels before analyzing the transition.',
  invalidType: 'Unsupported file type. Please upload a PNG, JPG, or JPEG image.',
  failed: 'The analysis could not be completed. Please try again.',
}

export function AnalysisWorkspace() {
  const [panels, setPanels] = useState<Record<Slot, PanelImage | null>>({ first: null, second: null })
  const [question, setQuestion] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState<string | null>(null)

  const questionRef = useRef<HTMLTextAreaElement>(null)
  const outputRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const panelsRef = useRef(panels)
  panelsRef.current = panels

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      for (const panel of Object.values(panelsRef.current)) {
        if (panel) URL.revokeObjectURL(panel.url)
      }
    }
  }, [])

  const isLoading = status === 'loading'
  const bothReady = Boolean(panels.first && panels.second)
  const uploadedCount = Number(Boolean(panels.first)) + Number(Boolean(panels.second))

  const setPanel = (slot: Slot, file: File | null) => {
    const previous = panels[slot]
    if (previous) URL.revokeObjectURL(previous.url)
    const next = file ? { file, url: URL.createObjectURL(file) } : null
    setPanels((current) => ({ ...current, [slot]: next }))
    setError(null)
    setResult(null)
    setStatus('idle')
  }

  const scrollToOutput = () => {
    requestAnimationFrame(() => {
      outputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  const runAnalysis = async () => {
    if (!panels.first || !panels.second) {
      setError(MESSAGES.missingPanels)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setError(null)
    setResult(null)
    setStatus('loading')
    scrollToOutput()

    try {
      const next = await analyzeComic(panels.first.file, panels.second.file, question, {
        signal: controller.signal,
      })
      setResult(next)
      setStatus('success')
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(MESSAGES.failed)
      setStatus('error')
    }
  }

  const askAnother = () => {
    setQuestion('')
    questionRef.current?.focus({ preventScroll: true })
    questionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <section
      id="analyze"
      aria-labelledby="workspace-heading"
      className="mx-auto max-w-[1100px] px-5 md:px-6"
    >
      <div className="rounded-sm border border-border bg-card/60">
        <header className="flex flex-col gap-3 border-b border-border px-5 py-5 sm:flex-row sm:items-end sm:justify-between md:px-8 md:py-6">
          <div>
            <h2 id="workspace-heading" className="text-xl font-medium tracking-tight">
              Analyze a sequence
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Compare two panels and identify what happens between them.
            </p>
          </div>
          <p className="font-mono text-[11px] tracking-[0.12em] text-muted-foreground" aria-live="polite">
            <span className={uploadedCount === 2 ? 'text-teal' : 'text-foreground'}>{uploadedCount}</span>
            {' / 2 PANELS ADDED'}
          </p>
        </header>

        <div className="px-5 py-8 md:px-8 md:py-10">
          <div className="mx-auto max-w-[900px]">
            <div className="mb-6 text-center md:mb-8">
              {uploadedCount === 0 ? (
                <>
                  <p className="text-[15px] font-medium">Compare two moments. Understand the change.</p>
                  <p className="mt-1 text-sm text-muted-foreground">Upload two comic panels to begin.</p>
                </>
              ) : (
                <>
                  <p className="text-[15px] font-medium">
                    {bothReady ? 'Both panels added.' : 'One panel added.'}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {bothReady
                      ? 'Add an optional question, or analyze the full transition.'
                      : `Upload the ${panels.first ? 'second' : 'first'} panel to continue.`}
                  </p>
                </>
              )}
            </div>

            <div className="grid grid-cols-1 items-center gap-4 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:gap-6 lg:gap-10">
              <ComicPanelUploader
                number="01"
                ordinal="first"
                value={panels.first}
                disabled={isLoading}
                onSelect={(file) => setPanel('first', file)}
                onRemove={() => setPanel('first', null)}
                onInvalid={() => setError(MESSAGES.invalidType)}
              />
              <TransitionIndicator />
              <ComicPanelUploader
                number="02"
                ordinal="second"
                value={panels.second}
                disabled={isLoading}
                onSelect={(file) => setPanel('second', file)}
                onRemove={() => setPanel('second', null)}
                onInvalid={() => setError(MESSAGES.invalidType)}
              />
            </div>

            <div className="mt-8 flex flex-col gap-6 md:mt-10">
              <QuestionField
                ref={questionRef}
                value={question}
                disabled={isLoading}
                onChange={setQuestion}
                onSubmit={runAnalysis}
              />

              <FormMessage message={error} />

              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-muted-foreground">
                  {bothReady
                    ? question.trim()
                      ? 'Comic Analyst will focus on your question.'
                      : 'Comic Analyst will provide a complete transition analysis.'
                    : 'Both panels are required.'}
                </p>
                <AnalyzeButton ready={bothReady} loading={isLoading} onClick={runAnalysis} />
              </div>
            </div>
          </div>
        </div>

        <div ref={outputRef} className="scroll-mt-6">
          {(isLoading || (status === 'success' && result)) && (
            <div className="border-t border-border px-5 py-8 md:px-8 md:py-12">
              <div className="mx-auto max-w-[900px]">
                {isLoading ? (
                  <AnalysisLoading />
                ) : result && panels.first && panels.second ? (
                  <AnalysisResult
                    result={result}
                    panels={[panels.first, panels.second]}
                    onAnalyzeAgain={runAnalysis}
                    onAskAnother={askAnother}
                  />
                ) : null}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
