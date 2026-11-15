import { Check, Eye, EyeOff, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Navigate } from 'react-router-dom'
import EmptyState from '../components/common/EmptyState'
import LoadingSpinner from '../components/common/LoadingSpinner'
import SpotMap from '../components/spots/SpotMap'
import { categoryLabel, directionsUrl, MONTHS, spotsApi } from '../services/spotsService'
import useAuthStore from '../store/authStore'

export default function AdminSpots() {
  const { token, user } = useAuthStore()
  const [items, setItems] = useState(null)
  const [notes, setNotes] = useState({})

  useEffect(() => {
    if (!token || !user?.is_admin) return
    spotsApi.pending().then((r) => setItems(r.items)).catch((e) => toast.error(e.message))
  }, [token, user?.is_admin])

  if (!token) return <Navigate to="/login?next=/admin/spots" replace />
  if (!user?.is_admin) return <EmptyState emoji="🔐" title="Admins only" />
  if (!items) return <LoadingSpinner message="Loading review queue…" />

  async function act(spot, action) {
    try {
      const updated = await spotsApi.review(spot.id, action, notes[spot.id] || null)
      if (action === 'approve' || action === 'reject') {
        setItems((xs) => xs.filter((x) => x.id !== spot.id))
        toast.success(action === 'approve' ? 'Approved, credits sent' : 'Rejected')
      } else {
        setItems((xs) => xs.map((x) => (x.id === spot.id ? { ...x, ...updated } : x)))
      }
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-extrabold text-primary">Review queue ({items.length})</h1>
      {items.length === 0 && <EmptyState emoji="✅" title="All caught up" />}
      {items.map((s) => (
        <div key={s.id} className="grid gap-4 rounded-2xl bg-white p-5 shadow-card lg:grid-cols-2">
          <div className="space-y-2">
            <p className="text-sm text-slate-500">
              {categoryLabel(s.category)} • {s.destination ? `${s.destination}, ` : ''}{s.district} • by {s.submitted_by || 'unknown'}
            </p>
            <h2 className="text-xl font-bold text-slate-800">{s.name}</h2>
            <p className="text-sm font-semibold">{s.is_hidden ? '🔒 Hidden gem (+3 credits)' : 'Public spot (+1 credit)'}</p>
            {s.description && <p className="whitespace-pre-line text-sm text-slate-600">{s.description}</p>}
            {s.access_notes && <p className="whitespace-pre-line text-sm text-slate-500"><b>Access:</b> {s.access_notes}</p>}
            {s.best_months?.length > 0 && <p className="text-sm text-slate-500"><b>Best:</b> {s.best_months.map((m) => MONTHS[m - 1]).join(', ')}</p>}
            {s.photo_url && <img src={s.photo_url} alt="" className="max-h-48 rounded-xl object-cover" />}
            <a href={directionsUrl(s.latitude, s.longitude)} target="_blank" rel="noreferrer" className="text-sm font-semibold text-primary underline">
              Check on Google Maps
            </a>
            <input
              placeholder="Note to the sharer (shown if rejected)"
              value={notes[s.id] || ''}
              onChange={(e) => setNotes({ ...notes, [s.id]: e.target.value })}
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
            <div className="flex flex-wrap gap-2 pt-1">
              <button onClick={() => act(s, 'approve')} className="inline-flex items-center gap-1 rounded-xl bg-success px-4 py-2 text-sm font-semibold text-white"><Check className="h-4 w-4" /> Approve</button>
              <button onClick={() => act(s, 'reject')} className="inline-flex items-center gap-1 rounded-xl bg-red-500 px-4 py-2 text-sm font-semibold text-white"><X className="h-4 w-4" /> Reject</button>
              <button onClick={() => act(s, s.is_hidden ? 'make_public' : 'make_hidden')} className="inline-flex items-center gap-1 rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-600">
                {s.is_hidden ? <><Eye className="h-4 w-4" /> Make public</> : <><EyeOff className="h-4 w-4" /> Make hidden</>}
              </button>
            </div>
          </div>
          <SpotMap spots={[s]} center={[s.latitude, s.longitude]} zoom={13} height={300} />
        </div>
      ))}
    </div>
  )
}
