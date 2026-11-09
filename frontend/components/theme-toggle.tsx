'use client'

import { Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()

  return (
    <button
      type="button"
      onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
      className="flex items-center gap-1.5 rounded-sm px-2 py-1.5 transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
    >
      <Sun aria-hidden="true" className="size-3.5 dark:hidden" strokeWidth={1.75} />
      <Moon aria-hidden="true" className="hidden size-3.5 dark:block" strokeWidth={1.75} />
      <span className="sr-only sm:not-sr-only">Theme</span>
      <span className="sr-only">: switch between light and dark</span>
    </button>
  )
}
