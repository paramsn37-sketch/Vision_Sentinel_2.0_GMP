import * as S from '@radix-ui/react-switch'
import { cn } from './cn'

export function Switch({
  checked,
  onChange,
  label,
  id,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label?: string
  id?: string
  disabled?: boolean
}) {
  return (
    <S.Root
      id={id}
      checked={checked}
      onCheckedChange={onChange}
      aria-label={label}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-[18px] w-8 shrink-0 items-center rounded-full border border-line-strong bg-sunken',
        'transition-colors duration-(--dur-fast) ease-out data-[state=checked]:border-accent data-[state=checked]:bg-accent',
        'disabled:cursor-not-allowed disabled:opacity-45',
      )}
    >
      <S.Thumb
        className={cn(
          'block size-3 translate-x-[2px] rounded-full bg-line-strong transition-transform duration-(--dur-ui) ease-out',
          'data-[state=checked]:translate-x-[15px] data-[state=checked]:bg-on-accent',
        )}
      />
    </S.Root>
  )
}

export function Checkbox({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <label className={cn('inline-flex items-center gap-2 text-sm', disabled && 'opacity-45')}>
      <input
        type="checkbox"
        className="size-4 rounded-sm accent-(--accent)"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  )
}
