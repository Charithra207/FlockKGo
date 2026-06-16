import { useCallback, useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'
import { Check, Copy, ExternalLink, Plus, Trash2 } from 'lucide-react'
import { addParticipant, createTrip, getParticipants } from '../services/tripService'
import { getSurveyStatus } from '../services/surveyService'
import { MONTHS } from '../utils/constants'
import { saveRecentTrip } from './Home'

// ── Small copy-button with a brief "Copied" flash ──────────────────────────
function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)
  const handle = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={handle}
      className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
      aria-label={label}
    >
      {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
      {copied ? 'Copied!' : label}
    </button>
  )
}

export default function CreateTrip() {
  const navigate = useNavigate()

  // Step 1 — trip details
  const [form, setForm] = useState({
    name: '',
    organizer_name: '',
    organizer_email: '',
    trip_month: 'Jun',
    duration_days: 5,
  })
  const [formErrors, setFormErrors] = useState({})
  const [creating, setCreating] = useState(false)

  // Step 2 — participants (only shown after trip is created)
  const [trip, setTrip] = useState(null)
  const [participants, setParticipants] = useState([])
  const [submittedCount, setSubmittedCount] = useState(0)
  const [pForm, setPForm] = useState({ name: '', email: '', phone: '' })
  const [addingP, setAddingP] = useState(false)

  // Auto-refresh survey status while on this page
  const refreshStatus = useCallback(async () => {
    if (!trip?.id) return
    try {
      const [latest, status] = await Promise.all([
        getParticipants(trip.id),
        getSurveyStatus(trip.id),
      ])
      setParticipants(latest)
      setSubmittedCount(status.submitted_count ?? 0)
    } catch {
      // silent
    }
  }, [trip?.id])

  useEffect(() => {
    if (!trip?.id) return
    refreshStatus()
    const t = setInterval(refreshStatus, 3000)
    return () => clearInterval(t)
  }, [trip?.id, refreshStatus])

  // ── Validate trip form ───────────────────────────────────────────────────
  const validate = () => {
    const errs = {}
    if (!form.name.trim()) errs.name = 'Trip name is required'
    if (!form.organizer_name.trim()) errs.organizer_name = 'Your name is required'
    if (!form.organizer_email.trim()) errs.organizer_email = 'Your email is required'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.organizer_email))
      errs.organizer_email = 'Enter a valid email'
    if (!form.duration_days || form.duration_days < 1)
      errs.duration_days = 'At least 1 day'
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

  // ── Field helper ─────────────────────────────────────────────────────────
  const Field = ({ name, ...props }) => (
    <div className="flex flex-col gap-1">
      <input
        className={`rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary ${
          formErrors[name] ? 'border-red-400 bg-red-50' : ''
        }`}
        value={form[name]}
        onChange={(e) =>
          setForm({ ...form, [name]: props.type === 'number' ? Number(e.target.value) : e.target.value })
        }
        {...props}
      />
      {formErrors[name] && (
        <p className="text-xs text-red-500">{formErrors[name]}</p>
      )}
    </div>
  )

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-2xl space-y-6">

      {/* ── Step 1: Trip Details ─────────────────────────────────────────── */}
      <div className="rounded-2xl bg-white p-6 shadow-card">
        <div className="mb-5 flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">
            1
          </span>
          <h1 className="text-xl font-bold text-primary">Trip Details</h1>
          {trip && (
            <span className="ml-auto rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
              ✓ Created
            </span>
          )}
        </div>

        {!trip ? (
          <form onSubmit={handleCreate} className="space-y-3" noValidate>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field name="name" placeholder="Trip name *" />
              <Field name="organizer_name" placeholder="Your name *" />
              <Field name="organizer_email" placeholder="Your email *" type="email" />
              <div className="flex flex-col gap-1">
                <select
                  className="rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  value={form.trip_month}
                  onChange={(e) => setForm({ ...form, trip_month: e.target.value })}
                >
                  {MONTHS.map((m) => <option key={m}>{m}</option>)}
                </select>
              </div>
              <Field
                name="duration_days"
                type="number"
                placeholder="Duration (days) *"
                min={1}
                max={90}
              />
            </div>
            <button
              disabled={creating}
              className="mt-2 w-full rounded-xl bg-primary py-3 font-semibold text-white disabled:opacity-50 hover:opacity-90"
            >
              {creating ? 'Creating…' : 'Create Trip →'}
            </button>
          </form>
        ) : (
          <div className="space-y-2 text-sm text-slate-600">
            <p><span className="font-medium">Trip:</span> {trip.name}</p>
            <p><span className="font-medium">Organizer:</span> {trip.organizer_name}</p>
            <p><span className="font-medium">When:</span> {form.trip_month} · {form.duration_days} days</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <CopyButton
                text={`${window.location.origin}/trip/${trip.id}`}
                label="Copy dashboard link"
              />
              <button
                onClick={goToDashboard}
                className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/5"
              >
                <ExternalLink className="h-3 w-3" />
                Open dashboard
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Step 2: Add Participants ─────────────────────────────────────── */}
      {trip && (
        <div className="rounded-2xl bg-white p-6 shadow-card">
          <div className="mb-5 flex items-center gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">
              2
            </span>
            <h2 className="text-xl font-bold text-primary">Add Your Flock</h2>
          </div>

          <form onSubmit={handleAddParticipant} className="grid gap-3 sm:grid-cols-4">
            <input
              className="rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Name *"
              value={pForm.name}
              onChange={(e) => setPForm({ ...pForm, name: e.target.value })}
            />
            <input
              className="rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Email"
              type="email"
              value={pForm.email}
              onChange={(e) => setPForm({ ...pForm, email: e.target.value })}
            />
            <input
              className="rounded-xl border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Phone"
              value={pForm.phone}
              onChange={(e) => setPForm({ ...pForm, phone: e.target.value })}
            />
            <button
              disabled={addingP}
              className="flex items-center justify-center gap-1 rounded-xl bg-accent py-3 font-semibold text-white disabled:opacity-50 hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              {addingP ? 'Adding…' : 'Add'}
            </button>
          </form>

          {/* Participant list */}
          {participants.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {submittedCount}/{participants.length} surveys submitted
              </p>
              {participants.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between rounded-xl border px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium">{p.name}</p>
                    {p.email && <p className="text-xs text-slate-400">{p.email}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <CopyButton
                      text={`${window.location.origin}/survey/${p.survey_token}`}
                      label="Survey link"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* CTA once enough participants are added */}
          {participants.length >= 2 && (
            <button
              onClick={goToDashboard}
              className="mt-5 w-full rounded-xl bg-primary py-3 font-semibold text-white hover:opacity-90"
            >
              Go to Trip Dashboard →
            </button>
          )}

          {participants.length > 0 && participants.length < 2 && (
            <p className="mt-4 text-center text-sm text-slate-400">
              Add at least one more person to continue
            </p>
          )}
        </div>
      )}
    </div>
  )
}
