import type { ReactNode } from 'react'
import { cn } from './cn'

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('vs-skeleton rounded-sm bg-hover', className)} />
}

/** Says what is missing and what to do next, with at most one action. */
export function EmptyState({
  title,
  children,
  action,
  icon,
  className,
}: {
  title: string
  children?: ReactNode
  action?: ReactNode
  icon?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-start gap-2 px-5 py-8 text-sm', className)}>
      {icon && <div className="text-subtle">{icon}</div>}
      <p className="font-medium text-fg">{title}</p>
      {children && <div className="max-w-[60ch] text-muted">{children}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div role="alert" className="flex flex-col items-start gap-2 px-5 py-6 text-sm">
      <p className="font-medium text-danger">Could not load this</p>
      <p className="max-w-[60ch] text-muted">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="text-accent underline">
          Try again
        </button>
      )}
    </div>
  )
}
