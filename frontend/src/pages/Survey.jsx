import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { useParams } from 'react-router-dom'
import BudgetSlider from '../components/survey/BudgetSlider'
import DateRangePicker from '../components/survey/DateRangePicker'
import ExclusionInput from '../components/survey/ExclusionInput'
import VibeSelector from '../components/survey/VibeSelector'
import { getSurveyInfo, submitSurvey } from '../services/surveyService'
import useUserStore from '../store/userStore'
import { DEV_MODE } from '../utils/constants'

export default function Survey() {
  const { token } = useParams()
  const { setParticipant } = useUserStore()
  const [step, setStep] = useState(1)
  const [submitted, setSubmitted] = useState(false)
  const [participantName, setParticipantName] = useState('Traveler')
  const [form, setForm] = useState({ budget_min: 500, budget_max: 1500, vibes: [], climate: 'either', activity_level: 'moderate', available_dates: [null, null], exclusions: [], visited: [] })

  useEffect(() => {
    if (DEV_MODE) return
    getSurveyInfo(token).then((d) => {
      setSubmitted(Boolean(d.submitted))
      setParticipantName(d.participant_name || 'Traveler')
      if (d.submitted) toast.success('Already submitted!')
    }).catch((e) => toast.error(e.message))
  }, [token])

  if (submitted) return <div className="rounded-2xl bg-white p-8 text-center shadow-card"><h1 className="text-2xl font-bold text-primary">Already submitted!</h1></div>

  const handleSubmit = async () => {
    try {
      if (!DEV_MODE) await submitSurvey(token, { ...form, available_dates: form.available_dates })
      setParticipant(`p-${token}`, participantName)
      setSubmitted(true)
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <div className="mx-auto max-w-3xl rounded-2xl bg-white p-6 shadow-card">
      <p className="mb-1 text-sm text-muted">Hi {participantName}</p>
      <p className="mb-4 text-sm font-semibold">Step {step} of 4</p>
      {step === 1 && <div className="space-y-3"><h2 className="text-xl font-bold">What's your budget per person?</h2><BudgetSlider min={form.budget_min} max={form.budget_max} onChange={(min, max) => setForm({ ...form, budget_min: min, budget_max: max })} /></div>}
      {step === 2 && <div className="space-y-3"><h2 className="text-xl font-bold">What's your travel vibe?</h2><VibeSelector selected={form.vibes} onToggle={(key) => setForm({ ...form, vibes: form.vibes.includes(key) ? form.vibes.filter((v) => v !== key) : [...form.vibes, key] })} /></div>}
      {step === 3 && <div className="space-y-4"><h2 className="text-xl font-bold">Climate & Activity</h2><div className="flex gap-2">{['warm', 'cold', 'either'].map((v) => <button key={v} onClick={() => setForm({ ...form, climate: v })} className={`rounded-xl border px-3 py-2 ${form.climate === v ? 'border-accent bg-red-50' : ''}`}>{v}</button>)}</div><div className="flex gap-2">{['relaxed', 'moderate', 'intense'].map((v) => <button key={v} onClick={() => setForm({ ...form, activity_level: v })} className={`rounded-xl border px-3 py-2 ${form.activity_level === v ? 'border-accent bg-red-50' : ''}`}>{v}</button>)}</div><DateRangePicker startDate={form.available_dates[0]} endDate={form.available_dates[1]} onChange={(dates) => setForm({ ...form, available_dates: dates })} /></div>}
      {step === 4 && <div className="space-y-4"><h2 className="text-xl font-bold">Anywhere you DON'T want to go?</h2><ExclusionInput label="Exclusions" values={form.exclusions} setValues={(v) => setForm({ ...form, exclusions: v })} /><ExclusionInput label="Been there, done that?" values={form.visited} setValues={(v) => setForm({ ...form, visited: v })} /></div>}
      <div className="mt-6 flex justify-between">
        <button disabled={step === 1} onClick={() => setStep((s) => s - 1)} className="rounded-xl border px-4 py-2 disabled:opacity-50">Back</button>
        {step < 4 ? <button onClick={() => setStep((s) => s + 1)} className="rounded-xl bg-primary px-4 py-2 text-white">Next</button> : <button onClick={handleSubmit} className="rounded-xl bg-accent px-4 py-2 text-white">Submit</button>}
      </div>
      {submitted && <div className="mt-6 rounded-xl bg-emerald-50 p-4 text-emerald-700">You're in the flock! 🐦 Your preferences have been saved.</div>}
    </div>
  )
}
