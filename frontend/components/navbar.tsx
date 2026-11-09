import { ThemeToggle } from './theme-toggle'

export function Navbar() {
  return (
    <header className="border-b border-border">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-14 max-w-[1100px] items-center justify-between px-5 md:px-6"
      >
        <a
          href="#top"
          className="flex shrink-0 items-center gap-2.5 rounded-sm text-[15px] whitespace-nowrap font-medium tracking-tight focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
        >
          <PanelsMark />
          Comic Analyst
        </a>
        <ul className="flex items-center text-[13px] whitespace-nowrap text-muted-foreground sm:gap-2 sm:text-sm">
          <li>
            <NavLink href="#how-it-works">How it works</NavLink>
          </li>
          <li>
            <NavLink href="#about">About</NavLink>
          </li>
          <li>
            <ThemeToggle />
          </li>
        </ul>
      </nav>
    </header>
  )
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      className="rounded-sm px-1.5 py-1.5 transition-colors sm:px-2 hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
    >
      {children}
    </a>
  )
}

function PanelsMark() {
  return (
    <svg
      aria-hidden="true"
      width="20"
      height="14"
      viewBox="0 0 20 14"
      fill="none"
      className="text-foreground"
    >
      <rect x="0.75" y="0.75" width="8" height="12.5" rx="0.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11.25" y="0.75" width="8" height="12.5" rx="0.5" className="fill-teal stroke-teal" strokeWidth="1.5" />
    </svg>
  )
}
