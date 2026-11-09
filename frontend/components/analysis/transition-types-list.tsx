'use client'

import { useId, useState } from 'react'
import { cn } from '@/lib/utils'
import { TRANSITION_TYPES, type TransitionTypeName } from '@/lib/analysis/transition-types'

export function TransitionTypesList({ current }: { current: TransitionTypeName }) {
  const [open, setOpen] = useState(false)
  const regionId = useId()
  const headingId = useId()

  return (
    <div className="mt-10">
      <ToggleLink open={open} controls={regionId} onClick={() => setOpen((v) => !v)} />

      <div
        id={regionId}
        role="region"
        aria-labelledby={headingId}
        inert={!open}
        className={cn(
          'grid transition-[grid-template-rows,opacity] duration-300 ease-out motion-reduce:transition-none',
          open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
        )}
      >
        <div className="overflow-hidden">
          <div className="mt-6 border-t border-border pt-8">
            <h4
              id={headingId}
              className="font-mono text-[11px] font-medium tracking-[0.14em] text-muted-foreground"
            >
              THE SIX TRANSITION TYPES
            </h4>

            <ol className="mt-5 max-w-3xl divide-y divide-border border-y border-border">
              {TRANSITION_TYPES.map((type, index) => {
                const isCurrent = type.name === current
                return (
                  <li
                    key={type.name}
                    aria-current={isCurrent ? 'true' : undefined}
                    className={cn(
                      'grid grid-cols-[2.5rem_1fr] gap-x-2 border-l-2 py-5 pr-4 pl-4',
                      isCurrent ? 'border-l-teal bg-teal/[0.06]' : 'border-l-transparent',
                    )}
                  >
                    <span className="pt-0.5 font-mono text-[11px] text-muted-foreground">
                      0{index + 1}
                    </span>
                    <div>
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <span className="text-[15px] font-medium">{type.name}</span>
                        {isCurrent && (
                          <span className="font-mono text-[10px] font-medium tracking-[0.14em] text-teal">
                            CURRENT
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground text-pretty">
                        {type.description}
                      </p>
                    </div>
                  </li>
                )
              })}
            </ol>

            <div className="mt-5">
              <ToggleLink open={open} controls={regionId} onClick={() => setOpen(false)} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ToggleLink({
  open,
  controls,
  onClick,
}: {
  open: boolean
  controls: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onClick}
      className="group inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-teal underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      {open ? 'Show less' : 'Know more'}
      <span
        aria-hidden="true"
        className={cn(
          'transition-transform duration-200 motion-reduce:transition-none',
          open ? 'group-hover:-translate-y-0.5' : 'group-hover:translate-x-0.5',
        )}
      >
        {open ? '↑' : '→'}
      </span>
    </button>
  )
}
