import {
  CalendarDays, ChevronLeft, LogOut, ChevronRight, EyeOff, Gift, Lock, MapPin, MapPinned, Pencil,
  Plane, Plus, Search, Share2, ShieldCheck, Sparkles, Stamp, X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useNavigate, useParams } from 'react-router-dom'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Avatar from '../components/profile/Avatar'
import MarkButtons from '../components/profile/MarkButtons'
import { BoardingPass, PassportStamp } from '../components/profile/TravelBadges'
import { categoryColor } from '../components/spots/SpotMap'
import { profileApi } from '../services/profileService'
import { CATEGORY_META, catName, photoSrc, spotTitle } from '../services/spotsService'
import useAuthStore from '../store/authStore'
import { useT } from '../i18n'

// ── Postcards (one per place in a row) ────────────────────────────────────────

function Postcard({ item, mark }) {
  const isSpot = item.kind === 'spot'
  const color = isSpot ? categoryColor(item.category) : '#1E3A5F'
  const emoji = isSpot ? (CATEGORY_META[item.category] || CATEGORY_META.other).emoji : '🗺️'
  const to = isSpot ? `/spots/${item.id}` : `/explore?district=${encodeURIComponent(item.district || '')}`
  // Your own trip photo wins; otherwise the spot's photo (if you can see it).
  const photo = item.trip_photo_url
    ? photoSrc(item.trip_photo_url)
    : isSpot && !item.locked && item.photo_url ? photoSrc(item.photo_url) : null
  const title = isSpot ? spotTitle(item) : item.name
  const sub = isSpot ? `${item.destination ? `${item.destination}, ` : ''}${item.district}` : item.district

  return (
    <Link
      to={to}
      className="group relative block h-56 w-40 shrink-0 snap-start overflow-hidden rounded-2xl shadow-card ring-1 ring-black/5 transition-transform duration-200 hover:-translate-y-1 hover:shadow-lg sm:h-64 sm:w-48"
    >
      {photo ? (
        <img src={photo} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
      ) : (
        <div
          className="absolute inset-0"
          style={{ background: `linear-gradient(150deg, ${color}dd 0%, ${color} 45%, #0f172a 100%)` }}
        >
          <span className={`absolute left-1/2 top-[38%] -translate-x-1/2 -translate-y-1/2 text-6xl drop-shadow ${item.locked ? 'blur-[2px]' : ''}`}>
            {emoji}
          </span>
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/50 to-transparent p-3 pt-10 text-white">
        <p className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-white/70">
          {isSpot ? catName(item.category) : 'Place'}
        </p>
        <p className={`line-clamp-2 font-bold leading-tight ${item.locked ? 'italic' : ''}`}>
          {item.locked && <Lock className="mr-1 inline h-3.5 w-3.5 text-accent" />}
          {title}
        </p>
        <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-white/70">
          <MapPin className="h-3 w-3 shrink-0" /> {sub}
        </p>
      </div>
      {mark === 'been' && (
        <PassportStamp date={item.visited_on || item.marked_at} verified={item.photo_verified} tone="light" animate={false} className="absolute right-1 top-2" />
      )}
      {mark === 'want' && <BoardingPass size="sm" animate={false} className="absolute right-2 top-3" />}
    </Link>
  )
}

function Row({ icon: Icon, title, hint, items, mark, empty }) {
  const ref = useRef(null)
  const scroll = (dir) => ref.current?.scrollBy({ left: dir * ref.current.clientWidth * 0.8, behavior: 'smooth' })
  return (
    <section>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-extrabold text-slate-800">
            <Icon className="h-5 w-5" /> {title}
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-bold text-slate-600">{items.length}</span>
          </h2>
          {hint && <p className="text-sm text-slate-500">{hint}</p>}
        </div>
        {items.length > 3 && (
          <div className="hidden gap-1 sm:flex">
            <button onClick={() => scroll(-1)} className="rounded-full bg-white p-1.5 shadow-card hover:text-primary" aria-label="Scroll left"><ChevronLeft className="h-5 w-5" /></button>
            <button onClick={() => scroll(1)} className="rounded-full bg-white p-1.5 shadow-card hover:text-primary" aria-label="Scroll right"><ChevronRight className="h-5 w-5" /></button>
          </div>
        )}
      </div>
      {items.length ? (
        <div ref={ref} className="no-scrollbar -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-3 pt-3">
          {items.map((it) => <Postcard key={`${it.kind}-${it.id}`} item={it} mark={mark} />)}
        </div>
      ) : (
        <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white/60 p-6 text-center text-sm text-slate-500">{empty}</div>
      )}
    </section>
  )
}

// ── "Karnataka explored": 31 district tiles, like a contribution graph ────────

function tileClass(n) {
  if (!n) return 'bg-slate-100 text-slate-400'
  if (n === 1) return 'bg-orange-200 text-orange-900'
  if (n <= 3) return 'bg-orange-400 text-white'
  return 'bg-orange-700 text-white'
}

function DistrictGrid({ districts, explored, total }) {
  const pct = Math.round((explored / total) * 100)
  return (
    <section className="rounded-2xl bg-white p-5 shadow-card">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-extrabold text-slate-800">
            <MapPinned className="h-5 w-5 text-orange-700" /> Karnataka explored
          </h2>
          <p className="text-sm text-slate-500">{explored} of {total} districts stamped</p>
        </div>
        <span className="text-3xl font-black text-orange-700">{pct}%</span>
      </div>
      <div className="mb-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-gradient-to-r from-orange-400 to-orange-700 transition-all duration-700" style={{ width: `${pct}%` }} />
      </div>
      <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-5 lg:grid-cols-7">
        {districts.map((d) => (
          <Link
            key={d.name}
            to={`/explore?district=${encodeURIComponent(d.name)}`}
            title={`${d.name}: ${d.count} place${d.count === 1 ? '' : 's'}`}
            className={`flex h-12 flex-col justify-center rounded-lg px-2 text-[11px] font-semibold leading-tight transition-transform hover:scale-105 ${tileClass(d.count)}`}
          >
            <span className="line-clamp-2">{d.name}</span>
            {d.count > 0 && <span className="text-[10px] font-black opacity-80">×{d.count}</span>}
          </Link>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-end gap-1 text-[10px] text-slate-400">
        Less {[0, 1, 2, 4].map((n) => <span key={n} className={`h-3 w-3 rounded-sm ${tileClass(n).split(' ')[0]}`} />)} More
      </div>
    </section>
  )
}

// ── "Add places" picker for the 65 Karnataka hubs ─────────────────────────────

function PlacePicker({ onClose, onChanged }) {
  const [places, setPlaces] = useState(null)
  const [marks, setMarks] = useState({})
  const [q, setQ] = useState('')

  useEffect(() => {
    Promise.all([profileApi.destinations(), profileApi.myMarks()])
      .then(([d, m]) => { setPlaces(d.items); setMarks(m.destinations) })
      .catch((e) => toast.error(e.message))
  }, [])

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (places || []).filter((p) => !needle || `${p.name} ${p.district}`.toLowerCase().includes(needle))
  }, [places, q])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/60 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-t-3xl bg-white shadow-2xl sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b p-4">
          <div>
            <h3 className="text-lg font-extrabold text-primary">Where have you been?</h3>
            <p className="text-xs text-slate-500">Stamp places you've visited, or add them to your bucket list.</p>
          </div>
          <button onClick={onClose} className="rounded-full p-1.5 hover:bg-slate-100" aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        <div className="border-b p-3">
          <label className="flex items-center gap-2 rounded-xl bg-slate-100 px-3 py-2">
            <Search className="h-4 w-4 text-slate-400" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search Coorg, Hampi, Gokarna…" className="w-full bg-transparent text-sm outline-none" autoFocus />
          </label>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {!places ? <LoadingSpinner message="Loading places…" /> : shown.map((p) => (
            <div key={p.id} className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 hover:bg-slate-50">
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-800">{p.name}</p>
                <p className="truncate text-xs text-slate-500">{p.district}{p.quick_info ? ` · ${p.quick_info}` : ''}</p>
              </div>
              <MarkButtons
                compact
                placeName={p.name}
                destinationId={p.id}
                value={marks[p.id] ?? null}
                onChange={(v) => { setMarks((m) => ({ ...m, [p.id]: v })); onChanged() }}
              />
            </div>
          ))}
        </div>
        <div className="border-t p-3">
          <button onClick={onClose} className="w-full rounded-xl bg-primary py-2.5 font-semibold text-white hover:opacity-90">Done</button>
        </div>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Stat({ value, label, accent }) {
  return (
    <div className="rounded-2xl bg-white px-4 py-3 text-center shadow-card">
      <p className={`text-2xl font-black ${accent || 'text-primary'}`}>{value}</p>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
    </div>
  )
}

export default function Profile() {
  const { username } = useParams()
  const { token, logout } = useAuthStore()
  const navigate = useNavigate()
  const t = useT()
  const [p, setP] = useState(null)
  const [error, setError] = useState(null)
  const [picker, setPicker] = useState(false)
  const [dirty, setDirty] = useState(0)

  useEffect(() => {
    setError(null)
    profileApi.get(username).then(setP).catch((e) => setError(e))
  }, [username, token, dirty])

  if (error) {
    return (
      <div className="rounded-2xl bg-white p-10 text-center shadow-card">
        <p className="text-5xl">🧭</p>
        <p className="mt-3 font-semibold text-slate-700">{error.status === 404 ? 'No traveller with that username.' : error.message}</p>
        <Link to="/explore" className="mt-3 inline-block font-semibold text-primary">Explore Karnataka</Link>
      </div>
    )
  }
  if (!p) return <LoadingSpinner message="Opening passport…" />

  const since = p.member_since ? new Date(p.member_since).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }) : null

  function share() {
    const url = window.location.href
    if (navigator.share) navigator.share({ title: `${p.display_name} on FlockGo`, url }).catch(() => {})
    else navigator.clipboard?.writeText(url).then(() => toast.success('Profile link copied'))
  }

  return (
    <div className="space-y-8">
      {/* Passport cover */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary via-[#24476f] to-[#0f2440] p-6 text-white shadow-card sm:p-8">
        <div className="pointer-events-none absolute -right-10 -top-10 h-48 w-48 rounded-full border-[18px] border-white/5" />
        <div className="pointer-events-none absolute -bottom-16 right-24 h-40 w-40 rounded-full border-[14px] border-amber-300/10" />
        <p className="text-[10px] font-bold uppercase tracking-[0.35em] text-amber-300/80">FlockGo · Karnataka passport</p>
        <div className="mt-4 flex flex-col gap-5 sm:flex-row sm:items-center">
          <Avatar user={p} size={96} className="ring-4 ring-amber-300/70" />
          <div className="min-w-0 flex-1">
            <h1 className="flex flex-wrap items-center gap-2 text-3xl font-black">
              {p.display_name}
              {p.is_admin && <ShieldCheck className="h-6 w-6 text-amber-300" title="FlockGo admin" />}
            </h1>
            <p className="font-mono text-amber-200/90">@{p.username}</p>
            {p.bio && <p className="mt-2 max-w-xl text-white/85">{p.bio}</p>}
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-white/70">
              {p.home_district && <span className="inline-flex items-center gap-1"><MapPin className="h-4 w-4" /> {p.home_district}</span>}
              {since && <span className="inline-flex items-center gap-1"><CalendarDays className="h-4 w-4" /> Exploring since {since}</span>}
              {p.is_me && !p.private && !p.profile_public && <span className="inline-flex items-center gap-1"><EyeOff className="h-4 w-4" /> Only you can see this</span>}
            </div>
          </div>
          <div className="flex gap-2 sm:flex-col">
            {p.is_me && (
              <Link to="/settings/profile" className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-white px-4 py-2 text-sm font-bold text-primary hover:bg-amber-50">
                <Pencil className="h-4 w-4" /> Edit profile
              </Link>
            )}
            <button onClick={share} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-white/30 px-4 py-2 text-sm font-bold hover:bg-white/10">
              <Share2 className="h-4 w-4" /> Share
            </button>
            {p.is_me && (
              <button
                onClick={() => { logout(); navigate('/') }}
                className="inline-flex items-center justify-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white/70 hover:bg-white/10 hover:text-white"
              >
                <LogOut className="h-4 w-4" /> Log out
              </button>
            )}
          </div>
        </div>
      </section>

      {p.private ? (
        <div className="rounded-2xl bg-white p-10 text-center shadow-card">
          <EyeOff className="mx-auto h-10 w-10 text-slate-300" />
          <p className="mt-3 font-semibold text-slate-700">This passport is private.</p>
        </div>
      ) : (
        <>
          {p.stats.been > 0 && (
            <Link
              to={`/u/${p.username}/wrapped?year=${new Date().getFullYear()}`}
              className="group flex items-center gap-4 overflow-hidden rounded-2xl bg-gradient-to-r from-[#0f2440] via-[#c2410c] to-amber-400 p-4 text-white shadow-card"
            >
              <Sparkles className="h-8 w-8 shrink-0 text-amber-200 transition-transform group-hover:rotate-12" />
              <div className="flex-1">
                <p className="text-lg font-black">{p.is_me ? 'Your' : `${p.display_name}'s`} {new Date().getFullYear()} Wrapped</p>
                <p className="text-sm text-white/85">Stamps, kilometres, districts and travel personality. Monthly too. Share it to your story.</p>
              </div>
              <ChevronRight className="h-6 w-6 shrink-0" />
            </Link>
          )}

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <Stat value={p.stats.been} label="Stamps" accent="text-orange-700" />
            <Stat value={p.stats.want} label="Bucket list" />
            <Stat value={`${p.stats.districts_explored}/${p.stats.districts_total}`} label="Districts" accent="text-orange-700" />
            <Stat value={p.stats.spots_shared} label="Spots shared" accent="text-accent" />
            <Stat value={p.stats.vouches} label="Vouches" accent="text-success" />
          </div>

          {p.is_me && (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border-2 border-dashed border-orange-300 bg-orange-50/60 p-4">
              <Stamp className="h-6 w-6 text-orange-700" />
              <p className="flex-1 text-sm text-slate-600">
                Fill your passport: stamp the Karnataka places you've been, and line up the ones you're dreaming of.
              </p>
              <button onClick={() => setPicker(true)} className="inline-flex items-center gap-1.5 rounded-xl bg-orange-700 px-4 py-2 text-sm font-bold text-white hover:bg-orange-800">
                <Plus className="h-4 w-4" /> Add places
              </button>
            </div>
          )}

          <Row
            icon={Stamp} title="Passport stamps" mark="been" items={p.been}
            hint={p.is_me ? 'Places you have been' : `Places ${p.display_name} has been`}
            empty={p.is_me ? 'No stamps yet. Tap “Add places”, or the stamp button on any spot.' : 'No stamps yet.'}
          />
          <Row
            icon={Plane} title="Bucket list" mark="want" items={p.want}
            hint={p.is_me ? 'Where you want to go next' : `Where ${p.display_name} wants to go`}
            empty={p.is_me ? 'Nothing here yet. Tap the ✈ button on any spot to save it.' : 'Nothing on the list yet.'}
          />

          <DistrictGrid districts={p.districts} explored={p.stats.districts_explored} total={p.stats.districts_total} />

          {(p.shared.length > 0 || p.is_me) && (
            <Row
              icon={Gift} title="Spots shared" items={p.shared}
              hint={p.is_me ? 'Places you gave to the community' : `Places ${p.display_name} shared with everyone`}
              empty={<>No shared spots yet. <Link to="/spots/share" className="font-semibold text-primary underline">{t('nav.share')}</Link> to earn unlocks.</>}
            />
          )}

          {p.is_me && (
            <p className="text-center text-sm text-slate-400">
              Your credits, unlocked spots and submissions: <Link to="/me" className="font-semibold text-primary underline">My spots</Link>
            </p>
          )}
        </>
      )}

      {picker && <PlacePicker onClose={() => { setPicker(false); setDirty((n) => n + 1) }} onChanged={() => {}} />}
    </div>
  )
}
