'use client'

import { ArrowRight, Check, Copy, PenLine, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { formatAnalysisAsText } from '@/lib/analysis/format'
import type { AnalysisResult as Result, PanelImage } from '@/lib/analysis/types'
import { TransitionTypesList } from './transition-types-list'

type AnalysisResultProps = {
  result: Result
  panels: [PanelImage, PanelImage]
  onAnalyzeAgain: () => void
  onAskAnother: () => void
}

export function AnalysisResult({ result, panels, onAnalyzeAgain, onAskAnother }: AnalysisResultProps) {
  return (
    <section
      aria-labelledby="analysis-heading"
      className="animate-in fade-in slide-in-from-bottom-1 duration-500"
    >
      <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-[11px] font-medium tracking-[0.14em] text-teal">
            PANEL 01 → PANEL 02
          </p>
          <h3 id="analysis-heading" className="mt-2 text-2xl font-medium tracking-tight">
            Analysis
          </h3>
        </div>
        <PanelReference panels={panels} />
      </div>

      <div className="mt-10 flex max-w-3xl flex-col gap-10">
        <div>
          <Eyebrow>TRANSITION TYPE</Eyebrow>
          <p className="mt-3 text-3xl font-medium tracking-tight text-balance sm:text-4xl">
            {result.transitionType}
          </p>
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground italic text-pretty">
            {result.transitionDescription}
          </p>
        </div>

        <div>
          <Eyebrow>WHY THIS FITS</Eyebrow>
          <p className="mt-3 text-[17px] leading-relaxed text-pretty">{result.whyThisFits}</p>
        </div>

        {result.question && result.questionAnswer && (
          <div className="flex flex-col gap-6 border-t border-border pt-8">
            <div>
              <Eyebrow>YOUR QUESTION</Eyebrow>
              <p className="mt-2 border-l-2 border-border-strong pl-4 text-[15px] text-muted-foreground italic">
                {result.question}
              </p>
            </div>
            <div>
              <Eyebrow>ANSWER</Eyebrow>
              <p className="mt-2 text-[17px] leading-relaxed text-pretty">{result.questionAnswer}</p>
            </div>
          </div>
        )}
      </div>

      <TransitionTypesList current={result.transitionType} />

      <ResultActions result={result} onAnalyzeAgain={onAnalyzeAgain} onAskAnother={onAskAnother} />
    </section>
  )
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[11px] font-medium tracking-[0.14em] text-muted-foreground">
      {children}
    </p>
  )
}

function PanelReference({ panels }: { panels: [PanelImage, PanelImage] }) {
  return (
    <figure className="flex items-center gap-2.5" aria-label="Analyzed panels">
      {panels.map((panel, index) => (
        <div key={panel.url} className="flex items-center gap-2.5">
          {index === 1 && (
            <ArrowRight aria-hidden="true" className="size-3.5 text-muted-foreground" strokeWidth={1.5} />
          )}
          <span className="font-mono text-[11px] text-muted-foreground">0{index + 1}</span>
          {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview */}
          <img
            src={panel.url}
            alt={`Panel 0${index + 1} thumbnail`}
            className="h-14 w-20 rounded-sm border border-border bg-muted object-contain p-1"
          />
        </div>
      ))}
    </figure>
  )
}

function ResultActions({
  result,
  onAnalyzeAgain,
  onAskAnother,
}: {
  result: Result
  onAnalyzeAgain: () => void
  onAskAnother: () => void
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(formatAnalysisAsText(result))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="mt-10 flex flex-wrap items-center gap-2 border-t border-border pt-6">
      <ActionButton onClick={handleCopy}>
        {copied ? (
          <Check aria-hidden="true" className="size-3.5 text-teal" strokeWidth={2} />
        ) : (
          <Copy aria-hidden="true" className="size-3.5" strokeWidth={1.75} />
        )}
        {copied ? 'Copied' : 'Copy'}
      </ActionButton>
      <ActionButton onClick={onAnalyzeAgain}>
        <RotateCcw aria-hidden="true" className="size-3.5" strokeWidth={1.75} />
        Analyze again
      </ActionButton>
      <ActionButton onClick={onAskAnother}>
        <PenLine aria-hidden="true" className="size-3.5" strokeWidth={1.75} />
        Ask another question
      </ActionButton>
      <span className="sr-only" aria-live="polite">
        {copied ? 'Analysis copied to clipboard' : ''}
      </span>
    </div>
  )
}

function ActionButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-border px-3 text-xs font-medium transition-colors hover:border-foreground/50 hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      {children}
    </button>
  )
}
