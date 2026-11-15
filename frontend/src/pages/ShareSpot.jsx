import { Crosshair, Gift, MapPin } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useNavigate } from 'react-router-dom'
import SpotMap from '../components/spots/SpotMap'
import { CATEGORY_META, MONTHS, spotsApi } from '../services/spotsService'
import useAuthStore from '../store/authStore'

const empty = {
  name: '', category: 'viewpoint', district: '', description: '', access_notes: '',
  best_months: [], permit_required: false, is_hidden: true, photo_url: '', tags: '',
}

export default function ShareSpot() {
  const navigate = useNavigate()
  const { token } = useAuthStore()
  const [form, setForm] = useState(empty)
  const [pin, setPin] = useState(null)
  const [focus, setFocus] = useState(null)
  const [districts, setDistricts] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    spotsApi.meta().then((m) => setDistricts(m.districts)).catch(() => {})
  }, [])

  if (!token) {
    return (
      <div className="mx-auto max-w-lg rounded-3xl bg-white p-8 text-center shadow-card">
        <Gift className="mx-auto h-10 w-10 text-accent" />
        <h1 className="mt-3 text-2xl font-extrabold text-primary">Give a spot, get a spot</h1>
        <p className="mt-2 text-slate-500">
          Share a hidden place you've been to. When it's approved you earn <b>3 unlocks</b> to discover
          other people's secret spots.
        </p>
        <Link to="/login?next=/spots/share" className="mt-5 inline-block rounded-xl bg-accent px-6 py-3 font-semibold text-white hover:opacity-90">
          Log in or sign up
        </Link>
      </div>
    )
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))
  const toggleMonth = (m) =>
    setForm((f) => ({ ...f, best_months: f.best_months.includes(m) ? f.best_months.filter((x) => x !== m) : [...f.best_months, m] }))

  function locateMe() {
    navigator.geolocation?.getCurrentPosition(
      (p) => {
        const c = [Number(p.coords.latitude.toFixed(6)), Number(p.coords.longitude.toFixed(6))]
        setPin(c)
        setFocus({ center: c, zoom: 14 })
      },
      () => toast.error('Could not get your location'),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  async function submit(e) {
    e.preventDefault()
    if (!pin) return toast.error('Drop a pin on the map first')
    if (!form.district) return toast.error('Pick a district')
    setSaving(true)
    try {
      const r = await spotsApi.submit({
        ...form,
        latitude: pin[0],
        longitude: pin[1],
        description: form.description || null,
        access_notes: form.access_notes || null,
        photo_url: form.photo_url.trim() || null,
        tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      })
      toast.success(r.message)
      navigate('/me')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const input = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm focus:border-primary focus:outline-none'
  const reward = form.is_hidden ? 3 : 1

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold text-primary">Share a spot</h1>
        <p className="mt-1 text-slate-500">
          Only places you've personally been to, please. Once it's approved you earn <b>{reward} unlock{reward > 1 ? 's' : ''}</b>.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-slate-700">
              <MapPin className="h-4 w-4 text-accent" /> Tap the map to drop the exact pin
            </p>
            <button type="button" onClick={locateMe} className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-primary shadow-card">
              <Crosshair className="h-3.5 w-3.5" /> I'm here now
            </button>
          </div>
          <SpotMap pick={pin} onPick={setPin} focus={focus} height={420} />
          {pin && <p className="text-xs text-slate-400">{pin[0]}, {pin[1]}</p>}
        </div>

        <div className="space-y-4 rounded-2xl bg-white p-5 shadow-card">
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">Name *</span>
            <input required minLength={2} maxLength={200} value={form.name} onChange={set('name')} className={input} placeholder="e.g. Sunrise rock behind the coffee estate" />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">Type *</span>
              <select value={form.category} onChange={set('category')} className={input}>
                {Object.entries(CATEGORY_META).map(([k, m]) => <option key={k} value={k}>{m.emoji} {m.label}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">District *</span>
              <select required value={form.district} onChange={set('district')} className={input}>
                <option value="">Choose…</option>
                {districts.map((d) => <option key={d}>{d}</option>)}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="text-sm font-semibold text-slate-700">What makes it special?</span>
            <textarea rows={3} maxLength={3000} value={form.description} onChange={set('description')} className={input} placeholder="The view, the vibe, what to order…" />
          </label>

          <label className="block">
            <span className="text-sm font-semibold text-slate-700">How to get there</span>
            <textarea rows={2} maxLength={2000} value={form.access_notes} onChange={set('access_notes')} className={input} placeholder="Park near…, 20 min walk, road is rough after rain…" />
          </label>

          <div>
            <span className="text-sm font-semibold text-slate-700">Best months</span>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {MONTHS.map((m, i) => (
                <button
                  type="button"
                  key={m}
                  onClick={() => toggleMonth(i + 1)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${form.best_months.includes(i + 1) ? 'bg-success text-white' : 'bg-slate-100 text-slate-500'}`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          <label className="block">
            <span className="text-sm font-semibold text-slate-700">Photo link (optional)</span>
            <input type="url" value={form.photo_url} onChange={set('photo_url')} className={input} placeholder="https://… (your own photo)" />
          </label>

          <label className="block">
            <span className="text-sm font-semibold text-slate-700">Tags</span>
            <input value={form.tags} onChange={set('tags')} className={input} placeholder="monsoon, sunrise, bike-friendly" />
          </label>

          <div className="space-y-2 rounded-xl bg-slate-50 p-3">
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={form.is_hidden} onChange={set('is_hidden')} className="mt-0.5" />
              <span><b>Hidden gem</b>: only people who unlock it see where it is (earns 3 unlocks)</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={form.permit_required} onChange={set('permit_required')} className="mt-0.5" />
              <span>Needs a forest / entry permit</span>
            </label>
          </div>

          <p className="text-xs text-slate-400">
            Don't share private property without permission or places that are unsafe or closed to visitors.
            Use your own photos.
          </p>

          <button disabled={saving} className="w-full rounded-xl bg-accent py-3 font-semibold text-white hover:opacity-90 disabled:opacity-50">
            {saving ? 'Sending…' : 'Submit for review'}
          </button>
        </div>
      </div>
    </form>
  )
}
