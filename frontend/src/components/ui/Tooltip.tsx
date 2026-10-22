import * as T from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'
import { Kbd } from './Kbd'

/** One provider for the app: after the first tooltip opens, the next opens without delay (skipDelayDuration). */
export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <T.Provider delayDuration={400} skipDelayDuration={300}>
      {children}
    </T.Provider>
  )
}

export function Tooltip({
  content,
  shortcut,
  side = 'top',
  children,
}: {
  content: ReactNode
  shortcut?: string
  side?: 'top' | 'right' | 'bottom' | 'left'
  children: ReactNode
}) {
  return (
    <T.Root>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          side={side}
          sideOffset={6}
          className="vs-pop z-50 flex items-center gap-2 rounded-sm border border-line bg-raised px-2 py-1 text-xs text-fg shadow-float"
        >
          {content}
          {shortcut && <Kbd>{shortcut}</Kbd>}
        </T.Content>
      </T.Portal>
    </T.Root>
  )
}
