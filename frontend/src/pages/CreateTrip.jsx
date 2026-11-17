import { useCallback, useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'
import { Check, Copy, ExternalLink, Plus } from 'lucide-react'
import { addParticipant, createTrip, getParticipants } from '../services/tripService'
import { getSurveyStatus } from '../services/surveyService'
import { MONTHS } from '../utils/constants'
import { saveRecentTrip } from './Home'

// ── Field defined OUTSIDE CreateTrip — prevents remount/focus-loss on keystrokes
function Field({ name, label, hint, form, formErrors, setForm, ...props }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm font-semibold text-slate-700">{label}</span>
      <input
        className={`rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary ${
          formErrors[name] ? 'border-red-400 bg-red-50' : ''
        }`}
        value={form[name]}
        onChange={(e) =>
          setForm((prev) => ({
            ...prev,
            [name]: props.type === 'number' ? Number(e.target.value) : e.target.value,
          }))
        }
        {...props}
      />
      {formErrors[name] ? (
        <p className="text-xs text-red-500">{formErrors[name]}</p>
      ) : hint ? (
        <p className="text-xs text-slate-400">{hint}</p>
      ) : null}
    </label>
  )
}

// Karnataka seasons, so picking a month means something.
const SEASON = {
  Jan: '❄️', Feb: '❄️', Mar: '☀️', Apr: '☀️', May: '☀️', Jun: '🌧️',
  Jul: '🌧️', Aug: '🌧️', Sep: '🌧️', Oct: '🍂', Nov: '❄️', Dec: '❄️',
}
const SEASON_NOTE = {
  '❄️': 'Cool and dry: best for hills, Hampi and the coast.',
  '☀️': 'Hot summer: hill stations and early-morning treks.',
  '🌧️': 'Monsoon: waterfalls at their best, Western Ghats are lush (and wet).',
  '🍂': 'Post-monsoon: green everywhere, falls still flowing.',
}
const DURATION_PRESETS = [
  { days: 2, label: 'Weekend' },
  { days: 3, label: '3 days' },
  { days: 5, label: '5 days' },
  { days: 7, label: '1 week' },
]

function MonthPicker({ value, onChange }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-semibold text-slate-700">Which month are you going?</span>
      <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
        {MONTHS.map((m) => (
          <button
            key={m} type="button" onClick={() => onChange(m)} aria-pressed={value === m}
            className={`rounded-xl border px-2 py-2 text-sm font-semibold transition ${
              value === m ? 'border-primary bg-primary text-white shadow' : 'border-slate-200 text-slate-600 hover:border-primary hover:text-primary'
            }`}
          >
            <span className="mr-1">{SEASON[m]}</span>{m}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-500">{SEASON_NOTE[SEASON[value]]}</p>
    </div>
  )
}

function DurationPicker({ value, onChange, error }) {
  const set = (n) => onChange(Math.min(30, Math.max(1, n)))
  const nights = value - 1
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-semibold text-slate-700">How many days is the trip?</span>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center rounded-xl border border-slate-200">
          <button type="button" onClick={() => set(value - 1)} className="px-4 py-2 text-xl font-bold text-slate-500 hover:text-primary" aria-label="One day less">−</button>
          <div className="min-w-[7.5rem] text-center">
            <p className="text-lg font-extrabold text-primary">{value} {value === 1 ? 'day' : 'days'}</p>
            <p className="-mt-0.5 text-[11px] text-slate-400">{nights === 0 ? 'day trip, no night stay' : `${nights} night${nights === 1 ? '' : 's'} away`}</p>
          </div>
          <button type="button" onClick={() => set(value + 1)} className="px-4 py-2 text-xl font-bold text-slate-500 hover:text-primary" aria-label="One day more">+</button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {DURATION_PRESETS.map((d) => (
            <button
              key={d.days} type="button" onClick={() => set(d.days)}
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${value === d.days ? 'border-accent bg-accent/10 text-accent' : 'border-slate-200 text-slate-500 hover:border-accent hover:text-accent'}`}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}

function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)
  const handle = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button type="button" onClick={handle}
      className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
      aria-label={label}>
      {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
      {copied ? 'Copied!' : label}
    </button>
  )
}

export default function CreateTrip() {
  const navigate = useNavigate()

  const [form, setForm] = useState({
    name: '', organizer_name: '', organizer_email: '', trip_month: MONTHS[(new Date().getMonth() + 1) % 12], duration_days: 3,
  })
  const [formErrors, setFormErrors] = useState({})
  const [creating, setCreating] = useState(false)
  const [trip, setTrip] = useState(null)
  const [participants, setParticipants] = useState([])
  const [submittedCount, setSubmittedCount] = useState(0)
  const [pForm, setPForm] = useState({ name: '', email: '', phone: '' })
  const [addingP, setAddingP] = useState(false)

  const refreshStatus = useCallback(async () => {
    if (!trip?.id) return
    try {
      const [latest, status] = await Promise.all([
        getParticipants(trip.id),
        getSurveyStatus(trip.id),
      ])
      setParticipants(latest)
      setSubmittedCount(status.submitted_count ?? 0)
    } catch { /* silent */ }
  }, [trip?.id])

  useEffect(() => {
    if (!trip?.id) return
    refreshStatus()
    const t = setInterval(refreshStatus, 3000)
    return () => clearInterval(t)
  }, [trip?.id, refreshStatus])

  const validate = () => {
    const errs = {}
    if (!form.name.trim()) errs.name = 'Trip name is required'
    if (!form.organizer_name.trim()) errs.organizer_name = 'Your name is required'
    if (!form.organizer_email.trim()) errs.organizer_email = 'Your email is required'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.organizer_email))
      errs.organizer_email = 'Enter a valid email'
    if (!form.duration_days || form.duration_days < 1) errs.duration_days = 'At least 1 day'
    return errs
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setFormErrors(errs); return }
    setFormErrors({})
    setCreating(true)
    try {
      const res = await createTrip(form)
      setTrip(res)
      saveRecentTrip(res.id, res.name)
      toast.success('Trip created! Now add your flock.')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreating(false)
    }
  }

  const handleAddParticipant = async (e) => {
    e.preventDefault()
    if (!pForm.name.trim()) { toast.error('Name is required'); return }
    setAddingP(true)
    try {
      const p = await addParticipant(trip.id, pForm)
      setParticipants((s) => [...s, p])
      setPForm({ name: '', email: '', phone: '' })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setAddingP(false)
    }
  }

  const goToDashboard = () => navigate(`/trip/${trip.id}`)

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Step 1 */}
      <div className="rounded-2xl bg-white p-6 shadow-card">
        <div className="mb-5 flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">1</span>
          <h1 className="text-xl font-bold text-primary">Plan a group trip</h1>
          {trip && <span className="ml-auto rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">Created</span>}
        </div>
        {!trip ? (
          <form onSubmit={handleCreate} className="space-y-5" noValidate>
            <ol className="grid gap-2 rounded-xl bg-slate-50 p-3 text-xs text-slate-500 sm:grid-cols-4">
              <li><b className="text-primary">1.</b> Trip basics</li>
              <li><b className="text-primary">2.</b> Add your friends: each gets a 2-minute survey</li>
              <li><b className="text-primary">3.</b> FlockGo shortlists Karnataka places that suit everyone</li>
              <li><b className="text-primary">4.</b> Everyone votes, and you get a fair budget</li>
            </ol>
            <Field name="name" label="Trip name" placeholder="e.g. Monsoon getaway with the college gang"
              form={form} formErrors={formErrors} setForm={setForm} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field name="organizer_name" label="Your name" placeholder="e.g. Charithra"
                form={form} formErrors={formErrors} setForm={setForm} />
              <Field name="organizer_email" label="Your email" placeholder="you@example.com" type="email"
                hint="Only used for this trip's updates."
                form={form} formErrors={formErrors} setForm={setForm} />
            </div>
            <MonthPicker value={form.trip_month} onChange={(m) => setForm((prev) => ({ ...prev, trip_month: m }))} />
            <DurationPicker
              value={form.duration_days} error={formErrors.duration_days}
              onChange={(n) => setForm((prev) => ({ ...prev, duration_days: n }))}
            />
            <p className="text-xs text-slate-400">
              You don't pick the destination here: your group's surveys and the vote decide it. You'll add people in the next step.
            </p>
            <button type="submit" disabled={creating}
              className="w-full rounded-xl bg-primary py-3 font-semibold text-white disabled:opacity-50 hover:opacity-90">
              {creating ? 'Creating...' : 'Create trip and add friends →'}
            </button>
          </form>
        ) : (
          <div className="space-y-2 text-sm text-slate-600">
            <p><span className="font-medium">Trip:</span> {trip.name}</p>
            <p><span className="font-medium">Organizer:</span> {trip.organizer_name}</p>
            <p><span className="font-medium">When:</span> {form.trip_month} · {form.duration_days} {form.duration_days === 1 ? 'day' : 'days'}{form.duration_days > 1 ? ` (${form.duration_days - 1} night${form.duration_days === 2 ? '' : 's'})` : ''}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <CopyButton text={`${window.location.origin}/trip/${trip.id}`} label="Copy dashboard link" />
              <button type="button" onClick={goToDashboard}
                className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/5">
                <ExternalLink className="h-3 w-3" /> Open dashboard
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Step 2 */}
      {trip && (
        <div className="rounded-2xl bg-white p-6 shadow-card">
          <div className="mb-5 flex items-center gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">2</span>
            <h2 className="text-xl font-bold text-primary">Add Your Flock</h2>
          </div>
          <p className="-mt-2 mb-4 text-sm text-slate-500">
            Add everyone who's coming (you too, if you want a say). Each person gets their own survey link to share on WhatsApp.
            Email and phone are optional.
          </p>
          <form onSubmit={handleAddParticipant} className="grid gap-3 sm:grid-cols-4">
            <input className="rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Friend's name" aria-label="Friend's name" value={pForm.name}
              onChange={(e) => setPForm((prev) => ({ ...prev, name: e.target.value }))} />
            <input className="rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Email (optional)" aria-label="Email (optional)" type="email" value={pForm.email}
              onChange={(e) => setPForm((prev) => ({ ...prev, email: e.target.value }))} />
            <input className="rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Phone (optional)" aria-label="Phone (optional)" value={pForm.phone}
              onChange={(e) => setPForm((prev) => ({ ...prev, phone: e.target.value }))} />
            <button type="submit" disabled={addingP}
              className="flex items-center justify-center gap-1 rounded-xl bg-accent py-3 font-semibold text-white disabled:opacity-50 hover:opacity-90">
              <Plus className="h-4 w-4" />{addingP ? 'Adding...' : 'Add'}
            </button>
          </form>
          {participants.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {participants.length} {participants.length === 1 ? 'person' : 'people'} · {submittedCount}/{participants.length} surveys done
              </p>
              {participants.map((p) => (
                <div key={p.id} className="flex items-center justify-between rounded-xl border px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">{p.name}</p>
                    {p.email && <p className="text-xs text-slate-400">{p.email}</p>}
                  </div>
                  <CopyButton text={`${window.location.origin}/survey/${p.survey_token}`} label="Survey link" />
                </div>
              ))}
            </div>
          )}
          {participants.length >= 2 && (
            <button type="button" onClick={goToDashboard}
              className="mt-5 w-full rounded-xl bg-primary py-3 font-semibold text-white hover:opacity-90">
              Go to Trip Dashboard →
            </button>
          )}
          {participants.length === 1 && (
            <p className="mt-4 text-center text-sm text-slate-400">Add at least one more person to continue</p>
          )}
        </div>
      )}
    </div>
  )
}
