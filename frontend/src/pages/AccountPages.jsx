import { CheckCircle2, KeyRound, MailCheck, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { accountApi } from '../services/authConfig'
import useAuthStore from '../store/authStore'

const input = 'w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:border-primary focus:outline-none'
const card = 'mx-auto max-w-md space-y-4 rounded-3xl bg-white p-8 shadow-card'

export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    try {
      setDone(await accountApi.forgot(email))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={card}>
      <h1 className="flex items-center gap-2 text-2xl font-extrabold text-primary"><KeyRound className="h-6 w-6" /> Forgot your password?</h1>
      {done ? (
        done.email_enabled ? (
          <p className="text-slate-600">
            If <b>{email}</b> has a FlockGo account, a reset link is on its way. It works for 1 hour. Check your spam folder too.
          </p>
        ) : (
          <p className="text-slate-600">
            Email isn't switched on for FlockGo yet. Message the FlockGo admin and they can send you a reset link directly.
          </p>
        )
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <p className="text-sm text-slate-500">Enter your email and we'll send you a link to set a new password.</p>
          <input required type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={input} placeholder="you@example.com" />
          <button disabled={busy} className="w-full rounded-xl bg-primary py-3 font-semibold text-white disabled:opacity-50">
            {busy ? 'Sending…' : 'Send reset link'}
          </button>
        </form>
      )}
      <Link to="/login" className="block text-center text-sm font-semibold text-primary">Back to log in</Link>
    </div>
  )
}

export function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const token = params.get('token') || ''

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    try {
      const r = await accountApi.reset(token, password)
      setSession(r.token, r.user)
      toast.success('Password changed. You are logged in.')
      navigate('/explore')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className={card}>
      <h1 className="flex items-center gap-2 text-2xl font-extrabold text-primary"><KeyRound className="h-6 w-6" /> Set a new password</h1>
      <input
        required type="password" minLength={8} autoComplete="new-password" value={password}
        onChange={(e) => setPassword(e.target.value)} className={input} placeholder="At least 8 characters"
      />
      <button disabled={busy || !token} className="w-full rounded-xl bg-primary py-3 font-semibold text-white disabled:opacity-50">
        {busy ? 'Saving…' : 'Save password'}
      </button>
      {!token && <p className="text-sm text-red-500">This link is missing its code. Open the link from your email again.</p>}
    </form>
  )
}

export function VerifyEmail() {
  const [params] = useSearchParams()
  const { token: session, user, setUser } = useAuthStore()
  const [state, setState] = useState('working')

  useEffect(() => {
    accountApi.verify(params.get('token') || '')
      .then(() => {
        setState('ok')
        if (session && user) setUser({ ...user, email_verified: true })
      })
      .catch(() => setState('bad'))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={`${card} text-center`}>
      {state === 'working' && <><MailCheck className="mx-auto h-10 w-10 text-primary" /><p>Confirming your email…</p></>}
      {state === 'ok' && (
        <>
          <CheckCircle2 className="mx-auto h-12 w-12 text-success" />
          <h1 className="text-2xl font-extrabold text-primary">Email confirmed</h1>
          <p className="text-slate-500">Thanks! You're all set to share spots.</p>
          <Link to="/explore" className="inline-block rounded-xl bg-primary px-5 py-2.5 font-semibold text-white">Explore Karnataka</Link>
        </>
      )}
      {state === 'bad' && (
        <>
          <XCircle className="mx-auto h-12 w-12 text-red-400" />
          <h1 className="text-xl font-extrabold text-slate-700">That link didn't work</h1>
          <p className="text-slate-500">It may have expired. Log in and use “Send the link again” at the top of the page.</p>
        </>
      )}
    </div>
  )
}

// ── Privacy + Terms ───────────────────────────────────────────────────────────

const UPDATED = '18 November 2026'

function Legal({ title, children }) {
  return (
    <article className="mx-auto max-w-3xl space-y-4 rounded-3xl bg-white p-8 leading-relaxed text-slate-600 shadow-card [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:font-bold [&_h2]:text-slate-800 [&_li]:ml-5 [&_li]:list-disc">
      <h1 className="text-3xl font-extrabold text-primary">{title}</h1>
      <p className="text-sm text-slate-400">Last updated {UPDATED}</p>
      {children}
    </article>
  )
}

export function Privacy() {
  return (
    <Legal title="Privacy policy">
      <p>FlockGo is a small, independent project for exploring Karnataka. This page explains, in plain words, what we store and why.</p>
      <h2>What we store</h2>
      <ul>
        <li><b>Account:</b> your email, name, a scrambled (hashed) password, and if you use it, your Google account ID. We never see or store your Google password.</li>
        <li><b>Profile:</b> username, bio, home district and profile photo, if you add them.</li>
        <li><b>Your activity:</b> spots you share, unlock, vouch for or report; places you stamp or add to your bucket list, with the date and photo you choose to add.</li>
        <li><b>Group trips:</b> the trip name, organiser name and email, the names (and optional email/phone) of people added to a trip, and their survey answers and votes.</li>
        <li><b>Photos:</b> images you upload, resized in your browser first.</li>
      </ul>
      <h2>Photo location</h2>
      <p>When you stamp a place with a photo, your browser reads the photo's GPS location and sends it once so we can check whether it was taken near the place (for the “verified” stamp). We do not save that location. Resizing in your browser removes the photo's hidden data before upload.</p>
      <h2>Who can see what</h2>
      <ul>
        <li>Your profile, stamps, bucket list and trip photos are public unless you make your profile private in <Link to="/settings/profile" className="text-primary underline">Edit profile</Link>.</li>
        <li>Your email is never shown to other users.</li>
        <li>Anyone with a trip's link can see that trip.</li>
      </ul>
      <h2>Services we use</h2>
      <p>Hosting (Vercel, Render), the database (Neon), and, when switched on, email delivery, Google sign-in, Cloudflare's “I'm human” check and error tracking. Map data comes from OpenStreetMap and Wikidata.</p>
      <h2>Your choices</h2>
      <ul>
        <li>Edit or hide your profile at any time.</li>
        <li>Remove any stamp or bucket-list item.</li>
        <li>To delete your account and data, or to ask what we hold about you, contact the FlockGo admin. We'll do it within 30 days.</li>
      </ul>
      <h2>Children</h2>
      <p>FlockGo is not meant for children under 13.</p>
      <h2>Changes</h2>
      <p>If this policy changes, we'll update this page and the date at the top.</p>
    </Legal>
  )
}

export function Terms() {
  return (
    <Legal title="Terms of use">
      <h2>Using FlockGo</h2>
      <p>FlockGo helps groups plan trips in Karnataka and helps people share places they love. Use it kindly and lawfully.</p>
      <h2>Your safety comes first</h2>
      <ul>
        <li>Spots are shared by the community and from open map data. They may be wrong, closed, on private land, or dangerous, especially waterfalls and treks in the monsoon.</li>
        <li>Check local conditions, follow forest department rules and signs, get permission where needed, and never take risks for a photo. You visit any place at your own risk.</li>
        <li>Please report spots that are unsafe, closed or wrong.</li>
      </ul>
      <h2>What you share</h2>
      <ul>
        <li>Only share places and photos you have the right to share. Don't share someone's home or private property, and don't post people without their consent.</li>
        <li>You keep ownership of your photos and text. By posting them you allow FlockGo to show them in the app.</li>
        <li>We may edit, hide or remove anything that's wrong, unsafe, spammy or against these terms, and close accounts that abuse the service.</li>
      </ul>
      <h2>Leave no trace</h2>
      <p>Hidden spots stay beautiful because people look after them. Carry your trash back, keep noise down, stay on paths, and respect locals and wildlife.</p>
      <h2>Credits and unlocks</h2>
      <p>Unlock credits have no money value and can't be sold or transferred.</p>
      <h2>No guarantees</h2>
      <p>FlockGo is provided as-is, without warranties. Travel suggestions, budgets and prices are estimates.</p>
      <h2>Contact</h2>
      <p>Questions or takedown requests: contact the FlockGo admin.</p>
    </Legal>
  )
}
