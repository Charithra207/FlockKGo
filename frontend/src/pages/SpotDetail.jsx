import { ArrowLeft, CalendarDays, FileWarning, Gift, Lock, Navigation, ShieldCheck, Unlock } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useNavigate, useParams } from 'react-router-dom'
import LoadingSpinner from '../components/common/LoadingSpinner'
import SpotCard from '../components/spots/SpotCard'
import SpotMap from '../components/spots/SpotMap'
import SafetyNotes from '../components/spots/SafetyNotes'
import ReportButton from '../components/spots/ReportButton'
import MarkButtons from '../components/profile/MarkButtons'
import { BoardingPass, PassportStamp } from '../components/profile/TravelBadges'
import { categoryLabel, catName, directionsUrl, monthNames, photoSrc, spotsApi, spotTitle } from '../services/spotsService'
import useAuthStore from '../store/authStore'
import { useT } from '../i18n'

function MonthChips({ months }) {
  if (!months?.length) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <CalendarDays className="h-4 w-4 text-slate-400" />
      {monthNames().map((m, i) => (
        <span
          key={m}
          className={`rounded-md px-1.5 py-0.5 text-xs font-medium ${months.includes(i + 1) ? 'bg-success/15 text-success' : 'text-slate-300'}`}
        >
          {m}
        </span>
      ))}
    </div>
  )
}

function Nearby({ spot }) {
  const t = useT()
  const [cafes, setCafes] = useState([])
  const [others, setOthers] = useState([])
  const lat = spot.latitude ?? spot.approx_latitude
  const lng = spot.longitude ?? spot.approx_longitude

  useEffect(() => {
    const base = { lat, lng, radius_km: 15, limit: 7 }
    spotsApi.list({ ...base, category: 'cafe' }).then((r) => setCafes(r.items.filter((s) => s.id !== spot.id).slice(0, 6))).catch(() => {})
    spotsApi.list({ ...base, hidden: true, radius_km: 30 }).then((r) => setOthers(r.items.filter((s) => s.id !== spot.id).slice(0, 6))).catch(() => {})
  }, [spot.id, lat, lng])

  return (
    <>
      {cafes.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-bold text-slate-700">{t('spot.cafesNearby')}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{cafes.map((s) => <SpotCard key={s.id} spot={s} />)}</div>
        </section>
      )}
      {others.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-bold text-slate-700">{t('spot.moreHidden')}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{others.map((s) => <SpotCard key={s.id} spot={s} />)}</div>
        </section>
      )}
    </>
  )
}

export default function SpotDetail() {
  const { spotId } = useParams()
  const navigate = useNavigate()
  const { token, user, setCredits } = useAuthStore()
  const t = useT()
  const [spot, setSpot] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [pledged, setPledged] = useState(() => {
    try { return localStorage.getItem('flockgo-pledge') === '1' } catch { return false }
  })
  function pledge(v) {
    setPledged(v)
    try { localStorage.setItem('flockgo-pledge', v ? '1' : '0') } catch { /* private mode */ }
  }

  useEffect(() => {
    setSpot(null)
    spotsApi.get(spotId).then(setSpot).catch((e) => setError(e.message))
  }, [spotId, token])

  async function unlock() {
    if (!token) return navigate(`/login?next=/spots/${spotId}`)
    setBusy(true)
    try {
      const r = await spotsApi.unlock(spotId)
      setSpot((s) => ({ ...r.spot, my_mark: s?.my_mark ?? null }))
      setCredits(r.credits)
      toast.success(r.spent ? `Unlocked! ${r.credits} credit${r.credits === 1 ? '' : 's'} left` : 'Unlocked')
    } catch (e) {
      if (e.status === 402) {
        toast((t) => (
          <span>
            {e.message}{' '}
            <button className="font-semibold text-primary underline" onClick={() => { toast.dismiss(t.id); navigate('/spots/share') }}>
              Share one
            </button>
          </span>
        ))
      } else toast.error(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function vouch() {
    setBusy(true)
    try {
      const r = await spotsApi.vouch(spotId)
      setSpot((s) => ({ ...s, vouch_count: r.vouch_count, vouched_by_me: true }))
      if (!r.already) toast.success('Thanks for confirming!')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-slate-500">{error}</p>
        <Link to="/explore" className="mt-3 inline-block font-semibold text-primary">Back to Explore</Link>
      </div>
    )
  }
  if (!spot) return <LoadingSpinner message="Loading spot…" />

  const credits = user?.unlock_credits ?? 0

  return (
    <div className="space-y-6">
      <button onClick={() => navigate(-1)} className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-primary">
        <ArrowLeft className="h-4 w-4" /> {t('spot.back')}
      </button>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-3">
          <div className="relative rounded-2xl bg-white p-6 shadow-card">
            {spot.my_mark === 'been' && (
              <PassportStamp size="lg" date={spot.my_mark_detail?.visited_on} verified={spot.my_mark_detail?.photo_verified} className="absolute right-4 top-10 z-10" />
            )}
            {spot.my_mark === 'want' && <BoardingPass className="absolute right-4 top-12 z-10" />}
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-semibold text-slate-600">{categoryLabel(spot.category)}</span>
              <span className="text-slate-300">•</span>
              <span className="text-slate-500">{spot.destination ? `${spot.destination}, ` : ''}{spot.district}</span>
              {spot.status !== 'approved' && (
                <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-semibold capitalize text-warning">{spot.status}</span>
              )}
              {(user?.is_admin || (spot.is_mine && spot.status === 'pending')) && (
                <Link to={`/spots/${spot.id}/edit`} className="ml-auto text-xs font-semibold text-primary underline">{t('spot.edit')}</Link>
              )}
            </div>
            <h1 className={`mt-2 text-3xl font-extrabold ${spot.my_mark ? 'pr-24' : ''} ${spot.locked ? 'italic text-slate-500' : 'text-primary'}`}>
              {spot.locked && <Lock className="mr-2 inline h-6 w-6 text-accent" />}
              {spotTitle(spot)}
            </h1>

            {spot.status === 'approved' && (
              <div className="mt-4">
                <MarkButtons
                  spotId={spot.id}
                  value={spot.my_mark ?? null}
                  placeName={spotTitle(spot)}
                  onChange={(v, r) => setSpot((s) => ({ ...s, my_mark: v, ...(r ? { my_mark_detail: r } : {}) }))}
                />
              </div>
            )}

            <div className="mt-4"><SafetyNotes spot={spot} /></div>

            {spot.locked ? (
              <div className="mt-5 rounded-xl border-2 border-dashed border-accent/40 bg-accent/5 p-5">
                <p className="font-semibold text-slate-700">{t('spot.lockedTitle', { cat: catName(spot.category) })}</p>
                <p className="mt-1 text-sm text-slate-500">
                  {t('spot.lockedBody')}
                  {spot.vouch_count > 0 && ` ${t('spot.confirmed', { n: spot.vouch_count })}`}
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  {token && credits > 0 && (
                    <label className="flex w-full items-start gap-2 text-xs text-slate-600">
                      <input type="checkbox" checked={pledged} onChange={(e) => pledge(e.target.checked)} className="mt-0.5" />
                      <span>🌱 I'll leave no trace: carry my trash back, keep it quiet, and won't post the exact location publicly.</span>
                    </label>
                  )}
                  {token && credits > 0 ? (
                    <button disabled={busy || !pledged} onClick={unlock} className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 font-semibold text-white hover:opacity-90 disabled:opacity-50">
                      <Unlock className="h-4 w-4" /> {t('spot.unlock', { n: credits })}
                    </button>
                  ) : token ? (
                    <Link to="/spots/share" className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 font-semibold text-white hover:opacity-90">
                      <Gift className="h-4 w-4" /> {t('spot.earn')}
                    </Link>
                  ) : (
                    <Link to={`/login?next=/spots/${spotId}`} className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 font-semibold text-white hover:opacity-90">
                      {t('spot.signup')}
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              <div className="mt-4 space-y-4">
                {spot.photo_url && (
                  <img src={photoSrc(spot.photo_url)} alt={spot.name} className="max-h-80 w-full rounded-xl object-cover" loading="lazy" />
                )}
                {spot.description && <p className="whitespace-pre-line text-slate-600">{spot.description}</p>}
                {spot.access_notes && (
                  <div className="rounded-xl bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{t('spot.howTo')}</p>
                    <p className="mt-1 whitespace-pre-line text-sm text-slate-600">{spot.access_notes}</p>
                  </div>
                )}
                {spot.extra?.opening_hours && (
                  <p className="text-sm text-slate-500"><span className="font-semibold">{t('spot.hours')}:</span> {spot.extra.opening_hours}</p>
                )}
                <div className="flex flex-wrap gap-3">
                  <a href={directionsUrl(spot.latitude, spot.longitude)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-90">
                    <Navigation className="h-4 w-4" /> {t('spot.directions')}
                  </a>
                  {user?.is_admin && (
                    <button
                      disabled={busy}
                      onClick={async () => {
                        try {
                          const r = await spotsApi.review(spot.id, spot.featured ? 'unfeature' : 'feature')
                          setSpot((s) => ({ ...s, featured: r.featured }))
                        } catch (e) { toast.error(e.message) }
                      }}
                      className="rounded-xl bg-amber-100 px-4 py-2 text-sm font-semibold text-amber-700"
                    >
                      {spot.featured ? '★ Unfeature' : '☆ Mark as famous'}
                    </button>
                  )}
                  {token && !spot.is_mine && (
                    <button disabled={busy || spot.vouched_by_me} onClick={vouch} className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-success shadow-card disabled:opacity-60">
                      <ShieldCheck className="h-4 w-4" /> {spot.vouched_by_me ? t('spot.vouched') : t('spot.vouch')}
                    </button>
                  )}
                </div>
              </div>
            )}

            <div className="mt-5 space-y-3 border-t pt-4">
              <MonthChips months={spot.best_months} />
              {spot.permit_required && (
                <p className="flex items-center gap-1.5 text-sm font-medium text-warning">
                  <FileWarning className="h-4 w-4" /> {t('spot.permit')}
                </p>
              )}
              {spot.vouch_count > 0 && (
                <p className="flex items-center gap-1.5 text-sm text-slate-500">
                  <ShieldCheck className="h-4 w-4 text-success" /> {t('spot.confirmedBy', { n: spot.vouch_count })}
                </p>
              )}
              {spot.source === 'osm' && (
                <p className="text-xs text-slate-400">Listing from © OpenStreetMap contributors</p>
              )}
              <ReportButton spotId={spot.id} />
              {spot.is_hidden && !spot.locked && (
                <p className="text-xs text-slate-400">
                  {t('spot.respect')}
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          <SpotMap
            spots={[spot]}
            center={spot.locked ? [spot.approx_latitude, spot.approx_longitude] : [spot.latitude, spot.longitude]}
            zoom={spot.locked ? 10 : 13}
            height={380}
          />
        </div>
      </div>

      <Nearby spot={spot} />
    </div>
  )
}
