import { ArrowDown, ArrowRight } from 'lucide-react'

export function TransitionIndicator() {
  return (
    <div
      aria-hidden="true"
      className="flex items-center justify-center gap-2 text-muted-foreground md:-mt-1 md:flex-col md:gap-1.5"
    >
      <span className="font-mono text-[10px] tracking-[0.16em]">TRANSITION</span>
      <ArrowRight className="hidden size-5 md:block" strokeWidth={1.25} />
      <ArrowDown className="size-4 md:hidden" strokeWidth={1.25} />
    </div>
  )
}
