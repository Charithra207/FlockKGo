import { useCallback, useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { Link } from 'react-router-dom'
import { addParticipant, createTrip, getParticipants, runAnalysis } from '../services/tripService'
import { MONTHS, DEV_MODE } from '../utils/constants'
import { MOCK_PARTICIPANTS, MOCK_TRIP } from '../utils/mockData'

export default function CreateTrip() {
  const [trip, setTrip] = useState(null)
  const [participants, setParticipants] = useState([])
  const [form, setForm] = useState({ name: '', organizer_name: '', organizer_email: '', trip_month: 'Jun', duration_days: 5 })
  const [participant, setParticipant] = useState({ name: '', email: '', phone: '' })
  const [loading, setLoading] = useState(false)

  const refreshParticipants = useCallback(async () => {
    if (!trip?.id || DEV_MODE) return
    const latest = await getParticipants(trip.id)
    setParticipants(latest)
  }, [trip?.id])

  useEffect(() => {
    if (!trip?.id || DEV_MODE) return
    refreshParticipants().catch(() => {})
    const timer = setInterval(() => {
      refreshParticipants().catch(() => {})
    }, 2500)
    return () => clearInterval(timer)
  }, [trip?.id, refreshParticipants])

  const onCreate = async (e) => {
    e.preventDefault()
    if (!form.name || !form.organizer_name || !form.organizer_email) return toast.error('Fill all required fields')
    try {
      setLoading(true)
      const res = DEV_MODE ? { ...MOCK_TRIP, ...form } : await createTrip(form)
      setTrip(res)
      toast.success('Trip created')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  const onAdd = async (e) => {
    e.preventDefault()
    if (!participant.name) return toast.error('Participant name is required')
    try {
      const p = DEV_MODE ? { id: crypto.randomUUID(), ...participant, survey_submitted: false, survey_link: `/survey/mock-${Date.now()}` } : await addParticipant(trip.id, participant)
      setParticipants((s) => [...s, p])
      setParticipant({ name: '', email: '', phone: '' })
      if (!DEV_MODE) await refreshParticipants()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const submitted = participants.filter((p) => p.survey_submitted).length
  const canRun = participants.length >= 2 && participants.every((p) => p.survey_submitted)

  return (
    <div className="space-y-6">
      <form onSubmit={onCreate} className="rounded-2xl bg-white p-6 shadow-card">
        <h1 className="mb-4 text-2xl font-bold text-primary">Create a Trip</h1>
        <div className="grid gap-3 md:grid-cols-2">
          <input className="rounded-xl border p-3" placeholder="Trip name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="rounded-xl border p-3" placeholder="Your name" value={form.organizer_name} onChange={(e) => setForm({ ...form, organizer_name: e.target.value })} />
          <input className="rounded-xl border p-3" placeholder="Your email" value={form.organizer_email} onChange={(e) => setForm({ ...form, organizer_email: e.target.value })} />
          <select className="rounded-xl border p-3" value={form.trip_month} onChange={(e) => setForm({ ...form, trip_month: e.target.value })}>{MONTHS.map((m) => <option key={m}>{m}</option>)}</select>
          <input type="number" className="rounded-xl border p-3" placeholder="How many days?" value={form.duration_days} onChange={(e) => setForm({ ...form, duration_days: Number(e.target.value) })} />
        </div>
        <button disabled={loading} className="mt-4 rounded-xl bg-primary px-5 py-3 font-semibold text-white">{loading ? 'Creating...' : 'Create Trip'}</button>
      </form>
      {trip && (
        <div className="space-y-4 rounded-2xl bg-white p-6 shadow-card">
          <p className="text-sm">Share trip link: <Link className="text-primary underline" to={`/trip/${trip.id}`}>/trip/{trip.id}</Link></p>
          <form onSubmit={onAdd} className="grid gap-3 md:grid-cols-4">
            <input className="rounded-xl border p-3" placeholder="Name*" value={participant.name} onChange={(e) => setParticipant({ ...participant, name: e.target.value })} />
            <input className="rounded-xl border p-3" placeholder="Email" value={participant.email} onChange={(e) => setParticipant({ ...participant, email: e.target.value })} />
            <input className="rounded-xl border p-3" placeholder="Phone" value={participant.phone} onChange={(e) => setParticipant({ ...participant, phone: e.target.value })} />
            <button className="rounded-xl bg-accent px-4 py-3 font-semibold text-white">Add to Flock</button>
          </form>
          <p className="text-sm text-muted">{submitted}/{participants.length} surveys complete</p>
          {!DEV_MODE && <button onClick={() => refreshParticipants().catch((e) => toast.error(e.message))} className="rounded-xl border px-4 py-2 text-sm">Refresh Survey Status</button>}
          <div className="space-y-2">{(DEV_MODE && participants.length === 0 ? MOCK_PARTICIPANTS : participants).map((p) => <div key={p.id} className="flex items-center justify-between rounded-xl border p-3"><span>{p.name}</span><button onClick={() => navigator.clipboard.writeText(`${window.location.origin}${p.survey_link}`)} className="text-xs text-primary underline">Copy survey link</button></div>)}</div>
          <button disabled={!canRun} onClick={() => runAnalysis(trip.id).then(() => toast.success('Analysis started')).catch((e) => toast.error(e.message))} className="rounded-xl bg-primary px-5 py-3 font-semibold text-white disabled:opacity-50">Generate Recommendations</button>
        </div>
      )}
    </div>
  )
}
