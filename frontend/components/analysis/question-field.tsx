'use client'

import { forwardRef, useId } from 'react'

const EXAMPLES = [
  "What changed in the character's expression?",
  'What action took place?',
  'What changed in the background?',
  'What happened to the character?',
  'Focus on the dialogue.',
]

type QuestionFieldProps = {
  value: string
  disabled?: boolean
  onChange: (value: string) => void
  onSubmit: () => void
}

export const QuestionField = forwardRef<HTMLTextAreaElement, QuestionFieldProps>(
  function QuestionField({ value, disabled, onChange, onSubmit }, ref) {
    const id = useId()
    const hintId = useId()

    return (
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <label htmlFor={id} className="text-sm font-medium">
            Optional question
          </label>
          <p id={hintId} className="text-xs text-muted-foreground">
            Leave blank for a complete transition analysis.
          </p>
        </div>
        <textarea
          ref={ref}
          id={id}
          rows={3}
          value={value}
          disabled={disabled}
          maxLength={500}
          aria-describedby={hintId}
          placeholder="Ask about something specific in the transition..."
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing || event.keyCode === 229) return
            if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
              event.preventDefault()
              onSubmit()
            }
          }}
          className="mt-2 block w-full resize-y rounded-sm border border-input bg-card px-3.5 py-3 text-sm leading-relaxed transition-colors placeholder:text-muted-foreground/80 hover:border-border-strong focus-visible:border-teal focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-ring/30 disabled:opacity-60"
        />
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 font-mono text-[11px] tracking-wide text-muted-foreground">
            EXAMPLES
          </span>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              disabled={disabled}
              onClick={() => onChange(example)}
              className="rounded-sm border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-foreground/40 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-60"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    )
  },
)
