import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Button, Checkbox, Field, Input, Select, Switch } from '@/components/ui'
import { api, type ZoneIn } from '@/lib/api/client'
import { ppeTitle } from '@/lib/format'
import type { Pt } from './editor/geometry'

export type FormValues = Omit<ZoneIn, 'polygon'> & { rules: NonNullable<ZoneIn['rules']> & { required_ppe: string[] } }

const PPE = ['helmet', 'vest', 'gloves', 'boots', 'goggles'] as const

export function ZoneForm({
  value,
  onChange,
  points,
  canSave,
  saving,
  onSave,
  onCancel,
  onDelete,
  drawing,
}: {
  value: FormValues
  onChange: (v: FormValues) => void
  points: Pt[]
  canSave: boolean
  saving: boolean
  onSave: () => void
  onCancel: () => void
  onDelete?: () => void
  drawing: boolean
}) {
  const set = (patch: Partial<FormValues>) => onChange({ ...value, ...patch })
  const rule = (patch: Partial<FormValues['rules']>) => onChange({ ...value, rules: { ...value.rules, ...patch } })
  const body = useDebounced(JSON.stringify({ ...value, polygon: points }), 300)
  // Server-side validation is the source of truth (same rules as the pipeline).
  const check = useQuery({
    queryKey: ['zone-validate', body],
    queryFn: () => api.post<{ valid: boolean; errors: string[] }>('/zones/validate', JSON.parse(body)),
    enabled: points.length >= 3 && !drawing,
    staleTime: Infinity,
  })
  const errors = drawing ? [] : (check.data?.errors ?? [])
  const nameMissing = !value.name.trim()

  return (
    <form
      className="flex flex-col gap-4 p-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (canSave && !nameMissing && !errors.length) onSave()
      }}
    >
      <Field label="Name" error={nameMissing && !drawing ? 'Give the zone a name operators will recognise.' : undefined}>
        {(p) => <Input {...p} value={value.name} onChange={(e) => set({ name: e.target.value })} placeholder="e.g. Loading bay" maxLength={80} />}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Kind">
          {(p) => (
            <Select
              id={p.id}
              label="Kind"
              value={value.kind}
              onChange={(kind) =>
                set({
                  kind,
                  rules: { ...value.rules, no_entry: kind === 'restricted' ? true : value.rules.no_entry, required_ppe: kind === 'ppe_required' && !value.rules.required_ppe.length ? ['helmet', 'vest'] : value.rules.required_ppe },
                })
              }
              options={[
                { value: 'restricted', label: 'No entry' },
                { value: 'ppe_required', label: 'PPE required' },
                { value: 'hazard', label: 'Hazard area' },
              ]}
            />
          )}
        </Field>
        <Field label="Severity">
          {(p) => (
            <Select
              id={p.id}
              label="Severity"
              value={value.severity}
              onChange={(severity) => set({ severity })}
              options={[
                { value: 'high', label: 'High' },
                { value: 'medium', label: 'Medium' },
                { value: 'low', label: 'Low' },
              ]}
            />
          )}
        </Field>
      </div>

      <fieldset className="flex flex-col gap-3 border-t border-line pt-4">
        <legend className="mb-2 text-sm font-semibold">Rules</legend>
        <label className="flex items-start justify-between gap-3">
          <span>
            <span className="block text-sm">No entry</span>
            <span className="block text-xs text-muted">Anyone whose feet are inside raises an incident.</span>
          </span>
          <Switch label="No entry" checked={!!value.rules.no_entry} onChange={(v) => rule({ no_entry: v })} />
        </label>
        <div>
          <span className="block text-sm">Required PPE</span>
          <span className="mb-2 block text-xs text-muted">Missing items raise an incident after the configured delay.</span>
          <div className="grid grid-cols-2 gap-2">
            {PPE.map((item) => (
              <Checkbox
                key={item}
                label={ppeTitle(item)}
                checked={value.rules.required_ppe.includes(item)}
                onChange={(on) => rule({ required_ppe: on ? [...value.rules.required_ppe, item] : value.rules.required_ppe.filter((x) => x !== item) })}
              />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Max people" hint="Empty = no limit">
            {(p) => (
              <Input
                {...p}
                inputMode="numeric"
                value={value.rules.max_occupancy ?? ''}
                onChange={(e) => rule({ max_occupancy: e.target.value === '' ? null : Math.max(0, Math.floor(Number(e.target.value)) || 0) })}
              />
            )}
          </Field>
          <Field label="Max stay (s)" hint="Empty = no limit">
            {(p) => (
              <Input
                {...p}
                inputMode="decimal"
                value={value.rules.max_dwell_s ?? ''}
                onChange={(e) => rule({ max_dwell_s: e.target.value === '' ? null : Math.max(1, Number(e.target.value) || 1) })}
              />
            )}
          </Field>
        </div>
        <Field label="Active hours" hint="24 h range, e.g. 07:00-19:00. Empty = always.">
          {(p) => <Input {...p} value={value.rules.active_hours ?? ''} onChange={(e) => rule({ active_hours: e.target.value.trim() || null })} placeholder="always" />}
        </Field>
        <label className="flex items-center justify-between gap-3">
          <span className="text-sm">Enabled</span>
          <Switch label="Enabled" checked={value.enabled ?? true} onChange={(enabled) => set({ enabled })} />
        </label>
      </fieldset>

      {errors.length > 0 && (
        <ul role="alert" className="flex flex-col gap-1 text-xs text-danger">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      {drawing && <p className="text-xs text-muted">Finish the outline on the frame (Enter or click the first point), then save.</p>}

      <div className="flex items-center gap-2 border-t border-line pt-4">
        <Button type="submit" variant="primary" loading={saving} disabled={!canSave || nameMissing || errors.length > 0}>
          Save zone
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Discard changes
        </Button>
        {onDelete && (
          <Button variant="danger" className="ml-auto" onClick={onDelete}>
            Delete
          </Button>
        )}
      </div>
    </form>
  )
}

/** The value after it has stopped changing for `ms` (keeps validation to one request per pause in typing). */
function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}
