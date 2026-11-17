import { ImagePlus, Star, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, useLocation } from 'react-router-dom'
import api from '../../services/api'
import { photoSrc, resizeImage, spotsApi } from '../../services/spotsService'
import useAuthStore from '../../store/authStore'
import Avatar from '../profile/Avatar'

function Stars({ value, onChange, size = 'h-5 w-5' }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n} type="button" disabled={!onChange} onClick={() => onChange?.(n)}
          aria-label={`${n} star${n === 1 ? '' : 's'}`} className={onChange ? 'cursor-pointer' : 'cursor-default'}
        >
          <Star className={`${size} ${n <= value ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`} />
        </button>
      ))}
    </div>
  )
}

function ReviewForm({ spotId, existing, onSaved }) {
  const [rating, setRating] = useState(existing?.rating || 0)
  const [text, setText] = useState(existing?.text || '')
  const [photos, setPhotos] = useState(existing?.photos || [])
  const [month, setMonth] = useState(existing?.visited_month || '')
  const [busy, setBusy] = useState(false)

  async function addPhoto(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || photos.length >= 4) return
    setBusy(true)
    try {
      const r = await spotsApi.uploadPhoto(await resizeImage(file))
      setPhotos((p) => [...p, r.url])
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function save() {
    if (!rating) return toast.error('Tap the stars to rate it')
    setBusy(true)
    try {
      await api.put(`/spots/${spotId}/reviews`, { rating, text: text || undefined, photos, visited_month: month || undefined })
      toast.success('Thanks for the review!')
      onSaved()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <Stars value={rating} onChange={setRating} size="h-7 w-7" />
        <label className="text-sm text-slate-500">
          Went in{' '}
          <input type="month" value={month} max={new Date().toISOString().slice(0, 7)} onChange={(e) => setMonth(e.target.value)} className="rounded-lg border border-slate-200 px-2 py-1 text-sm" />
        </label>
      </div>
      <textarea
        value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} rows={3}
        placeholder="What was it like? Best time, how to get there, what to carry…"
        className="w-full rounded-xl border border-slate-200 p-3 text-sm focus:border-primary focus:outline-none"
      />
      <div className="flex flex-wrap gap-2">
        {photos.map((p) => (
          <div key={p} className="relative">
            <img src={photoSrc(p)} alt="" className="h-20 w-20 rounded-lg object-cover" />
            <button onClick={() => setPhotos((xs) => xs.filter((x) => x !== p))} className="absolute -right-1 -top-1 rounded-full bg-black/70 p-0.5 text-white" aria-label="Remove photo">
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
        {photos.length < 4 && (
          <label className="flex h-20 w-20 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 text-[10px] text-slate-500 hover:border-primary">
            <ImagePlus className="h-5 w-5" /> Photo
            <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={addPhoto} disabled={busy} />
          </label>
        )}
      </div>
      <button disabled={busy} onClick={save} className="rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">
        {busy ? '…' : existing ? 'Update review' : 'Post review'}
      </button>
    </div>
  )
}

export default function Reviews({ spot }) {
  const { token } = useAuthStore()
  const location = useLocation()
  const [data, setData] = useState(null)
  const [writing, setWriting] = useState(false)
  const load = () => api.get(`/spots/${spot.id}/reviews`).then((r) => setData(r.data)).catch(() => setData(null))
  useEffect(() => { load() }, [spot.id, token]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!data) return null
  const mine = data.items.find((r) => r.mine)

  return (
    <section className="space-y-4 rounded-2xl bg-white p-6 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-bold text-slate-700">
          Reviews
          {data.average && (
            <span className="inline-flex items-center gap-1 text-base text-amber-600">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" /> {data.average} <span className="text-sm text-slate-400">({data.count})</span>
            </span>
          )}
        </h2>
        {!spot.is_mine && (token ? (
          <button onClick={() => setWriting((w) => !w)} className="text-sm font-semibold text-primary">
            {writing ? 'Cancel' : mine ? 'Edit your review' : 'Write a review'}
          </button>
        ) : (
          <Link to={`/login?next=${encodeURIComponent(location.pathname)}`} className="text-sm font-semibold text-primary">Log in to review</Link>
        ))}
      </div>
      {writing && <ReviewForm spotId={spot.id} existing={mine} onSaved={() => { setWriting(false); load() }} />}
      {data.items.length === 0 && !writing && <p className="text-sm text-slate-500">No reviews yet. Been here? Be the first.</p>}
      <div className="space-y-4">
        {data.items.map((r) => (
          <article key={r.id} className="space-y-2 border-t pt-4 first:border-0 first:pt-0">
            <div className="flex items-center gap-2">
              <Link to={`/u/${r.author.username}`}><Avatar user={r.author} size={32} /></Link>
              <div className="min-w-0 flex-1">
                <Link to={`/u/${r.author.username}`} className="text-sm font-semibold text-slate-700">{r.author.display_name}</Link>
                <div className="flex items-center gap-2"><Stars value={r.rating} size="h-3.5 w-3.5" />{r.visited_month && <span className="text-xs text-slate-400">went {r.visited_month}</span>}</div>
              </div>
              {r.mine && (
                <button onClick={async () => { await api.delete(`/spots/${spot.id}/reviews`); load() }} className="text-slate-300 hover:text-red-500" aria-label="Delete my review">
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
            {r.text && <p className="whitespace-pre-line text-sm text-slate-600">{r.text}</p>}
            {r.photos.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {r.photos.map((p) => (
                  <a key={p} href={photoSrc(p)} target="_blank" rel="noreferrer">
                    <img src={photoSrc(p)} alt="" loading="lazy" className="h-24 w-24 rounded-lg object-cover" />
                  </a>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
