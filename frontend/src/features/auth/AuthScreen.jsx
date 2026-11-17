import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../app/providers/AuthProvider.jsx'
import { useToast } from '../../app/providers/ToastProvider.jsx'
import Button from '../../components/ui/Button.jsx'
import Input, { inputClass } from '../../components/ui/Input.jsx'

/** Login / register gate — the only unauthenticated route. */
export default function AuthScreen() {
  const { login, register } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', fullName: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const set = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'register') {
        await register({
          email: form.email,
          password: form.password,
          full_name: form.fullName || null,
        })
        toast.info('Account created — signing you in…')
      }
      await login(form.email, form.password)
      toast.success('Welcome back to SecureVoice AI')
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Authentication failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-slate-950 px-4">
      <div className="w-full max-w-sm rounded-3xl border border-slate-800/70 bg-slate-900/60 p-6 shadow-2xl shadow-black/40 sm:p-8">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-500 text-2xl">
            🎙️
          </div>
          <h1 className="text-lg font-semibold text-white">SecureVoice AI</h1>
          <p className="mt-1 text-xs text-slate-400">
            {mode === 'login' ? 'Sign in to start your voice session' : 'Create your customer account'}
          </p>
        </div>

        <form onSubmit={submit} className="space-y-3">
          {mode === 'register' && (
            <Input
              value={form.fullName}
              onChange={set('fullName')}
              placeholder="Full name (optional)"
              className="h-11"
            />
          )}
          <Input
            type="email"
            required
            autoComplete="email"
            value={form.email}
            onChange={set('email')}
            placeholder="Email address"
            className="h-11"
          />
          <Input
            type="password"
            required
            minLength={8}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={form.password}
            onChange={set('password')}
            placeholder="Password (min. 8 characters)"
            className="h-11"
          />
          {error && (
            <div className="rounded-xl bg-rose-500/10 px-4 py-2.5 text-xs text-rose-200">{error}</div>
          )}
          <Button type="submit" disabled={busy} className="h-11 w-full">
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account & sign in'}
          </Button>
        </form>

        <button
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError(null)
          }}
          className="mt-4 w-full text-center text-xs text-slate-400 hover:text-slate-200"
        >
          {mode === 'login' ? 'No account yet? Register' : 'Already have an account? Sign in'}
        </button>
      </div>
    </div>
  )
}
