import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'

type AnalyzeButtonProps = {
  ready: boolean
  loading: boolean
  onClick: () => void
}

/**
 * Uses aria-disabled instead of the native attribute so that a click while
 * incomplete can still surface the "upload both panels" message.
 */
export function AnalyzeButton({ ready, loading, onClick }: AnalyzeButtonProps) {
  const inactive = !ready || loading

  return (
    <button
      type="button"
      aria-disabled={inactive}
      onClick={() => {
        if (!loading) onClick()
      }}
      className={cn(
        'inline-flex h-10 items-center justify-center gap-2 rounded-sm px-5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        inactive
          ? 'cursor-not-allowed bg-muted text-muted-foreground'
          : 'bg-primary text-primary-foreground hover:bg-primary-hover',
      )}
    >
      {loading ? 'Analyzing…' : 'Analyze transition'}
      {!loading && <ArrowRight aria-hidden="true" className="size-4" strokeWidth={1.75} />}
    </button>
  )
}
