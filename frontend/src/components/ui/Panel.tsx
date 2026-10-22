import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from './cn'

/** A panel: sunken card with a title row. Panels sit darker than the ground; no shadow. */
export function Panel({
  title,
  actions,
  children,
  className,
  bodyClassName,
  ...rest
}: {
  title?: ReactNode
  actions?: ReactNode
  bodyClassName?: string
} & HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn('flex min-h-0 flex-col rounded-md border border-line bg-sunken', className)} {...rest}>
      {(title || actions) && (
        <header className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line px-4">
          {typeof title === 'string' ? <h2 className="text-sm font-semibold">{title}</h2> : title}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn('min-h-0 flex-1', bodyClassName)}>{children}</div>
    </section>
  )
}

/** A label above a figure with its unit. KPIs are type, not tiles. */
export function Metric({
  label,
  value,
  unit,
  note,
  tone,
}: {
  label: string
  value: ReactNode
  unit?: string
  note?: ReactNode
  tone?: 'danger' | 'warning' | 'ok'
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-xs text-muted">{label}</span>
      <span
        className={cn(
          'num text-xl leading-tight font-medium',
          tone === 'danger' && 'text-danger',
          tone === 'warning' && 'text-warning',
          tone === 'ok' && 'text-ok',
        )}
      >
        {value}
        {unit && <span className="ml-1 font-sans text-xs font-normal text-muted">{unit}</span>}
      </span>
      {note && <span className="text-xs text-subtle">{note}</span>}
    </div>
  )
}
