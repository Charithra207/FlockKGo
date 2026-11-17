import { Camera, Crosshair, Gift, MapPin, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import LoadingSpinner from '../components/common/LoadingSpinner'
import SpotMap from '../components/spots/SpotMap'
import { catName, CATEGORY_META, monthNames, photoSrc, resizeImage, SAFETY_META, spotsApi } from '../services/spotsService'
import Turnstile, { Honeypot } from '../components/auth/Turnstile'
import useAuthStore from '../store/authStore'
import { useT } from '../i18n'

const empty = {
  name: '', category: 'viewpoint', district: '', description: '', access_notes: '',
  best_months: [], permit_required: false, is_hidden: true, photo_url: '', tags: '', safety: [],
}

/** Share a new spot, or edit one (/spots/:spotId/edit). */
export default function ShareSpot() {
  const { spotId } = useParams()
  const editing = Boolean(spotId)
  const navigate = useNavigate()
  const { token } = useAuthStore()
  const t = useT()
  // ?district=Kodagu&lat=..&lng=.. (from a trip: "share a spot you found there")
  const [params] = useSearchParams()
  const [form, setForm] = useState(() => ({ ...empty, district: params.get('district') || '' }))
  const [pin, setPin] = useState(null)
  const [focus, setFocus] = useState(() => {
    const la = Number(params.get('lat'))
    const ln = Number(params.get('lng'))
    return la && ln ? { center: [la, ln], zoom: 11 } : null
  })
  const [districts, setDistricts] = useState([])
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [loaded, setLoaded] = useState(!editing)
  const [captcha, setCaptcha] = useState(null)
  const [website, setWebsite] = useState('')

  useEffect(() => {
    spotsApi.meta().then((m) => setDistricts(m.districts)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!editing || !token) return
    spotsApi.get(spotId).then((s) => {
      if (s.locked) throw new Error("You can't edit this spot")
      setForm({
        name: s.name, category: s.category, district: s.district, description: s.description || '',
        access_notes: s.access_notes || '', best_months: s.best_months || [], permit_required: s.permit_required,
        is_hidden: s.is_hidden, photo_url: s.photo_url || '', tags: (s.tags || []).join(', '), safety: s.safety || [],
      })
      setPin([s.latitude, s.longitude])
      setFocus({ center: [s.latitude, s.longitude], zoom: 13 })
      setLoaded(true)
    }).catch((e) => { toast.error(e.message); navigate(-1) })
  }, [editing, spotId, token, navigate])

  if (!token) {
    return (
      <div className="mx-auto max-w-lg rounded-3xl bg-white p-8 text-center shadow-card">
        <Gift className="mx-auto h-10 w-10 text-accent" />
        <h1 className="mt-3 text-2xl font-extrabold text-primary">{t('share.gateTitle')}</h1>
        <p className="mt-2 text-slate-500">{t('share.gateBody')}</p>
        <Link to="/login?next=/spots/share" className="mt-5 inline-block rounded-xl bg-accent px-6 py-3 font-semibold text-white hover:opacity-90">
          {t('share.gateCta')}
        </Link>
      </div>
    )
  }
  if (!loaded) return <LoadingSpinner message="Loading spot…" />

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

  async function onPhoto(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) return toast.error('Please pick an image')
    setUploading(true)
    try {
      const blob = await resizeImage(file)
      const r = await spotsApi.uploadPhoto(blob)
      setForm((f) => ({ ...f, photo_url: r.url }))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setUploading(false)
    }
  }

  async function submit(e) {
    e.preventDefault()
    if (!pin) return toast.error('Drop a pin on the map first')
    if (!form.district) return toast.error('Pick a district')
    setSaving(true)
    const body = {
      ...form,
      latitude: pin[0],
      longitude: pin[1],
      description: form.description || null,
      access_notes: form.access_notes || null,
      photo_url: form.photo_url.trim() || (editing ? '' : null),
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      captcha_token: captcha || undefined,
      website: website || undefined,
    }
    try {
      if (editing) {
        await spotsApi.edit(spotId, body)
        toast.success('Saved')
        navigate(`/spots/${spotId}`)
      } else {
        const r = await spotsApi.submit(body)
        toast.success(r.message)
        navigate('/me')
      }
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
        <h1 className="text-3xl font-extrabold text-primary">{editing ? t('share.editTitle') : t('share.title')}</h1>
        {!editing && (
          <p className="mt-1 text-slate-500">{t('share.intro', { n: reward })}</p>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-slate-700">
              <MapPin className="h-4 w-4 text-accent" /> {t('share.pin')}
            </p>
            <button type="button" onClick={locateMe} className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-primary shadow-card">
              <Crosshair className="h-3.5 w-3.5" /> {t('share.here')}
            </button>
          </div>
          <SpotMap pick={pin} onPick={setPin} focus={focus} height={420} />
          {pin && <p className="text-xs text-slate-400">{pin[0]}, {pin[1]}</p>}
        </div>

        <div className="space-y-4 rounded-2xl bg-white p-5 shadow-card">
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">{t('share.name')} *</span>
            <input required minLength={2} maxLength={200} value={form.name} onChange={set('name')} className={input} placeholder="e.g. Sunrise rock behind the coffee estate" />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">{t('share.type')} *</span>
              <select value={form.category} onChange={set('category')} className={input}>
                {Object.entries(CATEGORY_META).map(([k, m]) => <option key={k} value={k}>{m.emoji} {catName(k)}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">{t('share.district')} *</span>
              <select required value={form.district} onChange={set('district')} className={input}>
                <option value="">{t('share.choose')}</option>
                {districts.map((d) => <option key={d}>{d}</option>)}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="text-sm font-semibold text-slate-700">{t('share.special')}</span>
            <textarea rows={3} maxLength={3000} value={form.description} onChange={set('description')} className={input} placeholder="The view, the vibe, what to order…" />
          </label>

          <label className="block">
            <span className="text-sm font-semibold text-slate-700">{t('share.access')}</span>
            <textarea rows={2} maxLength={2000} value={form.access_notes} onChange={set('access_notes')} className={input} placeholder="Park near…, 20 min walk, road is rough after rain…" />
          </label>

          <div>
            <span className="text-sm font-semibold text-slate-700">{t('share.months')}</span>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {monthNames().map((m, i) => (
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

          <div>
            <span className="text-sm font-semibold text-slate-700">{t('share.photo')}</span>
            {form.photo_url ? (
              <div className="relative mt-1.5">
                <img src={photoSrc(form.photo_url)} alt="" className="max-h-56 w-full rounded-xl object-cover" />
                <button type="button" aria-label="Remove photo" onClick={() => setForm((f) => ({ ...f, photo_url: '' }))} className="absolute right-2 top-2 rounded-full bg-black/60 p-1 text-white">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <label className="mt-1.5 flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-200 py-6 text-sm font-semibold text-slate-500 hover:border-primary hover:text-primary">
                <Camera className="h-5 w-5" /> {uploading ? '…' : t('share.addPhoto')}
                <input type="file" accept="image/*" className="hidden" disabled={uploading} onChange={onPhoto} />
              </label>
            )}
          </div>

          <label className="block">
            <span className="text-sm font-semibold text-slate-700">{t('share.tags')}</span>
            <input value={form.tags} onChange={set('tags')} className={input} placeholder="monsoon, sunrise, bike-friendly" />
          </label>

          <div className="space-y-2 rounded-xl bg-slate-50 p-3">
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={form.is_hidden} onChange={set('is_hidden')} className="mt-0.5" />
              <span>{t('share.hidden')}</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={form.permit_required} onChange={set('permit_required')} className="mt-0.5" />
              <span>{t('share.permit')}</span>
            </label>
          </div>

          <div className="space-y-2">
            <span className="text-sm font-semibold text-slate-700">Safety notes <span className="font-normal text-slate-400">(tick all that apply)</span></span>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(SAFETY_META).map(([k, m]) => {
                const on = form.safety.includes(k)
                return (
                  <button
                    key={k} type="button" title={m.tip}
                    onClick={() => setForm((f) => ({ ...f, safety: on ? f.safety.filter((x) => x !== k) : [...f.safety, k] }))}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold ${on ? 'border-amber-500 bg-amber-100 text-amber-800' : 'border-slate-200 text-slate-500'}`}
                  >
                    {m.emoji} {m.label}
                  </button>
                )
              })}
            </div>
          </div>
          <Honeypot value={website} onChange={setWebsite} />
          {!editing && <Turnstile onToken={setCaptcha} />}

          <p className="text-xs text-slate-400">
            {t('share.rules')}
          </p>

          <button disabled={saving || uploading} className="w-full rounded-xl bg-accent py-3 font-semibold text-white hover:opacity-90 disabled:opacity-50">
            {saving ? '…' : editing ? t('share.save') : t('share.submit')}
          </button>
        </div>
      </div>
    </form>
  )
}
