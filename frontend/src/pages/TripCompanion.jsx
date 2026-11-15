import { ArrowLeft, Backpack, Bus, CalendarDays, Check, Phone, Plus, Siren, Sparkles, Trash2, Wallet } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import LoadingSpinner from '../components/common/LoadingSpinner'
import SpotCard from '../components/spots/SpotCard'
import { companionApi, inr } from '../services/companionService'
import { spotsApi } from '../services/spotsService'

const TABS = [
  { key: 'packing', label: 'Packing', icon: Backpack },
  { key: 'expenses', label: 'Expenses', icon: Wallet },
  { key: 'itinerary', label: 'Itinerary', icon: CalendarDays },
  { key: 'travel', label: 'Getting there', icon: Bus },
  { key: 'sos', label: 'SOS', icon: Siren },
]

const card = 'rounded-2xl bg-white p-5 shadow-card'
const input = 'rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none'

// ── Packing ───────────────────────────────────────────────────────────────────

function Packing({ tripId, people }) {
  const [data, setData] = useState(null)
  const [name, setName] = useState('')
  const [category, setCategory] = useState('misc')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => companionApi.checklist(tripId).then(setData).catch((e) => toast.error(e.message)), [tripId])
  useEffect(() => { load() }, [load])

  async function run(fn, ok) {
    setBusy(true)
    try { await fn(); await load(); if (ok) toast.success(ok) } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }

  if (!data) return <LoadingSpinner message="Loading packing list…" />
  const cats = Object.entries(data.categories)

  return (
    <div className="space-y-4">
      <div className={`${card} flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`}>
        <div className="flex-1">
          <p className="text-sm font-semibold text-slate-600">{data.packed_items} of {data.total_items} packed</p>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-success transition-all" style={{ width: `${data.completion_pct}%` }} />
          </div>
        </div>
        <button disabled={busy} onClick={() => run(async () => {
          const r = await companionApi.suggestChecklist(tripId)
          toast.success(`Added ${r.generated} items for ${r.destination}`)
        })} className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          <Sparkles className="h-4 w-4" /> Suggest a list
        </button>
      </div>

      <form
        className={`${card} flex flex-col gap-2 sm:flex-row`}
        onSubmit={(e) => {
          e.preventDefault()
          if (!name.trim()) return
          run(() => companionApi.addItem(tripId, { name: name.trim(), category }).then(() => setName('')))
        }}
      >
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Add an item, e.g. raincoat" className={`${input} flex-1`} maxLength={200} />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className={input}>
          {['clothing', 'toiletries', 'documents', 'electronics', 'health', 'gear', 'food', 'misc'].map((c) => <option key={c}>{c}</option>)}
        </select>
        <button disabled={busy} className="inline-flex items-center justify-center gap-1 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white"><Plus className="h-4 w-4" /> Add</button>
      </form>

      {cats.length === 0 && <p className="text-center text-sm text-slate-400">Nothing yet. Tap “Suggest a list” to start from the destination's weather and vibe.</p>}

      {cats.map(([cat, items]) => (
        <div key={cat} className={card}>
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-400">{cat}</h3>
          <ul className="divide-y">
            {items.map((it) => (
              <li key={it.id} className="flex items-center gap-3 py-2">
                <button
                  aria-label={it.is_packed ? 'Mark not packed' : 'Mark packed'}
                  onClick={() => run(() => companionApi.patchItem(tripId, it.id, { is_packed: !it.is_packed }))}
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border-2 ${it.is_packed ? 'border-success bg-success text-white' : 'border-slate-300'}`}
                >
                  {it.is_packed && <Check className="h-4 w-4" />}
                </button>
                <span className={`flex-1 text-sm ${it.is_packed ? 'text-slate-400 line-through' : 'text-slate-700'}`}>{it.name}</span>
                <select
                  value={it.assigned_to_participant_id || ''}
                  onChange={(e) => run(() => companionApi.patchItem(tripId, it.id, { assigned_to_participant_id: e.target.value }))}
                  className="max-w-[8rem] rounded-lg border border-slate-200 px-1.5 py-1 text-xs text-slate-500"
                >
                  <option value="">Anyone</option>
                  {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <button aria-label="Delete" onClick={() => run(() => companionApi.deleteItem(tripId, it.id))} className="text-slate-300 hover:text-red-500">
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

// ── Expenses ──────────────────────────────────────────────────────────────────

function Expenses({ tripId, people }) {
  const [list, setList] = useState(null)
  const [settle, setSettle] = useState(null)
  const [form, setForm] = useState({ paid_by_participant_id: '', description: '', amount_inr: '', category: 'food' })
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => Promise.all([
    companionApi.expenses(tripId).then(setList),
    companionApi.settlement(tripId).then(setSettle),
  ]).catch((e) => toast.error(e.message)), [tripId])
  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!form.paid_by_participant_id && people[0]) setForm((f) => ({ ...f, paid_by_participant_id: people[0].id }))
  }, [people, form.paid_by_participant_id])

  async function add(e) {
    e.preventDefault()
    const amount = parseInt(form.amount_inr, 10)
    if (!amount || amount <= 0) return toast.error('Enter an amount')
    setBusy(true)
    try {
      await companionApi.addExpense(tripId, { ...form, amount_inr: amount })
      setForm((f) => ({ ...f, description: '', amount_inr: '' }))
      await load()
    } catch (err) { toast.error(err.message) } finally { setBusy(false) }
  }

  if (!list || !settle) return <LoadingSpinner message="Loading expenses…" />
  const nameOf = (id) => people.find((p) => p.id === id)?.name || '—'

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <div className="space-y-4 lg:col-span-3">
        <form onSubmit={add} className={`${card} grid gap-2 sm:grid-cols-2`}>
          <input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What for? e.g. homestay" className={`${input} sm:col-span-2`} maxLength={300} />
          <input required inputMode="numeric" value={form.amount_inr} onChange={(e) => setForm({ ...form, amount_inr: e.target.value.replace(/\D/g, '') })} placeholder="Amount (₹)" className={input} />
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className={input}>
            {['food', 'stay', 'transport', 'activities', 'shopping', 'misc'].map((c) => <option key={c}>{c}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-500 sm:col-span-2">
            Paid by
            <select value={form.paid_by_participant_id} onChange={(e) => setForm({ ...form, paid_by_participant_id: e.target.value })} className={`${input} flex-1`}>
              {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <button disabled={busy || !people.length} className="rounded-xl bg-accent py-2.5 text-sm font-semibold text-white disabled:opacity-50 sm:col-span-2">
            Add expense (split equally)
          </button>
        </form>

        <div className={card}>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="font-bold text-slate-700">Spent so far</h3>
            <span className="text-xl font-extrabold text-primary">{inr(list.total_spend_inr)}</span>
          </div>
          {list.expenses.length === 0 ? <p className="text-sm text-slate-400">No expenses yet.</p> : (
            <ul className="divide-y">
              {list.expenses.map((x) => (
                <li key={x.id} className="flex items-center gap-3 py-2 text-sm">
                  <div className="flex-1">
                    <p className="font-medium text-slate-700">{x.description}</p>
                    <p className="text-xs text-slate-400">{x.category} · paid by {nameOf(x.paid_by_participant_id)}</p>
                  </div>
                  <span className="font-semibold">{inr(x.amount_inr)}</span>
                  <button aria-label="Delete" onClick={async () => { await companionApi.deleteExpense(tripId, x.id).catch((e) => toast.error(e.message)); load() }} className="text-slate-300 hover:text-red-500">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className={`${card} space-y-3 lg:col-span-2`}>
        <h3 className="font-bold text-slate-700">Settle up</h3>
        {settle.settlements.length === 0 ? (
          <p className="text-sm text-success">Everyone is square 🎉</p>
        ) : (
          <ul className="space-y-2">
            {settle.settlements.map((s, i) => (
              <li key={i} className="rounded-xl bg-slate-50 p-3 text-sm">
                <b>{s.from_name}</b> pays <b>{s.to_name}</b>
                <span className="float-right font-bold text-primary">{inr(s.amount_inr)}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="border-t pt-3">
          {Object.entries(settle.balances).map(([id, b]) => (
            <p key={id} className="flex justify-between py-0.5 text-xs text-slate-500">
              <span>{b.name}</span>
              <span className={b.net_balance_inr > 0 ? 'text-success' : b.net_balance_inr < 0 ? 'text-red-500' : ''}>
                {b.net_balance_inr > 0 ? 'gets back ' : b.net_balance_inr < 0 ? 'owes ' : ''}{inr(Math.abs(b.net_balance_inr))}
              </span>
            </p>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Itinerary ─────────────────────────────────────────────────────────────────

function Itinerary({ tripId }) {
  const [data, setData] = useState(null)
  const [nearby, setNearby] = useState([])

  useEffect(() => {
    companionApi.itinerary(tripId).then(setData).catch((e) => toast.error(e.message))
  }, [tripId])

  useEffect(() => {
    if (!data?.destination) return
    spotsApi.meta().then((m) => {
      const hub = m.hubs.find((h) => h.name.toLowerCase() === data.destination.toLowerCase())
      if (hub) spotsApi.list({ destination_id: hub.id, limit: 6 }).then((r) => setNearby(r.items)).catch(() => {})
    }).catch(() => {})
  }, [data?.destination])

  if (!data) return <LoadingSpinner message="Building your days…" />
  if (!data.itinerary?.length) return <p className="text-center text-sm text-slate-400">Pick a destination first (finish voting) to get an itinerary.</p>

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">{data.duration_days} days in <b>{data.destination}</b>{data.trip_month ? `, ${data.trip_month}` : ''}. A starting plan; adjust it as a group.</p>
      <div className="grid gap-4 md:grid-cols-2">
        {data.itinerary.map((d) => (
          <div key={d.day_number} className={card}>
            <h3 className="mb-2 font-bold text-primary">{d.day_label}</h3>
            <ul className="space-y-1.5">
              {d.slots.map((s, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span className="w-12 shrink-0 font-mono text-xs text-slate-400">{s.time}</span>
                  <span className="text-slate-600">{s.activity}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {nearby.length > 0 && (
        <section>
          <h3 className="mb-3 mt-2 font-bold text-slate-700">Add some local spots near {data.destination}</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{nearby.map((s) => <SpotCard key={s.id} spot={s} />)}</div>
        </section>
      )}
    </div>
  )
}

// ── Getting there ─────────────────────────────────────────────────────────────

function Travel({ tripId }) {
  const [date, setDate] = useState('')
  const [data, setData] = useState(null)

  useEffect(() => {
    setData(null)
    companionApi.travelOptions(tripId, date || undefined).then(setData).catch((e) => toast.error(e.message))
  }, [tripId, date])

  if (!data) return <LoadingSpinner message="Checking routes…" />
  const buses = data.bus_schedules?.schedules || []
  const liveBuses = buses.filter((b) => b.source !== 'stub')
  const stays = data.accommodations?.accommodations || []
  const liveStays = stays.filter((s) => s.source !== 'stub')
  const q = encodeURIComponent

  const links = [
    ['KSRTC bus booking', 'https://ksrtc.karnataka.gov.in/'],
    ['redBus', `https://www.redbus.in/`],
    ['Trains (IRCTC)', 'https://www.irctc.co.in/'],
    ['Stays on Google Maps', `https://www.google.com/maps/search/${q(`homestays in ${data.destination}`)}`],
    ['Route on Google Maps', `https://www.google.com/maps/dir/${q(data.origin)}/${q(data.destination + ', Karnataka')}`],
  ]

  return (
    <div className="space-y-4">
      <div className={`${card} flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`}>
        <p className="text-sm text-slate-600"><b>{data.origin}</b> → <b>{data.destination}</b></p>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={input} />
      </div>

      {liveBuses.length > 0 && (
        <div className={card}>
          <h3 className="mb-2 font-bold text-slate-700">Buses</h3>
          <ul className="divide-y text-sm">
            {liveBuses.map((b, i) => (
              <li key={i} className="flex flex-wrap items-center gap-3 py-2">
                <span className="flex-1 font-medium">{b.operator} <span className="text-xs text-slate-400">{b.bus_type}</span></span>
                <span>{b.departure} → {b.arrival}</span>
                <span className="font-semibold">{inr(b.fare_inr)}</span>
                {b.booking_url && <a href={b.booking_url} target="_blank" rel="noreferrer" className="text-primary underline">Book</a>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {liveStays.length > 0 && (
        <div className={card}>
          <h3 className="mb-2 font-bold text-slate-700">Places to stay</h3>
          <ul className="divide-y text-sm">
            {liveStays.map((s, i) => (
              <li key={i} className="flex justify-between py-2"><span>{s.name} <span className="text-xs text-slate-400">{s.type}</span></span><span>{inr(s.price_per_night_inr)}/night</span></li>
            ))}
          </ul>
        </div>
      )}

      {(liveBuses.length === 0 || liveStays.length === 0) && (
        <div className={`${card} space-y-3`}>
          <p className="text-sm text-slate-500">
            Live bus and stay listings aren't connected yet, so we don't show made-up timings or prices.
            Check and book here:
          </p>
          <div className="flex flex-wrap gap-2">
            {links.map(([label, href]) => (
              <a key={label} href={href} target="_blank" rel="noreferrer" className="rounded-xl bg-slate-100 px-3 py-2 text-sm font-semibold text-primary hover:bg-slate-200">{label} ↗</a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── SOS ───────────────────────────────────────────────────────────────────────

function Sos({ tripId }) {
  const [data, setData] = useState(null)
  useEffect(() => { companionApi.sos(tripId).then(setData).catch((e) => toast.error(e.message)) }, [tripId])
  if (!data) return <LoadingSpinner message="Loading emergency info…" />

  const nat = data.national_emergency || {}
  const big = [['112', 'All emergencies'], [nat.national_ambulance_disaster || '108', 'Ambulance'], [nat.police || '100', 'Police'], [nat.women_helpline || '1091', 'Women helpline']]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {big.map(([n, label]) => (
          <a key={label} href={`tel:${n}`} className="rounded-2xl bg-red-600 p-4 text-center text-white shadow-card hover:bg-red-700">
            <p className="text-2xl font-extrabold">{n}</p>
            <p className="text-xs font-semibold opacity-90">{label}</p>
          </a>
        ))}
      </div>
      {data.altitude_warning && <p className="rounded-xl bg-warning/15 p-3 text-sm text-warning">{data.altitude_warning}</p>}
      {[['Hospitals nearby', data.hospitals], ['Police stations nearby', data.police_stations]].map(([title, rows]) => rows?.length > 0 && (
        <div key={title} className={card}>
          <h3 className="mb-2 font-bold text-slate-700">{title}</h3>
          <ul className="divide-y text-sm">
            {rows.map((r, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 py-2">
                <span className="flex-1">{r.name}{r.address ? <span className="block text-xs text-slate-400">{r.address}</span> : null}</span>
                {r.phone && <a href={`tel:${r.phone}`} className="inline-flex items-center gap-1 font-semibold text-primary"><Phone className="h-3.5 w-3.5" />{r.phone}</a>}
                {r.lat && r.lon && <a href={`https://www.google.com/maps/dir/?api=1&destination=${r.lat},${r.lon}`} target="_blank" rel="noreferrer" className="text-xs text-primary underline">Directions</a>}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {data.note && <p className="text-sm text-slate-500">{data.note}</p>}
      {data.source === 'osm_overpass' && <p className="text-xs text-slate-400">Nearby places from © OpenStreetMap contributors. Call ahead to confirm.</p>}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TripCompanion() {
  const { tripId } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = TABS.some((t) => t.key === params.get('tab')) ? params.get('tab') : 'packing'
  const [dash, setDash] = useState(null)

  useEffect(() => {
    companionApi.dashboard(tripId).then(setDash).catch((e) => toast.error(e.message))
  }, [tripId])

  const people = dash?.participants || []

  return (
    <div className="space-y-5">
      <Link to={`/trip/${tripId}`} className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-primary">
        <ArrowLeft className="h-4 w-4" /> Trip dashboard
      </Link>
      <h1 className="text-2xl font-extrabold text-primary">{dash?.trip?.name || 'Your trip'}</h1>

      <div className="-mx-4 overflow-x-auto px-4">
        <div className="flex w-max gap-1 rounded-xl bg-white p-1 shadow-card">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setParams({ tab: key })}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold ${tab === key ? (key === 'sos' ? 'bg-red-600 text-white' : 'bg-primary text-white') : 'text-slate-500'}`}
            >
              <Icon className="h-4 w-4" /> {label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'packing' && <Packing tripId={tripId} people={people} />}
      {tab === 'expenses' && <Expenses tripId={tripId} people={people} />}
      {tab === 'itinerary' && <Itinerary tripId={tripId} />}
      {tab === 'travel' && <Travel tripId={tripId} />}
      {tab === 'sos' && <Sos tripId={tripId} />}
    </div>
  )
}
