import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import SpotCard from '../components/spots/SpotCard'
import { spotsApi } from '../services/spotsService'
import { MONTHS } from '../utils/constants'

const MONTH_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** Hand-picked shelves, built automatically from categories, districts and seasons. */
export function collectionsFor(month) {
  return [
    { key: 'now', emoji: '🌿', title: `Best in ${MONTH_LONG[month - 1]}`, note: 'Nature spots at their best right now.',
      params: { in_season: month, category: 'waterfall,viewpoint,trek,lake' } },
    { key: 'hidden', emoji: '🔒', title: 'Hidden gems', note: 'Locked spots. Share one of yours to unlock them.',
      params: { hidden: true } },
    { key: 'monsoon', emoji: '🌧️', title: 'Monsoon waterfalls', note: 'Jun to Oct, when the Western Ghats roar.',
      params: { category: 'waterfall', in_season: 7 } },
    { key: 'sunrise', emoji: '🌄', title: 'Sunrise treks & viewpoints', note: 'Cool, clear mornings from Oct to Feb.',
      params: { category: 'trek,viewpoint', in_season: 12 } },
    { key: 'coffee', emoji: '☕', title: 'Coffee country cafes', note: 'Kodagu, Chikkamagaluru and Hassan.',
      params: { category: 'cafe', district: 'Kodagu,Chikkamagaluru,Hassan' } },
    { key: 'coast', emoji: '🌊', title: 'Coastal Karnataka', note: 'Udupi, Dakshina Kannada and Uttara Kannada.',
      params: { district: 'Udupi,Dakshina Kannada,Uttara Kannada', category: 'beach,viewpoint,waterfall,cafe,food' } },
    { key: 'heritage', emoji: '🏛️', title: 'Heritage trail', note: 'Temples, forts and ruins.',
      params: { category: 'heritage,temple' } },
    { key: 'lakes', emoji: '🏞️', title: 'Lakes & quiet water', note: 'Still water, slow afternoons.',
      params: { category: 'lake' } },
    { key: 'blr', emoji: '☕', title: 'Bengaluru cafes', note: 'For the weekends you stay in town.',
      params: { category: 'cafe', district: 'Bengaluru Urban' } },
  ]
}

export function Shelf({ c, limit = 12 }) {
  const [items, setItems] = useState(null)
  const ref = useRef(null)
  useEffect(() => {
    spotsApi.list({ ...c.params, limit }).then((r) => setItems(r.items)).catch(() => setItems([]))
  }, [c.key]) // eslint-disable-line react-hooks/exhaustive-deps
  if (items && !items.length) return null
  const scroll = (d) => ref.current?.scrollBy({ left: d * ref.current.clientWidth * 0.8, behavior: 'smooth' })
  return (
    <section>
      <div className="mb-2 flex items-end justify-between gap-2">
        <div>
          <h2 className="text-xl font-extrabold text-slate-800">{c.emoji} {c.title}</h2>
          <p className="text-sm text-slate-500">{c.note}</p>
        </div>
        <div className="hidden gap-1 sm:flex">
          <button onClick={() => scroll(-1)} className="rounded-full bg-white p-1.5 shadow-card" aria-label="Scroll left"><ChevronLeft className="h-5 w-5" /></button>
          <button onClick={() => scroll(1)} className="rounded-full bg-white p-1.5 shadow-card" aria-label="Scroll right"><ChevronRight className="h-5 w-5" /></button>
        </div>
      </div>
      <div ref={ref} className="no-scrollbar -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 pt-3">
        {(items || Array.from({ length: 4 })).map((s, i) => (
          <div key={s?.id || i} className="w-72 shrink-0 snap-start">
            {s ? <SpotCard spot={s} /> : <div className="h-40 animate-pulse rounded-2xl bg-slate-200" />}
          </div>
        ))}
      </div>
    </section>
  )
}

export default function Collections() {
  const month = new Date().getMonth() + 1
  return (
    <div className="space-y-8">
      <section className="rounded-3xl bg-gradient-to-br from-[#064e3b] via-[#0f766e] to-[#1e3a5f] p-6 text-white shadow-card sm:p-8">
        <p className="text-sm font-semibold uppercase tracking-wider text-white/70">Collections · {MONTHS[month - 1]}</p>
        <h1 className="mt-1 text-3xl font-extrabold sm:text-4xl">Karnataka, by season and mood</h1>
        <p className="mt-2 max-w-2xl text-white/80">
          Shelves that update themselves with the season. Looking for a quick escape?{' '}
          <Link to="/explore" className="font-semibold underline">Try “weekend getaway from” on Explore</Link>.
        </p>
      </section>
      {collectionsFor(month).map((c) => <Shelf key={c.key} c={c} />)}
    </div>
  )
}
