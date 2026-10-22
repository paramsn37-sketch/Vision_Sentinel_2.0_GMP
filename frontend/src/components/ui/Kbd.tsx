import { cn } from './cn'
import type { ReactNode } from 'react'

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd className={cn('num inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-line bg-bg px-1 text-[11px] leading-none text-muted', className)}>
      {children}
    </kbd>
  )
}
