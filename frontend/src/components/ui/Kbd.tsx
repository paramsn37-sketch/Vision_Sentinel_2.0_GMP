import type { ReactNode } from 'react'

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="num inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-line bg-bg px-1 text-[11px] leading-none text-muted">
      {children}
    </kbd>
  )
}
