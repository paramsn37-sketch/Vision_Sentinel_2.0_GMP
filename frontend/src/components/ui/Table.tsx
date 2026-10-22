import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from './cn'

export function Table({ className, ...rest }: HTMLAttributes<HTMLTableElement>) {
  return <table className={cn('w-full border-collapse text-sm', className)} {...rest} />
}

export function Th({ className, align, ...rest }: ThHTMLAttributes<HTMLTableCellElement> & { align?: 'right' }) {
  return (
    <th
      scope="col"
      className={cn(
        'sticky top-0 z-[1] h-9 border-b border-line bg-sunken px-3 text-xs font-medium whitespace-nowrap text-muted',
        align === 'right' ? 'text-right' : 'text-left',
        className,
      )}
      {...rest}
    />
  )
}

export function Td({ className, align, ...rest }: TdHTMLAttributes<HTMLTableCellElement> & { align?: 'right' }) {
  return (
    <td
      className={cn('h-(--row-height) border-b border-line px-3 whitespace-nowrap', align === 'right' && 'num text-right', className)}
      {...rest}
    />
  )
}

/** Selected rows carry the 1 px selection line on their left edge (inset shadow, so the layout does not shift). */
export function Tr({ selected, className, ...rest }: HTMLAttributes<HTMLTableRowElement> & { selected?: boolean }) {
  return (
    <tr
      aria-selected={selected}
      className={cn(
        'transition-colors duration-(--dur-fast)',
        selected ? 'bg-hover shadow-[inset_1px_0_0_var(--accent)]' : 'hover:bg-hover/60',
        className,
      )}
      {...rest}
    />
  )
}
