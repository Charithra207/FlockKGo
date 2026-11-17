import { Copy, Flag, KeyRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'
import api from '../../services/api'
import { accountApi } from '../../services/authConfig'
import { categoryLabel } from '../../services/spotsService'

const LABEL = {
  closed: 'Closed', wrong_location: 'Wrong place', unsafe: 'Unsafe', private_property: 'Private land',
  crowded: 'Too crowded', spam: 'Spam', other: 'Other',
}

export function ReportsQueue() {
  const [items, setItems] = useState(null)
  const load = () => api.get('/admin/reports').then((r) => setItems(r.data.items)).catch((e) => toast.error(e.message))
  useEffect(() => { load() }, [])
  async function resolve(id, action) {
    try {
      await api.post(`/admin/reports/${id}/resolve`, { action })
      toast.success('Done')
      load()
    } catch (e) {
      toast.error(e.message)
    }
  }
  if (!items) return null
  return (
    <section className="space-y-3">
      <h2 className="flex items-center gap-2 text-xl font-extrabold text-primary"><Flag className="h-5 w-5" /> Reports ({items.length})</h2>
      {items.length === 0 && <p className="text-sm text-slate-500">No open reports.</p>}
      {items.map(({ spot, reasons, notes, total }) => (
        <div key={spot.id} className="space-y-2 rounded-2xl bg-white p-5 shadow-card">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/spots/${spot.id}`} className="font-bold text-slate-800 underline">{spot.name}</Link>
            <span className="text-sm text-slate-500">{categoryLabel(spot.category)} · {spot.district}</span>
            {spot.status === 'flagged' && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-600">Hidden until you decide</span>}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(reasons).map(([k, n]) => (
              <span key={k} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">{LABEL[k] || k} ×{n}</span>
            ))}
            <span className="text-xs text-slate-400">{total} report{total === 1 ? '' : 's'}</span>
          </div>
          {notes.length > 0 && <ul className="space-y-1 text-sm text-slate-600">{notes.map((n, i) => <li key={i}>“{n}”</li>)}</ul>}
          <div className="flex flex-wrap gap-2 pt-1">
            <button onClick={() => resolve(spot.id, 'dismiss')} className="rounded-xl bg-slate-100 px-3 py-1.5 text-sm font-semibold">Reports are wrong: keep it</button>
            <button onClick={() => resolve(spot.id, 'make_hidden')} className="rounded-xl bg-amber-100 px-3 py-1.5 text-sm font-semibold text-amber-800">Make it a hidden gem</button>
            <button onClick={() => resolve(spot.id, 'unpublish')} className="rounded-xl bg-red-100 px-3 py-1.5 text-sm font-semibold text-red-700">Remove it</button>
          </div>
        </div>
      ))}
    </section>
  )
}

export function ResetLinkTool() {
  const [email, setEmail] = useState('')
  const [link, setLink] = useState('')
  async function make(e) {
    e.preventDefault()
    try {
      setLink((await accountApi.adminResetLink(email)).link)
    } catch (err) {
      toast.error(err.message)
    }
  }
  return (
    <section className="space-y-2 rounded-2xl bg-white p-5 shadow-card">
      <h2 className="flex items-center gap-2 text-lg font-extrabold text-primary"><KeyRound className="h-5 w-5" /> Password reset link</h2>
      <p className="text-sm text-slate-500">Someone locked out and email isn't set up? Make a 1-hour reset link and send it to them yourself.</p>
      <form onSubmit={make} className="flex flex-wrap gap-2">
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="their@email.com"
          className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm" />
        <button className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white">Make link</button>
      </form>
      {link && (
        <button onClick={() => navigator.clipboard?.writeText(link).then(() => toast.success('Copied'))}
          className="flex w-full items-center gap-2 break-all rounded-xl bg-slate-50 p-3 text-left text-xs text-slate-600">
          <Copy className="h-4 w-4 shrink-0" /> {link}
        </button>
      )}
    </section>
  )
}
