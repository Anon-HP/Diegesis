import { Columns2, ImageUp, TextCursorInput, type LucideIcon } from 'lucide-react'

const STEPS: { number: string; title: string; text: string; icon: LucideIcon }[] = [
  { number: '01', title: 'Upload', text: 'Add the first and second comic panels.', icon: ImageUp },
  {
    number: '02',
    title: 'Specify',
    text: 'Optionally tell Comic Analyst what to focus on.',
    icon: TextCursorInput,
  },
  { number: '03', title: 'Analyze', text: 'Review the transition between the two panels.', icon: Columns2 },
]

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      aria-labelledby="how-heading"
      className="mx-auto max-w-[1100px] scroll-mt-8 px-5 pt-24 md:px-6 md:pt-32"
    >
      <h2 id="how-heading" className="text-2xl font-medium tracking-tight md:text-3xl">
        How it works
      </h2>
      <ol className="mt-10 grid gap-10 md:grid-cols-3 md:gap-8">
        {STEPS.map((step) => (
          <li key={step.number} className="border-t border-foreground/80 pt-5">
            <div className="flex items-center justify-between">
              <p className="font-mono text-[11px] font-medium tracking-[0.14em] text-muted-foreground">
                {step.number} — <span className="text-foreground">{step.title.toUpperCase()}</span>
              </p>
              <step.icon aria-hidden="true" className="size-4 text-teal" strokeWidth={1.5} />
            </div>
            <p className="mt-4 max-w-xs text-[15px] leading-relaxed text-muted-foreground">{step.text}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
