import { AlertCircle } from 'lucide-react'

export function FormMessage({ message }: { message: string | null }) {
  return (
    <div aria-live="assertive" className="min-h-0">
      {message ? (
        <p
          role="alert"
          className="flex items-start gap-2 border-l-2 border-terracotta bg-terracotta/[0.06] px-3 py-2.5 text-sm text-terracotta-text animate-in fade-in duration-200"
        >
          <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" strokeWidth={1.75} />
          {message}
        </p>
      ) : null}
    </div>
  )
}
