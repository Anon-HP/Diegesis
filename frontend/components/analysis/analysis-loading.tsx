import { Loader2 } from 'lucide-react'

export function AnalysisLoading() {
  return (
    <div role="status" aria-live="polite" className="animate-in fade-in duration-300">
      <div className="flex items-start gap-3">
        <Loader2
          aria-hidden="true"
          className="mt-0.5 size-4 animate-spin text-teal motion-reduce:animate-none"
          strokeWidth={1.75}
        />
        <div>
          <p className="text-sm font-medium">Analyzing panels...</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Comparing visual and narrative changes
          </p>
        </div>
      </div>
      <div className="mt-5 h-px w-full overflow-hidden bg-border">
        <div className="h-full w-full origin-left animate-progress bg-teal" />
      </div>
    </div>
  )
}
