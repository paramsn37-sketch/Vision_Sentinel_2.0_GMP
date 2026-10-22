import * as S from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from './cn'

export interface Option<V extends string = string> {
  value: V
  label: string
}

export function Select<V extends string>({
  value,
  onChange,
  options,
  placeholder = 'Select',
  label,
  id,
  className,
  disabled,
}: {
  value: V | undefined
  onChange: (v: V) => void
  options: Option<V>[]
  placeholder?: string
  label?: string
  id?: string
  className?: string
  disabled?: boolean
}) {
  return (
    <S.Root value={value} onValueChange={(v) => onChange(v as V)} disabled={disabled}>
      <S.Trigger
        id={id}
        aria-label={label}
        className={cn(
          'inline-flex h-8 min-w-32 items-center justify-between gap-2 rounded-sm border border-line-strong/70 bg-sunken px-2.5 text-sm text-fg',
          'transition-colors duration-(--dur-fast) hover:border-line-strong data-[placeholder]:text-subtle',
          'disabled:cursor-not-allowed disabled:opacity-45',
          className,
        )}
      >
        <S.Value placeholder={placeholder} />
        <S.Icon>
          <ChevronDown className="size-4 text-muted" aria-hidden />
        </S.Icon>
      </S.Trigger>
      <S.Portal>
        <S.Content
          position="popper"
          sideOffset={4}
          className="vs-pop z-50 max-h-80 min-w-(--radix-select-trigger-width) overflow-hidden rounded-md border border-line bg-raised shadow-float"
        >
          <S.Viewport className="p-1">
            {options.map((o) => (
              <S.Item
                key={o.value}
                value={o.value}
                className="relative flex h-8 cursor-default items-center rounded-sm pr-8 pl-2.5 text-sm text-fg outline-none select-none data-[highlighted]:bg-hover"
              >
                <S.ItemText>{o.label}</S.ItemText>
                <S.ItemIndicator className="absolute right-2">
                  <Check className="size-4 text-accent" aria-hidden />
                </S.ItemIndicator>
              </S.Item>
            ))}
          </S.Viewport>
        </S.Content>
      </S.Portal>
    </S.Root>
  )
}
