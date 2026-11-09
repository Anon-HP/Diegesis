export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-[1100px] flex-col gap-2 px-5 py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between md:px-6">
        <p>
          <span className="font-medium text-foreground">Comic Analyst</span> · Visual transition
          analysis
        </p>
        <p className="font-mono text-[11px]">© 2026 · Prototype — results are simulated</p>
      </div>
    </footer>
  )
}
