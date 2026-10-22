import * as T from '@radix-ui/react-tabs'
import type { ReactNode } from 'react'
import { cn } from './cn'

export const Tabs = T.Root
export const TabPanel = T.Content

/** Tabs sit on a 1 px rule; the active tab is marked by the 1 px selection line lying on that rule. */
export function TabList({ tabs, className }: { tabs: { value: string; label: ReactNode }[]; className?: string }) {
  return (
    <T.List className={cn('flex gap-5 border-b border-line', className)}>
      {tabs.map((t) => (
        <T.Trigger
          key={t.value}
          value={t.value}
          className={cn(
            'relative -mb-px h-9 text-sm text-muted transition-colors duration-(--dur-fast) hover:text-fg',
            'data-[state=active]:text-fg',
            'after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-accent after:opacity-0 after:transition-opacity after:duration-(--dur-fast)',
            'data-[state=active]:after:opacity-100',
          )}
        >
          {t.label}
        </T.Trigger>
      ))}
    </T.List>
  )
}
