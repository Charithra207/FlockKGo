import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { Link, useParams } from 'react-router-dom'
import BudgetSlider from '../components/survey/BudgetSlider'
import DateRangePicker from '../components/survey/DateRangePicker'
import ExclusionInput from '../components/survey/ExclusionInput'
import VibeSelector from '../components/survey/VibeSelector'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { getSurveyInfo, submitSurvey } from '../services/surveyService'
import useUserStore from '../store/userStore'

export default function Survey() {
  const { token } = useParams()
  const { setParticipant } = useUserStore()

  const [step, setStep] = useState(1)
  const [submitted, setSubmitted] = useState(false)
  const [participantName, setParticipantName] = useState('Traveler')
  const [tripName, setTripName] = useState('')
  const [tripId, setTripId] = useState('')
  const [pageLoading, setPageLoading] = useState(true)
  const [pageError, setPageError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [form, setForm] = useState({
    budget_min: 500,
    budget_max: 1500,
    vibes: [],
    climate: 'any',
    activity_level: 'moderate',
    available_dates: [null, null],
    exclusions: [],
    visited: [],
  })

  useEffect(() => {
    getSurveyInfo(token)
      .then((d) => {
        // Backend returns `already_submitted`, not `submitted`
        if (d.already_submitted) {
          setSubmitted(true)
        }
        setParticipantName(d.participant_name || 'Traveler')
        setTripName(d.trip_name || '')
        setTripId(d.trip_id || '')
      })
      .catch((e) => setPageError(e.message))
      .finally(() => setPageLoading(false))
  }, [token])

  if (pageLoading) return <LoadingSpinner message="Loading your survey…" />

  if (pageError) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-3xl">😕</p>
        <h2 className="mt-2 text-lg font-bold text-red-600">Survey not found</h2>
        <p className="mt-1 text-sm text-slate-500">{pageError}</p>
        <p className="mt-3 text-xs text-slate-400">
          Double-check the link your organizer sent you.
        </p>
      </div>
    )
  }

  if (submitted) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-5xl">🐦</p>
        <h1 className="mt-3 text-2xl font-bold text-primary">You're in the flock!</h1>
        <p className="mt-1 text-slate-500">
          Your preferences for <span className="font-semibold">{tripName}</span> have been saved.
        </p>
        <p className="mt-3 text-sm text-slate-400">
          Your organizer will let you know when recommendations are ready.
        </p>
        {tripId && (
          <Link
            to={`/trip/${tripId}`}
            className="mt-5 inline-block rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            View Trip Dashboard
          </Link>
        )}
      </div>
    )
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await submitSurvey(token, {
        budget_min: form.budget_min,
        budget_max: form.budget_max,
        vibes: form.vibes,
        climate_pref: form.climate,
        activity_level: form.activity_level,
        available_start: form.available_dates[0]
          ? new Date(form.available_dates[0]).toISOString().slice(0, 10)
          : null,
        available_end: form.available_dates[1]
          ? new Date(form.available_dates[1]).toISOString().slice(0, 10)
          : null,
        excluded_destinations: form.exclusions,
        already_visited: form.visited,
      })
      setParticipant(`p-${token}`, participantName)
      setSubmitted(true)
      toast.success('Survey submitted!')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl rounded-2xl bg-white p-6 shadow-card">
      <p className="mb-1 text-sm text-slate-500">Hi {participantName} 👋</p>
      {tripName && <p className="mb-1 text-sm font-semibold text-primary">{tripName}</p>}

      {/* Step progress */}
      <div className="mb-5 flex gap-2">
        {[1, 2, 3, 4].map((n) => (
          <div
            key={n}
            className={`h-1.5 flex-1 rounded-full transition-all ${
              n <= step ? 'bg-accent' : 'bg-slate-200'
            }`}
          />
        ))}
      </div>
      <p className="mb-4 text-xs text-slate-400">Step {step} of 4</p>

      {step === 1 && (
        <div className="space-y-3">
          <h2 className="text-xl font-bold">What's your budget per person?</h2>
          <BudgetSlider
            min={form.budget_min}
            max={form.budget_max}
            onChange={(min, max) => setForm({ ...form, budget_min: min, budget_max: max })}
          />
        </div>
      )}

      {step === 2 && (
        <div className="space-y-3">
          <h2 className="text-xl font-bold">What's your travel vibe?</h2>
          <p className="text-sm text-slate-500">Pick all that apply</p>
          <VibeSelector
            selected={form.vibes}
            onToggle={(key) =>
              setForm({
                ...form,
                vibes: form.vibes.includes(key)
                  ? form.vibes.filter((v) => v !== key)
                  : [...form.vibes, key],
              })
            }
          />
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <h2 className="text-xl font-bold">Climate & Activity Level</h2>
          <div>
            <p className="mb-2 text-sm font-medium text-slate-600">Preferred climate</p>
            <div className="flex gap-2">
              {['warm', 'cold', 'any'].map((v) => (
                <button
                  key={v}
                  onClick={() => setForm({ ...form, climate: v })}
                  className={`rounded-xl border px-4 py-2 text-sm capitalize transition-colors ${
                    form.climate === v
                      ? 'border-accent bg-red-50 font-semibold text-accent'
                      : 'hover:bg-slate-50'
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-slate-600">Activity level</p>
            <div className="flex gap-2">
              {['relaxed', 'moderate', 'intense'].map((v) => (
                <button
                  key={v}
                  onClick={() => setForm({ ...form, activity_level: v })}
                  className={`rounded-xl border px-4 py-2 text-sm capitalize transition-colors ${
                    form.activity_level === v
                      ? 'border-accent bg-red-50 font-semibold text-accent'
                      : 'hover:bg-slate-50'
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-slate-600">Available dates (optional)</p>
            <DateRangePicker
              startDate={form.available_dates[0]}
              endDate={form.available_dates[1]}
              onChange={(dates) => setForm({ ...form, available_dates: dates })}
            />
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-4">
          <h2 className="text-xl font-bold">Any places off the table?</h2>
          <ExclusionInput
            label="Places you don't want to go"
            values={form.exclusions}
            setValues={(v) => setForm({ ...form, exclusions: v })}
          />
          <ExclusionInput
            label="Places you've already been"
            values={form.visited}
            setValues={(v) => setForm({ ...form, visited: v })}
          />
        </div>
      )}

      <div className="mt-6 flex justify-between">
        <button
          disabled={step === 1}
          onClick={() => setStep((s) => s - 1)}
          className="rounded-xl border px-4 py-2 text-sm font-semibold disabled:opacity-40 hover:bg-slate-50"
          aria-label="Go to previous step"
        >
          Back
        </button>
        {step < 4 ? (
          <button
            onClick={() => setStep((s) => s + 1)}
            className="rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white hover:opacity-90"
            aria-label="Go to next step"
          >
            Next
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:opacity-90"
            aria-label="Submit survey"
          >
            {submitting ? 'Submitting…' : 'Submit'}
          </button>
        )}
      </div>
    </div>
  )
}
