import { cn } from './cn'

/** A radio group drawn as text options; the chosen one carries the 1 px selection line under its label. */
export function SegmentedControl<V extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: V
  onChange: (v: V) => void
  options: { value: V; label: string }[]
  label: string
  className?: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cn('inline-flex items-center gap-3', className)}>
      {options.map((o) => {
        const on = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => {
              const i = options.findIndex((x) => x.value === value)
              if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                e.preventDefault()
                const n = options[(i + (e.key === 'ArrowRight' ? 1 : options.length - 1)) % options.length]
                onChange(n.value)
                ;(e.currentTarget.parentElement?.querySelectorAll('button')[options.indexOf(n)] as HTMLElement)?.focus()
              }
            }}
            tabIndex={on ? 0 : -1}
            className={cn(
              'relative h-7 text-sm transition-colors duration-(--dur-fast) hover:text-fg',
              on ? 'text-fg' : 'text-muted',
              'after:absolute after:inset-x-0 after:bottom-0.5 after:h-px after:bg-accent after:transition-opacity after:duration-(--dur-fast)',
              on ? 'after:opacity-100' : 'after:opacity-0',
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
