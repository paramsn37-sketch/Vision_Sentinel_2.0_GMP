import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { Mark } from '@/components/shell/Mark'
import { Button, Field, Input } from '@/components/ui'
import { api, ApiError } from '@/lib/api/client'
import { keys } from '@/lib/api/hooks'

export function LoginPage() {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const qc = useQueryClient()

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const me = await api.post<{ user: string; csrf_token: string }>('/auth/login', { username, password })
      qc.setQueryData(keys.me, me)
      const next = params.get('next')
      navigate(next && next.startsWith('/') && !next.startsWith('//') ? next : '/live', { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? 'Too many attempts. Wait a minute, then try again.'
          : err instanceof ApiError && err.status === 401
            ? 'That username and password do not match.'
            : `Could not sign in: ${(err as Error).message}`,
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-full place-items-center bg-bg px-4">
      <div className="w-full max-w-[360px]">
        <div className="mb-8 flex items-center gap-3 text-fg">
          <Mark className="size-8" />
          <div>
            <h1 className="text-lg font-semibold">Vision Sentinel</h1>
            <p className="text-xs text-muted">Site safety monitoring</p>
          </div>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-4 rounded-md border border-line bg-sunken p-5" noValidate>
          <Field label="Username">
            {(p) => <Input {...p} autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />}
          </Field>
          <Field
            label="Password"
            error={error}
            hint="First run: the password is in data/runtime/ADMIN_PASSWORD.txt, or set VS_ADMIN_PASSWORD."
          >
            {(p) => (
              <Input {...p} type="password" autoComplete="current-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} required />
            )}
          </Field>
          <Button type="submit" variant="primary" loading={busy} disabled={!password} className="mt-1">
            Sign in
          </Button>
        </form>
      </div>
    </main>
  )
}
