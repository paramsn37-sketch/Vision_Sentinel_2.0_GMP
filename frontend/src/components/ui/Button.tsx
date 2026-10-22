import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from './cn'
import { Tooltip } from './Tooltip'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

const variants: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent hover:brightness-110 disabled:brightness-100',
  secondary: 'bg-sunken text-fg border border-line-strong/60 hover:bg-hover',
  ghost: 'text-fg hover:bg-hover',
  danger: 'bg-sunken text-danger border border-danger/60 hover:bg-danger-bg',
}
const sizes: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-sm gap-2',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', loading, icon, className, children, disabled, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'press inline-flex shrink-0 items-center justify-center rounded-sm font-medium whitespace-nowrap select-none',
        'transition-[background-color,border-color,color,filter,transform] duration-(--dur-fast) ease-out',
        'disabled:cursor-not-allowed disabled:opacity-45',
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  )
})

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  shortcut?: string
  size?: Size
  active?: boolean
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, shortcut, size = 'md', active, className, children, type = 'button', ...rest },
  ref,
) {
  return (
    <Tooltip content={label} shortcut={shortcut}>
      <button
        ref={ref}
        type={type}
        aria-label={label}
        aria-pressed={active}
        className={cn(
          'press inline-flex shrink-0 items-center justify-center rounded-sm text-muted',
          'transition-[background-color,color,transform] duration-(--dur-fast) ease-out',
          'hover:bg-hover hover:text-fg disabled:cursor-not-allowed disabled:opacity-45',
          active && 'bg-hover text-fg',
          size === 'sm' ? 'size-7' : 'size-8',
          className,
        )}
        {...rest}
      >
        {children}
      </button>
    </Tooltip>
  )
})
