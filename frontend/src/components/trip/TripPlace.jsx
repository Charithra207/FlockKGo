import { Coffee, Gift, Lock, MapPin, Stamp, Sun, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import Avatar from '../profile/Avatar'
import MarkButtons from '../profile/MarkButtons'
import { PassportStamp } from '../profile/TravelBadges'
import SpotCard from '../spots/SpotCard'
import api from '../../services/api'
import { photoSrc, spotsApi } from '../../services/spotsService'
import useAuthStore from '../../store/authStore'
import { MONTHS } from '../../utils/constants'

export const tripSocialApi = {
  memories: (tripId) => api.get(`/trips/${tripId}/memories`).then((r) => r.data),
  join: (tripId) => api.post(`/trips/${tripId}/join`).then((r) => r.data),
  leave: (tripId) => api.delete(`/trips/${tripId}/join`).then((r) => r.data),
}

function SpotRow({ icon: Icon, title, items, empty }) {
  if (!items) return null
  return (
    <section>
      <h3 className="mb-3 flex items-center gap-2 text-lg font-bold text-slate-700"><Icon className="h-5 w-5" /> {title}</h3>
      {items.length ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{items.map((s) => <SpotCard key={s.id} spot={s} />)}</div>
      ) : (
        <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">{empty}</p>
      )}
    </section>
  )
}

/**
 * Everything around the group's chosen place: hidden gems, cafes, what's in
 * season that month, and the group passport ("We went! Stamp it").
 */
export default function TripPlace({ tripId, tripMonth }) {
  const { token } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [mem, setMem] = useState(null)
  const [hidden, setHidden] = useState(null)
  const [cafes, setCafes] = useState(null)
  const [seasonal, setSeasonal] = useState(null)
  const [myMark, setMyMark] = useState(null)

  const load = () => tripSocialApi.memories(tripId).then(setMem).catch(() => setMem(false))
  useEffect(() => { load() }, [tripId, token]) // eslint-disable-line react-hooks/exhaustive-deps

  const dest = mem?.destination
  const monthNum = tripMonth ? MONTHS.indexOf(tripMonth) + 1 : 0

  useEffect(() => {
    if (!dest) return
    const near = { lat: dest.latitude, lng: dest.longitude }
    spotsApi.list({ ...near, radius_km: 40, hidden: true, limit: 6 }).then((r) => setHidden(r.items)).catch(() => setHidden([]))
    spotsApi.list({ ...near, radius_km: 25, category: 'cafe', limit: 6 }).then((r) => setCafes(r.items)).catch(() => setCafes([]))
    if (monthNum > 0) {
      spotsApi.list({ ...near, radius_km: 40, hidden: false, in_season: monthNum, category: 'waterfall,viewpoint,trek,lake', limit: 6 })
        .then((r) => setSeasonal(r.items)).catch(() => setSeasonal([]))
    }
    if (token) {
      api.get('/marks/mine').then((r) => setMyMark(r.data.destinations[dest.id] ?? null)).catch(() => {})
    }
  }, [dest?.id, monthNum, token]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!mem || !dest) return null

  async function join() {
    if (!token) return navigate(`/login?next=${encodeURIComponent(location.pathname)}`)
    try {
      await tripSocialApi.join(tripId)
      toast.success("You're on the trip! Stamp it once you've been.")
      load()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const shareHere = `/spots/share?district=${encodeURIComponent(dest.district || '')}&lat=${dest.latitude}&lng=${dest.longitude}`

  return (
    <div className="space-y-8">
      <div className="rounded-2xl bg-gradient-to-br from-primary to-[#0f2440] p-6 text-white shadow-card">
        <p className="text-xs font-bold uppercase tracking-[0.3em] text-amber-300">Around {dest.name}</p>
        <h2 className="mt-1 text-2xl font-extrabold">The local side of {dest.name}</h2>
        <p className="mt-1 text-white/80">
          <MapPin className="mr-1 inline h-4 w-4" />{dest.district} district. Hidden gems locals shared, cafes nearby
          {monthNum > 0 ? ` and what's at its best in ${MONTHS[monthNum - 1]}` : ''}.
        </p>
      </div>

      {monthNum > 0 && <SpotRow icon={Sun} title={`At its best in ${MONTHS[monthNum - 1]}`} items={seasonal} empty="Nothing listed for that month yet." />}
      <SpotRow
        icon={Lock} title="Hidden gems nearby" items={hidden}
        empty={<>No hidden gems mapped around here yet. Be the first: <Link to={shareHere} className="font-semibold text-primary underline">share one</Link>.</>}
      />
      <SpotRow icon={Coffee} title="Cafes nearby" items={cafes} empty="No cafes mapped here yet. Found a good one? Share it!" />

      {/* Group passport */}
      <section className="rounded-2xl border-2 border-dashed border-orange-300 bg-orange-50/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-extrabold text-orange-800"><Stamp className="h-5 w-5" /> Group passport</h3>
            <p className="text-sm text-slate-600">
              After the trip, everyone stamps {dest.name} with a photo. It goes into each person's passport and their Wrapped.
            </p>
          </div>
          {!mem.me_joined ? (
            <button onClick={join} className="inline-flex items-center gap-1.5 rounded-xl bg-orange-700 px-4 py-2 text-sm font-bold text-white hover:bg-orange-800">
              <Users className="h-4 w-4" /> I'm on this trip
            </button>
          ) : (
            <MarkButtons
              destinationId={dest.id} placeName={dest.name} value={myMark}
              onChange={(v, r) => { setMyMark(v); if (r) load() }}
            />
          )}
        </div>

        {mem.members.length > 0 && (
          <>
            <p className="mt-4 text-xs font-bold uppercase tracking-wider text-slate-400">
              {mem.stamped_count}/{mem.members.length} stamped
            </p>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {mem.members.map((m) => (
                <Link key={m.username} to={`/u/${m.username}`} className="relative flex items-center gap-3 overflow-hidden rounded-xl bg-white p-3 shadow-sm hover:shadow">
                  <Avatar user={m} size={40} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-slate-700">{m.display_name}</p>
                    <p className="text-xs text-slate-400">{m.stamped ? (m.visited_on ? `Went on ${m.visited_on}` : 'Been there') : 'Not stamped yet'}</p>
                  </div>
                  {m.trip_photo_url && <img src={photoSrc(m.trip_photo_url)} alt="" className="h-12 w-12 rounded-lg object-cover" />}
                  {m.stamped && <PassportStamp size="sm" verified={m.photo_verified} animate={false} className="shrink-0" />}
                </Link>
              ))}
            </div>
          </>
        )}

        <Link to={shareHere} className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-accent underline">
          <Gift className="h-4 w-4" /> Found a hidden spot on this trip? Share it and earn 3 unlocks
        </Link>
      </section>
    </div>
  )
}
