import { Crosshair, Gift, Lock, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'
import EmptyState from '../components/common/EmptyState'
import LoadingSpinner from '../components/common/LoadingSpinner'
import SpotCard from '../components/spots/SpotCard'
import SpotMap from '../components/spots/SpotMap'
import { authApi, catName, CATEGORY_META, spotsApi } from '../services/spotsService'
import useAuthStore from '../store/authStore'
import { useT } from '../i18n'

const VISIBILITY = ['all', 'hidden', 'public']

export default function Explore() {
  const { token, user, setUser } = useAuthStore()
  const t = useT()
  const [meta, setMeta] = useState(null)
  const [data, setData] = useState({ total: 0, items: [] })
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [district, setDistrict] = useState('')
  const [visibility, setVisibility] = useState('all')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [near, setNear] = useState(null) // [lat, lng]
  const [focus, setFocus] = useState(null)

  useEffect(() => {
    spotsApi.meta().then(setMeta).catch((e) => toast.error(e.message))
    if (token) authApi.me().then(setUser).catch(() => {})
  }, [token, setUser])

  const params = useMemo(() => {
    const p = { limit: 500 }
    if (category) p.category = category
    if (district) p.district = district
    if (visibility === 'hidden') p.hidden = true
    if (visibility === 'public') p.hidden = false
    if (query) p.q = query
    if (near) Object.assign(p, { lat: near[0], lng: near[1], radius_km: 60 })
    return p
  }, [category, district, visibility, query, near])

  useEffect(() => {
    setLoading(true)
    spotsApi
      .list(params)
      .then(setData)
      .catch((e) => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [params, token])

  function locateMe() {
    if (!navigator.geolocation) return toast.error('Location is not available in this browser')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const c = [pos.coords.latitude, pos.coords.longitude]
        setNear(c)
        setFocus({ center: c, zoom: 9 })
      },
      () => toast.error('Could not get your location'),
      { timeout: 10000 },
    )
  }

  function chooseDistrict(d) {
    setDistrict(d)
    const hub = meta?.hubs?.find((h) => h.district === d)
    setFocus(hub ? { center: [hub.latitude, hub.longitude], zoom: 9 } : { center: [14.6, 76.1], zoom: 7 })
  }

  const credits = user?.unlock_credits

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-3xl bg-gradient-to-br from-primary to-[#2f5d8a] p-6 text-white shadow-card sm:p-8">
        <p className="text-sm font-semibold uppercase tracking-wider text-white/70">{t('explore.kicker')}</p>
        <h1 className="mt-1 text-3xl font-extrabold sm:text-4xl">{t('explore.title')}</h1>
        <p className="mt-2 max-w-2xl text-white/80">
          {t('explore.body', { hidden: meta?.hidden_count ? t('explore.hiddenN', { n: meta.hidden_count }) : t('explore.hidden') })}
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Link
            to="/spots/share"
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 font-semibold text-white hover:opacity-90"
          >
            <Gift className="h-4 w-4" /> {t('explore.shareCta')}
          </Link>
          {token ? (
            <span className="inline-flex items-center gap-1.5 rounded-xl bg-white/15 px-4 py-2.5 text-sm font-semibold">
              <Lock className="h-4 w-4" /> {t('explore.credits', { n: credits ?? '…' })}
            </span>
          ) : (
            <Link to="/login?next=/explore" className="text-sm font-semibold underline underline-offset-4">
              {t('explore.signup')}
            </Link>
          )}
        </div>
      </section>

      {/* Filters */}
      <section className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setCategory('')}
            className={`rounded-full px-3 py-1.5 text-sm font-medium ${category === '' ? 'bg-primary text-white' : 'bg-white text-slate-600 shadow-card'}`}
          >
            {t('explore.all')}
          </button>
          {(meta?.categories || Object.keys(CATEGORY_META)).map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c === category ? '' : c)}
              className={`rounded-full px-3 py-1.5 text-sm font-medium ${category === c ? 'bg-primary text-white' : 'bg-white text-slate-600 shadow-card'}`}
            >
              {CATEGORY_META[c]?.emoji} {catName(c)}
              {meta?.counts?.[c] ? <span className="ml-1 opacity-60">{meta.counts[c]}</span> : null}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <form
            className="relative flex-1"
            onSubmit={(e) => {
              e.preventDefault()
              setQuery(q.trim())
            }}
          >
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onBlur={() => setQuery(q.trim())}
              placeholder={t('explore.search')}
              className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm focus:border-primary focus:outline-none"
            />
          </form>
          <select
            value={district}
            onChange={(e) => chooseDistrict(e.target.value)}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm"
          >
            <option value="">{t('explore.allDistricts')}</option>
            {meta?.districts?.map((d) => <option key={d}>{d}</option>)}
          </select>
          <div className="flex rounded-xl bg-white p-1 shadow-card">
            {VISIBILITY.map((v) => (
              <button
                key={v}
                onClick={() => setVisibility(v)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${visibility === v ? 'bg-primary text-white' : 'text-slate-600'}`}
              >
                {t(`explore.vis.${v}`)}
              </button>
            ))}
          </div>
          <button
            onClick={() => (near ? setNear(null) : locateMe())}
            className={`inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-sm font-medium shadow-card ${near ? 'bg-primary text-white' : 'bg-white text-slate-600'}`}
          >
            <Crosshair className="h-4 w-4" /> {near ? `${t('explore.near')} ✕` : t('explore.near')}
          </button>
        </div>
      </section>

      <SpotMap spots={data.items} hubs={meta?.hubs || []} focus={focus} />

      {/* Results */}
      <section>
        <p className="mb-3 text-sm text-slate-500">
          {loading ? '…' : `${t('explore.count', { n: data.total })}${near ? ` ${t('explore.within')}` : ''}`}
        </p>
        {loading ? (
          <LoadingSpinner message={t('explore.loading')} />
        ) : data.items.length === 0 ? (
          <EmptyState
            emoji="🗺️"
            title={t('explore.emptyTitle')}
            message={t('explore.emptyBody')}
            action={{ label: t('nav.share'), href: '/spots/share' }}
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map((s) => <SpotCard key={s.id} spot={s} />)}
          </div>
        )}
      </section>
    </div>
  )
}
