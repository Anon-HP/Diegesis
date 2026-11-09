export function Hero() {
  return (
    <section
      aria-labelledby="hero-heading"
      className="mx-auto max-w-[1100px] px-5 pt-14 pb-10 md:px-6 md:pt-20 md:pb-14"
    >
      <p className="flex items-center gap-2 font-mono text-[11px] font-medium tracking-[0.16em] text-teal">
        <span aria-hidden="true" className="inline-block size-1.5 bg-ochre" />
        VISUAL TRANSITION ANALYSIS
      </p>
      <h1
        id="hero-heading"
        className="mt-5 max-w-3xl text-4xl leading-[1.08] font-medium tracking-tight text-balance md:text-[3.25rem]"
      >
        Trace the Transition.
      </h1>
      <p className="mt-5 max-w-xl text-base leading-relaxed text-pretty text-muted-foreground md:text-lg">
        Upload two panels and Comic Analyst will identify the visual, contextual, and narrative
        changes between them.
      </p>
    </section>
  )
}
