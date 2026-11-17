import { useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import GoogleButton from '../components/auth/GoogleButton'
import Turnstile, { Honeypot } from '../components/auth/Turnstile'
import { authApi } from '../services/spotsService'
import useAuthStore from '../store/authStore'
import { useT } from '../i18n'

export default function Login() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const t = useT()
  const [mode, setMode] = useState('register')
  const [form, setForm] = useState({ email: '', password: '', display_name: '' })
  const [busy, setBusy] = useState(false)
  const [captcha, setCaptcha] = useState(null)
  const [website, setWebsite] = useState('')

  const next = params.get('next') || '/explore'
  const safeNext = next.startsWith('/') && !next.startsWith('//') ? next : '/explore'

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    try {
      const r = mode === 'register'
        ? await authApi.register({ ...form, captcha_token: captcha || undefined, website: website || undefined })
        : await authApi.login({ email: form.email, password: form.password })
      done(r, mode === 'register')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  function done(r, isNew) {
    setSession(r.token, r.user)
    toast.success(isNew ? 'Welcome! You have 1 free unlock 🎁' : `Welcome back, ${r.user.display_name}`)
    navigate(safeNext)
  }

  const input = 'w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:border-primary focus:outline-none'

  return (
    <div className="mx-auto max-w-md rounded-3xl bg-white p-8 shadow-card">
      <div className="mb-6 flex rounded-xl bg-slate-100 p-1">
        {[['register', t('login.signup')], ['login', t('login.login')]].map(([k, label]) => (
          <button
            key={k}
            onClick={() => setMode(k)}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold ${mode === k ? 'bg-white text-primary shadow' : 'text-slate-500'}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mb-4">
        <GoogleButton onSession={(r) => done(r, false)} />
      </div>

      <form onSubmit={submit} className="relative space-y-4">
        <Honeypot value={website} onChange={setWebsite} />
        {mode === 'register' && (
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">{t('login.name')}</span>
            <input required maxLength={80} value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} className={input} />
          </label>
        )}
        <label className="block">
          <span className="text-sm font-semibold text-slate-700">{t('login.email')}</span>
          <input required type="email" autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={input} />
        </label>
        <label className="block">
          <span className="text-sm font-semibold text-slate-700">{t('login.password')}</span>
          <input
            required
            type="password"
            minLength={mode === 'register' ? 8 : 1}
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className={input}
          />
          {mode === 'register' && <span className="text-xs text-slate-400">{t('login.min')}</span>}
          {mode === 'login' && (
            <Link to="/forgot-password" className="mt-1 block text-right text-xs font-semibold text-primary">Forgot password?</Link>
          )}
        </label>
        {mode === 'register' && <Turnstile onToken={setCaptcha} />}
        <button disabled={busy} className="w-full rounded-xl bg-primary py-3 font-semibold text-white hover:opacity-90 disabled:opacity-50">
          {busy ? '…' : mode === 'register' ? t('login.create') : t('login.login')}
        </button>
      </form>
      {mode === 'register' && (
        <>
          <p className="mt-4 text-center text-xs text-slate-400">{t('login.free')}</p>
          <p className="mt-2 text-center text-xs text-slate-400">
            By signing up you agree to the <Link to="/terms" className="underline">Terms</Link> and{' '}
            <Link to="/privacy" className="underline">Privacy policy</Link>.
          </p>
        </>
      )}
    </div>
  )
}
