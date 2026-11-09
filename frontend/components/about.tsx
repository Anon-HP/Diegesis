export function About() {
  return (
    <section
      id="about"
      aria-labelledby="about-heading"
      className="mx-auto max-w-[1100px] scroll-mt-8 px-5 pt-24 pb-24 md:px-6 md:pt-32 md:pb-32"
    >
      <div className="grid gap-6 border-t border-border pt-10 md:grid-cols-[1fr_2fr] md:gap-12">
        <h2 id="about-heading" className="text-2xl font-medium tracking-tight md:text-3xl">
          About
        </h2>
        <div className="flex max-w-2xl flex-col gap-4 text-[15px] leading-relaxed text-muted-foreground">
          <p>
            In comics, much of the story happens in the gutter — the space between panels where the
            reader infers time, motion, and cause. Comic Analyst is built to make that inference
            explicit.
          </p>
          <p>
            It is intended for readers, students, editors, and researchers who want a careful,
            structured account of how one panel leads to the next: who moved, what changed in the
            scene, and what the text adds.
          </p>
        </div>
      </div>
    </section>
  )
}
