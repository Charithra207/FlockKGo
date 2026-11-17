import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, ChevronLeft, ChevronRight, Download, Instagram, Lock, Pause, Play } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Avatar from '../components/profile/Avatar'
import { PassportStamp } from '../components/profile/TravelBadges'
import { categoryColor } from '../components/spots/SpotMap'
import { profileApi } from '../services/profileService'
import { CATEGORY_META, catName, photoSrc } from '../services/spotsService'
import { makeWrappedImage } from '../utils/wrappedImage'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const SLIDE_MS = 6000

const BACKGROUNDS = [
  'from-[#0f2440] via-[#1e3a5f] to-[#c2410c]',
  'from-[#7c2d12] via-[#c2410c] to-[#f59e0b]',
  'from-[#064e3b] via-[#047857] to-[#0ea5e9]',
  'from-[#4c1d95] via-[#7c3aed] to-[#ec4899]',
  'from-[#1e3a5f] via-[#0f766e] to-[#84cc16]',
  'from-[#111827] via-[#1e3a5f] to-[#a16207]',
  'from-[#0f2440] via-[#1e3a5f] to-[#c2410c]',
]

const big = 'text-6xl font-black leading-none sm:text-7xl'
const kicker = 'text-sm font-bold uppercase tracking-[0.3em] text-amber-300'

function Tile({ p, i }) {
  const color = p.category === 'place' ? '#1E3A5F' : categoryColor(p.category)
  const emoji = p.category === 'place' ? '🗺️' : (CATEGORY_META[p.category] || CATEGORY_META.other).emoji
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8, rotate: i % 2 ? 4 : -4 }}
      animate={{ opacity: 1, scale: 1, rotate: i % 2 ? 2 : -2 }}
      transition={{ delay: 0.15 + i * 0.08 }}
      className="relative aspect-[3/4] overflow-hidden rounded-xl bg-white p-1.5 pb-6 shadow-xl"
    >
      {p.trip_photo_url ? (
        <img src={photoSrc(p.trip_photo_url)} alt="" className="h-full w-full rounded-lg object-cover" />
      ) : (
        <div className="grid h-full w-full place-items-center rounded-lg text-4xl" style={{ background: color }}>{emoji}</div>
      )}
      <p className="absolute inset-x-1.5 bottom-1 truncate text-center text-[10px] font-bold text-slate-700">
        {p.locked && <Lock className="mr-0.5 inline h-2.5 w-2.5" />}{p.name}
      </p>
    </motion.div>
  )
}

function slidesFor(w) {
  const s = []
  s.push(
    <div className="space-y-6 text-center">
      <p className={kicker}>FlockGo Wrapped</p>
      <Avatar user={w} size={96} className="mx-auto ring-4 ring-amber-300/70" />
      <h1 className="text-5xl font-black sm:text-6xl">{w.period.label}</h1>
      <p className="text-xl text-white/85">{w.is_me ? 'Your' : `${w.display_name}'s`} Karnataka, in stamps.</p>
      <PassportStamp size="lg" tone="light" date={w.period.end} className="mx-auto" />
    </div>,
  )
  s.push(
    <div className="space-y-5">
      <p className={kicker}>Passport stamps</p>
      <p className={big}>{w.stamps}</p>
      <p className="text-2xl font-bold">{w.stamps === 1 ? 'place stamped' : 'places stamped'}</p>
      {w.km > 0 && (
        <p className="text-xl text-white/85">
          That's about <b className="text-amber-300">{w.km.toLocaleString('en-IN')} km</b> hopping between them.
          {w.km > 500 && ' Basically a road trip across the state.'}
        </p>
      )}
      {w.verified > 0 && <p className="text-lg text-white/80">📸 {w.verified} of them photo-verified.</p>}
    </div>,
  )
  s.push(
    <div className="space-y-5">
      <p className={kicker}>Districts</p>
      <p className={big}>{w.districts.length}<span className="text-3xl text-white/60">/{w.districts_in_state}</span></p>
      <p className="text-2xl font-bold">
        districts this {w.period.month ? 'month' : 'year'}
        {w.new_districts.length > 0 && <>, <span className="text-amber-300">{w.new_districts.length} brand new</span></>}
      </p>
      <div className="flex flex-wrap gap-2">
        {w.districts.slice(0, 12).map((d) => (
          <span key={d.name} className={`rounded-full px-3 py-1 text-sm font-bold ${w.new_districts.includes(d.name) ? 'bg-amber-300 text-slate-900' : 'bg-white/15'}`}>
            {d.name}{d.count > 1 ? ` ×${d.count}` : ''}
          </span>
        ))}
      </div>
      <p className="text-white/70">{w.districts_total_explored} of {w.districts_in_state} Karnataka districts explored, all-time.</p>
    </div>,
  )
  const maxCat = Math.max(1, ...w.categories.map((c) => c.count))
  s.push(
    <div className="space-y-5">
      <p className={kicker}>Your travel personality</p>
      <p className="text-7xl">{w.personality.category && w.personality.category !== 'place' ? (CATEGORY_META[w.personality.category] || CATEGORY_META.other).emoji : '🧭'}</p>
      <p className="text-5xl font-black leading-tight">{w.personality.title}</p>
      <p className="text-xl italic text-white/85">“{w.personality.tagline}”</p>
      <div className="space-y-2 pt-2">
        {w.categories.slice(0, 4).map((c, i) => (
          <div key={c.category} className="flex items-center gap-3 text-sm font-semibold">
            <span className="w-24 truncate">{c.category === 'place' ? 'Towns' : catName(c.category)}</span>
            <motion.div
              initial={{ width: 0 }} animate={{ width: `${(c.count / maxCat) * 100}%` }} transition={{ delay: 0.2 + i * 0.1, duration: 0.6 }}
              className="h-3 max-w-[60%] rounded-full bg-amber-300"
            />
            <span>{c.count}</span>
          </div>
        ))}
      </div>
    </div>,
  )
  if (w.top_places.length) {
    s.push(
      <div className="space-y-5">
        <p className={kicker}>Moments</p>
        <p className="text-3xl font-black">From {w.first?.name} to {w.latest?.name}</p>
        <div className="grid grid-cols-3 gap-3">{w.top_places.slice(0, 6).map((p, i) => <Tile key={`${p.kind}-${p.id}`} p={p} i={i} />)}</div>
      </div>,
    )
  }
  if (w.busiest_month || w.top_percent) {
    s.push(
      <div className="space-y-8">
        {w.busiest_month && (
          <div className="space-y-2">
            <p className={kicker}>Busiest month</p>
            <p className={big}>{w.busiest_month.month}</p>
            <p className="text-xl text-white/85">{w.busiest_month.count} stamp{w.busiest_month.count === 1 ? '' : 's'}. You were everywhere.</p>
          </div>
        )}
        {w.top_percent && (
          <div className="space-y-2">
            <p className={kicker}>Ranking</p>
            <p className={big}>Top {w.top_percent}%</p>
            <p className="text-xl text-white/85">of FlockGo explorers this {w.period.month ? 'month' : 'year'}.</p>
          </div>
        )}
      </div>,
    )
  }
  return s
}

function SummaryCard({ w }) {
  return (
    <div className="space-y-4">
      <p className={kicker}>FlockGo Wrapped · {w.period.label}</p>
      <div className="flex items-center gap-3">
        <Avatar user={w} size={56} className="ring-2 ring-amber-300/70" />
        <div>
          <p className="text-2xl font-black">{w.display_name}</p>
          <p className="font-mono text-sm text-amber-200">@{w.username}</p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[[w.stamps, 'stamps'], [`${w.km.toLocaleString('en-IN')}`, 'km'], [w.districts.length, 'districts']].map(([v, l]) => (
          <div key={l} className="rounded-2xl bg-white/12 py-3" style={{ background: 'rgba(255,255,255,0.12)' }}>
            <p className="text-3xl font-black">{v}</p>
            <p className="text-xs font-bold uppercase tracking-wider text-white/70">{l}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl p-4" style={{ background: 'rgba(255,255,255,0.12)' }}>
        <p className="text-xs font-bold uppercase tracking-wider text-white/70">Travel personality</p>
        <p className="text-2xl font-black">{w.personality.title}</p>
      </div>
      <div className="grid grid-cols-3 gap-2">{w.top_places.slice(0, 3).map((p, i) => <Tile key={`${p.kind}-${p.id}`} p={p} i={i} />)}</div>
    </div>
  )
}

export default function Wrapped() {
  const { username } = useParams()
  const [params, setParams] = useSearchParams()
  const now = new Date()
  const year = Number(params.get('year')) || now.getFullYear()
  const month = params.get('month') ? Number(params.get('month')) : null
  const [w, setW] = useState(null)
  const [error, setError] = useState(null)
  const [i, setI] = useState(0)
  const [paused, setPaused] = useState(false)
  const [sharing, setSharing] = useState(false)

  useEffect(() => {
    setW(null); setError(null); setI(0)
    profileApi.wrapped(username, year, month).then(setW).catch((e) => setError(e.message))
  }, [username, year, month])

  const slides = useMemo(() => (w && w.stamps ? [...slidesFor(w), <SummaryCard key="sum" w={w} />] : []), [w])
  const last = slides.length - 1

  useEffect(() => {
    if (!slides.length || paused || i >= last) return
    const t = setTimeout(() => setI((n) => Math.min(n + 1, last)), SLIDE_MS)
    return () => clearTimeout(t)
  }, [i, paused, slides.length, last])

  async function share() {
    setSharing(true)
    try {
      const blob = await makeWrappedImage(w)
      const file = new File([blob], `flockgo-wrapped-${w.period.label.replace(/\s+/g, '-').toLowerCase()}.png`, { type: 'image/png' })
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: `My ${w.period.label} FlockGo Wrapped` }).catch(() => {})
      } else {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = file.name
        a.click()
        setTimeout(() => URL.revokeObjectURL(a.href), 5000)
        toast.success('Saved! Post it to your Instagram story')
      }
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSharing(false)
    }
  }

  const years = []
  for (let y = now.getFullYear(); y >= now.getFullYear() - 5; y--) years.push(y)
  const setPeriod = (y, m) => setParams(m ? { year: String(y), month: String(m) } : { year: String(y) })

  return (
    <div className="mx-auto max-w-md space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Link to={`/u/${username}`} className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-primary">
          <ArrowLeft className="h-4 w-4" /> Passport
        </Link>
        <div className="flex gap-2">
          <select value={month || ''} onChange={(e) => setPeriod(year, Number(e.target.value) || null)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-semibold">
            <option value="">Whole year</option>
            {MONTHS.map((m, n) => <option key={m} value={n + 1}>{m}</option>)}
          </select>
          <select value={year} onChange={(e) => setPeriod(Number(e.target.value), month)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm font-semibold">
            {years.map((y) => <option key={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {error ? (
        <div className="rounded-3xl bg-white p-8 text-center shadow-card"><p className="text-slate-500">{error}</p></div>
      ) : !w ? (
        <LoadingSpinner message="Wrapping your year…" />
      ) : !w.stamps ? (
        <div className={`rounded-3xl bg-gradient-to-br ${BACKGROUNDS[0]} p-8 text-center text-white shadow-card`}>
          <p className="text-6xl">🧳</p>
          <p className="mt-4 text-2xl font-black">No stamps in {w.period.label}</p>
          <p className="mt-2 text-white/80">
            {w.is_me ? 'Stamp the places you go (add the date you went) and your Wrapped builds itself.' : 'Nothing stamped in this period yet.'}
          </p>
          {w.is_me && <Link to="/explore" className="mt-5 inline-block rounded-xl bg-white px-5 py-2.5 font-bold text-primary">Find places</Link>}
        </div>
      ) : (
        <>
          <div
            className={`relative isolate aspect-[9/16] w-full overflow-hidden rounded-3xl bg-gradient-to-br ${BACKGROUNDS[i % BACKGROUNDS.length]} text-white shadow-2xl transition-colors duration-700`}
          >
            <div className="absolute inset-x-3 top-3 z-20 flex gap-1">
              {slides.map((_, n) => (
                <div key={n} className="h-1 flex-1 overflow-hidden rounded-full bg-white/30">
                  <div
                    className="h-full bg-white"
                    style={{
                      width: n < i ? '100%' : n === i ? (paused || i === last ? '100%' : '0%') : '0%',
                      animation: n === i && !paused && i !== last ? `wrapped-progress ${SLIDE_MS}ms linear forwards` : 'none',
                    }}
                  />
                </div>
              ))}
            </div>
            <AnimatePresence mode="wait">
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -30 }}
                transition={{ duration: 0.35 }}
                className="absolute inset-0 flex flex-col justify-center px-7 pb-10 pt-12"
              >
                {slides[i]}
              </motion.div>
            </AnimatePresence>
            {/* tap zones */}
            <button aria-label="Previous" onClick={() => setI((n) => Math.max(0, n - 1))} className="absolute inset-y-0 left-0 z-10 w-1/3" />
            <button aria-label="Next" onClick={() => setI((n) => Math.min(last, n + 1))} className="absolute inset-y-0 right-0 z-10 w-2/3" />
            <p className="absolute inset-x-0 bottom-3 z-20 text-center text-[11px] font-semibold tracking-wider text-white/60">flock-k-go.vercel.app</p>
          </div>

          <div className="flex items-center justify-between gap-2">
            <div className="flex gap-1">
              <button onClick={() => setI((n) => Math.max(0, n - 1))} className="rounded-full bg-white p-2 shadow-card" aria-label="Previous slide"><ChevronLeft className="h-5 w-5" /></button>
              <button onClick={() => setPaused((p) => !p)} className="rounded-full bg-white p-2 shadow-card" aria-label={paused ? 'Play' : 'Pause'}>
                {paused ? <Play className="h-5 w-5" /> : <Pause className="h-5 w-5" />}
              </button>
              <button onClick={() => setI((n) => Math.min(last, n + 1))} className="rounded-full bg-white p-2 shadow-card" aria-label="Next slide"><ChevronRight className="h-5 w-5" /></button>
            </div>
            <button
              onClick={share} disabled={sharing}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-fuchsia-600 via-rose-500 to-amber-400 px-4 py-2.5 font-bold text-white shadow-lg hover:opacity-95 disabled:opacity-60"
            >
              {navigator.canShare ? <Instagram className="h-5 w-5" /> : <Download className="h-5 w-5" />}
              {sharing ? 'Making your story…' : 'Share to story'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
