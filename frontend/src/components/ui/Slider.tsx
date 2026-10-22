import * as S from '@radix-ui/react-slider'

export function Slider({
  value,
  onChange,
  min = 0,
  max = 1,
  step = 0.01,
  label,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  label: string
}) {
  return (
    <S.Root
      className="relative flex h-5 w-full touch-none items-center select-none"
      value={[value]}
      min={min}
      max={max}
      step={step}
      onValueChange={([v]) => onChange(v)}
    >
      <S.Track className="relative h-[3px] grow rounded-full bg-line-strong/50">
        <S.Range className="absolute h-full rounded-full bg-accent" />
      </S.Track>
      <S.Thumb
        aria-label={label}
        className="block size-3.5 rounded-full border border-line-strong bg-fg transition-transform duration-(--dur-fast) hover:scale-110"
      />
    </S.Root>
  )
}
