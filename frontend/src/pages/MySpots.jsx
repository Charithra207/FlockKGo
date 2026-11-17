import { Gift, Lock, LogOut, ShieldCheck, Stamp } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import EmptyState from '../components/common/EmptyState'
import LoadingSpinner from '../components/common/LoadingSpinner'
import SpotCard from '../components/spots/SpotCard'
import { spotsApi } from '../services/spotsService'
import useAuthStore from '../store/authStore'
import { profilePath } from '../services/profileService'

const STATUS_STYLE = {
  pending: 'bg-warning/15 text-warning',
  approved: 'bg-success/15 text-success',
  rejected: 'bg-red-100 text-red-600',
}

export default function MySpots() {
  const { token, user, setCredits, logout } = useAuthStore()
  const navigate = useNavigate()
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!token) return
    spotsApi
      .mine()
      .then((d) => {
        setData(d)
        setCredits(d.credits)
      })
      .catch((e) => toast.error(e.message))
  }, [token, setCredits])

  if (!token) return <Navigate to="/login?next=/me" replace />
  if (!data) return <LoadingSpinner message="Loading your spots…" />

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-4 rounded-3xl bg-white p-6 shadow-card sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-primary">Hi {user?.display_name} 👋</h1>
          <p className="mt-1 flex items-center gap-1.5 text-slate-500">
            <Lock className="h-4 w-4" /> <b className="text-slate-700">{data.credits}</b> unlock credit{data.credits === 1 ? '' : 's'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={profilePath(user)} className="inline-flex items-center gap-2 rounded-xl bg-orange-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-orange-800">
            <Stamp className="h-4 w-4" /> My passport
          </Link>
          <Link to="/spots/share" className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90">
            <Gift className="h-4 w-4" /> Share a spot
          </Link>
          {user?.is_admin && (
            <Link to="/admin/spots" className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90">
              <ShieldCheck className="h-4 w-4" /> Review queue
            </Link>
          )}
          <button
            onClick={() => { logout(); navigate('/') }}
            className="inline-flex items-center gap-2 rounded-xl bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-600"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold text-slate-700">Spots you shared</h2>
        {data.submitted.length === 0 ? (
          <EmptyState emoji="🎁" title="You haven't shared a spot yet" message="Each approved hidden spot earns you 3 unlocks." action={{ label: 'Share one', href: '/spots/share' }} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.submitted.map((s) => (
              <div key={s.id} className="space-y-1">
                <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLE[s.status]}`}>
                  {s.status}
                </span>
                <SpotCard spot={s} />
                {s.status === 'rejected' && s.review_note && <p className="text-xs text-red-500">{s.review_note}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold text-slate-700">Spots you unlocked</h2>
        {data.unlocked.length === 0 ? (
          <p className="text-sm text-slate-400">None yet. <Link to="/explore" className="font-semibold text-primary">Explore hidden gems</Link></p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.unlocked.map((s) => <SpotCard key={s.id} spot={s} />)}
          </div>
        )}
      </section>
    </div>
  )
}
