import * as D from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from './cn'

interface Props {
  open: boolean
  onOpenChange: (v: boolean) => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
  className?: string
}

/** Side drawer for details that keep the list visible beside them (no scrim click-blocking on wide screens). */
export function Drawer({ open, onOpenChange, title, description, children, footer, className }: Props) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="vs-fade fixed inset-0 z-40 bg-(--scrim) lg:bg-transparent" />
        <D.Content
          className={cn(
            'vs-drawer fixed inset-y-0 right-0 z-50 flex w-full max-w-[560px] flex-col border-l border-line bg-raised shadow-float outline-none',
            className,
          )}
        >
          <header className="flex shrink-0 items-start justify-between gap-4 border-b border-line px-5 py-4">
            <div className="min-w-0">
              <D.Title className="text-lg font-semibold">{title}</D.Title>
              {description ? (
                <D.Description className="mt-0.5 text-xs text-muted">{description}</D.Description>
              ) : (
                <D.Description className="sr-only">Details</D.Description>
              )}
            </div>
            <D.Close className="press rounded-sm p-1 text-muted hover:bg-hover hover:text-fg" aria-label="Close">
              <X className="size-4" />
            </D.Close>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
          {footer && <footer className="flex shrink-0 items-center gap-2 border-t border-line px-5 py-3">{footer}</footer>}
        </D.Content>
      </D.Portal>
    </D.Root>
  )
}

export function Dialog({ open, onOpenChange, title, description, children, footer, className }: Props) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="vs-fade fixed inset-0 z-40 bg-(--scrim)" />
        <D.Content
          className={cn(
            'vs-dialog fixed top-1/2 left-1/2 z-50 flex max-h-[85vh] w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-md border border-line bg-raised shadow-float outline-none',
            className,
          )}
        >
          <header className="px-5 pt-5">
            <D.Title className="text-lg font-semibold">{title}</D.Title>
            {description ? (
              <D.Description className="mt-1 text-sm text-muted">{description}</D.Description>
            ) : (
              <D.Description className="sr-only">Dialog</D.Description>
            )}
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && <footer className="flex justify-end gap-2 px-5 pb-5">{footer}</footer>}
        </D.Content>
      </D.Portal>
    </D.Root>
  )
}
