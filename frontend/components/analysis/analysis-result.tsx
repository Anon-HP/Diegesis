'use client'

import { ArrowRight, Check, Copy, RotateCcw, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { formatAnalysisAsText, formatPercent } from '@/lib/analysis/format'
import { TRANSITION_TYPES } from '@/lib/analysis/transition-types'
import { cn } from '@/lib/utils'
import type { AnalysisResult as Result, PanelImage } from '@/lib/analysis/types'
import { TransitionTypesList } from './transition-types-list'

type AnalysisResultProps = {
  result: Result
  panels: [PanelImage, PanelImage]
  onAnalyzeAgain: () => void
}

export function AnalysisResult({ result, panels, onAnalyzeAgain }: AnalysisResultProps) {
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
          <p className="mt-2 font-mono text-[12px] tracking-[0.08em] text-teal">
            CONFIDENCE {formatPercent(result.confidence)}
          </p>
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground italic text-pretty">
            {result.transitionDescription}
          </p>
        </div>

        {result.warnings.length > 0 && (
          <ul className="flex flex-col gap-2" aria-label="Notes about this prediction">
            {result.warnings.map((warning) => (
              <li
                key={warning}
                className="flex items-start gap-2 border-l-2 border-ochre pl-3 text-sm leading-relaxed text-muted-foreground"
              >
                <TriangleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-ochre" strokeWidth={1.75} />
                {warning}
              </li>
            ))}
          </ul>
        )}

        <ProbabilityBreakdown result={result} />
      </div>

      <TransitionTypesList current={result.label} />

      <ResultActions result={result} onAnalyzeAgain={onAnalyzeAgain} />
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

function ProbabilityBreakdown({ result }: { result: Result }) {
  return (
    <div>
      <Eyebrow>MODEL PROBABILITIES</Eyebrow>
      <ul className="mt-4 flex flex-col gap-2.5">
        {TRANSITION_TYPES.map((type) => {
          const p = result.probabilities[type.label]
          const isCurrent = type.label === result.label
          return (
            <li key={type.label} className="grid grid-cols-[9.5rem_1fr_3rem] items-center gap-3 text-sm">
              <span className={cn(isCurrent ? 'font-medium text-foreground' : 'text-muted-foreground')}>
                {type.name}
              </span>
              <span className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                <span
                  className={cn('block h-full rounded-full', isCurrent ? 'bg-teal' : 'bg-border-strong')}
                  style={{ width: `${Math.max(p * 100, 0.5)}%` }}
                />
              </span>
              <span className="text-right font-mono text-[12px] text-muted-foreground">{formatPercent(p)}</span>
            </li>
          )
        })}
      </ul>
      <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
        Prediction from a model trained on Golden Age US comics with machine-generated labels. On held-out
        comics it agrees with the reference label about 38% of the time — treat it as a suggestion, not a verdict.
      </p>
    </div>
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
}: {
  result: Result
  onAnalyzeAgain: () => void
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
