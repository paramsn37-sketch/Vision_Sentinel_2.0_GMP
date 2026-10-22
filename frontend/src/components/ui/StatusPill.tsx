import type { ReactNode } from 'react'
import { cn } from './cn'

export type Tone = 'danger' | 'warning' | 'ok' | 'info' | 'neutral'

const tones: Record<Tone, string> = {
  danger: 'bg-danger-bg text-danger',
  warning: 'bg-warning-bg text-warning',
  ok: 'bg-ok-bg text-ok',
  info: 'bg-accent-bg text-accent',
  neutral: 'bg-neutral-bg text-muted',
}
const dots: Record<Tone, string> = {
  danger: 'bg-danger',
  warning: 'bg-warning',
  ok: 'bg-ok',
  info: 'bg-accent',
  neutral: 'bg-subtle',
}

/** Colour always comes with a word: the pill never relies on colour alone. */
export function StatusPill({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex h-5 items-center gap-1.5 rounded-sm px-1.5 text-xs font-medium whitespace-nowrap',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function StatusDot({ tone, label }: { tone: Tone; label: string }) {
  return <span role="img" aria-label={label} title={label} className={cn('inline-block size-2 rounded-full', dots[tone])} />
}
