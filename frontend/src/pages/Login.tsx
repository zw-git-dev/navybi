import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui'

export function LoginPage() {
  const { login, loginError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      await login(username, password)
      const from = (location.state as { from?: string } | null)?.from ?? '/'
      navigate(from, { replace: true })
    } catch {
      // loginError from context already covers this
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-accent text-lg font-bold text-white">
            N
          </div>
          <div className="text-center">
            <h1 className="text-lg font-semibold text-ink">NavyBI</h1>
            <p className="text-sm text-ink-muted">Sign in to continue</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="rounded-lg border border-border bg-surface p-6 shadow-card">
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-muted">Username</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-muted">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              />
            </div>

            {loginError && <p className="text-sm text-bad">{loginError}</p>}

            <Button type="submit" className="w-full" disabled={submitting || !username || !password}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </div>
        </form>

        <p className="mt-4 text-center text-xs text-ink-faint">
          Demo authentication only — local accounts seeded by <code>auth/seed_users.py</code>, not DoD PKI/CAC
          or an enterprise identity provider.
        </p>
      </div>
    </div>
  )
}
