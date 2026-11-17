import { Camera, CheckCircle2, ImagePlus, MapPin, Stamp, X } from 'lucide-react'
import { useState } from 'react'
import toast from 'react-hot-toast'
import { resizeImage, spotsApi } from '../../services/spotsService'
import { readExif } from '../../utils/exif'
import { PassportStamp } from './TravelBadges'

const today = () => new Date().toISOString().slice(0, 10)

/**
 * "Stamp your passport": optional visit date + a photo from the trip.
 * The photo's EXIF date fills in the visit date; its GPS (if any) is sent
 * once so the server can decide whether it's a VERIFIED stamp.
 */
export default function StampDialog({ placeName, onClose, onStamp }) {
  const [visitedOn, setVisitedOn] = useState(today())
  const [photo, setPhoto] = useState(null) // { url, preview, lat, lng }
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  async function pick(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    try {
      const exif = await readExif(file)
      if (exif.takenOn && exif.takenOn <= today()) setVisitedOn(exif.takenOn)
      const blob = await resizeImage(file, 1600, 0.82)
      const r = await spotsApi.uploadPhoto(blob)
      setPhoto({ url: r.url, preview: URL.createObjectURL(blob), lat: exif.lat, lng: exif.lng })
      setNote(
        exif.lat != null
          ? 'Photo has a location: if it was taken here, you get a gold VERIFIED stamp.'
          : exif.takenOn
            ? 'Got the date from your photo.'
            : 'No date or location in this photo (some apps remove it). That\'s fine!',
      )
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function submit(extras) {
    setBusy(true)
    try {
      await onStamp(extras)
      onClose()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-slate-900/60 sm:items-center sm:p-4" onClick={onClose}>
      <div
        className="w-full max-w-md overflow-hidden rounded-t-3xl bg-[#fbf7ef] shadow-2xl sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative bg-primary px-5 pb-5 pt-4 text-white">
          <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-amber-300/80">Karnataka passport</p>
          <h3 className="mt-1 flex items-center gap-2 text-xl font-black"><Stamp className="h-5 w-5" /> Stamp it</h3>
          <p className="mt-0.5 truncate text-sm text-white/75">{placeName}</p>
          <button onClick={onClose} className="absolute right-3 top-3 rounded-full p-1.5 hover:bg-white/10" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
          <PassportStamp size="md" tone="light" date={visitedOn} className="absolute right-12 top-6" />
        </div>

        <div className="space-y-4 p-5">
          <label className="block space-y-1">
            <span className="text-sm font-semibold text-slate-600">When did you go?</span>
            <input
              type="date" value={visitedOn} max={today()} min="1950-01-01"
              onChange={(e) => setVisitedOn(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-slate-800 outline-none focus:border-primary"
            />
          </label>

          <div className="space-y-1">
            <span className="text-sm font-semibold text-slate-600">A photo from your trip <span className="font-normal text-slate-400">(optional)</span></span>
            {photo ? (
              <div className="relative">
                <img src={photo.preview} alt="" className="h-44 w-full rounded-xl object-cover" />
                <button
                  onClick={() => { setPhoto(null); setNote('') }}
                  className="absolute right-2 top-2 rounded-full bg-black/60 p-1 text-white" aria-label="Remove photo"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <label className="flex h-28 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-slate-300 bg-white text-sm text-slate-500 hover:border-primary hover:text-primary">
                {busy ? 'Uploading…' : <><ImagePlus className="h-6 w-6" /> Add a photo you took there</>}
                <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={pick} disabled={busy} />
              </label>
            )}
            {note && (
              <p className="flex items-start gap-1.5 pt-1 text-xs text-slate-500">
                {photo?.lat != null ? <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" /> : <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />}
                {note}
              </p>
            )}
            <p className="pt-1 text-[11px] text-slate-400">
              <Camera className="mr-1 inline h-3 w-3" />
              Your photo shows on your public passport. Its location is only used to check the stamp and is never saved.
            </p>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              disabled={busy}
              onClick={() => submit({})}
              className="rounded-xl px-4 py-3 text-sm font-semibold text-slate-500 hover:bg-slate-100 disabled:opacity-50"
            >
              Just stamp
            </button>
            <button
              disabled={busy}
              onClick={() => submit({
                visited_on: visitedOn || undefined,
                photo_url: photo?.url,
                photo_lat: photo?.lat ?? undefined,
                photo_lng: photo?.lng ?? undefined,
              })}
              className="flex-1 rounded-xl bg-orange-700 py-3 font-black uppercase tracking-wide text-white hover:bg-orange-800 disabled:opacity-50"
            >
              {busy ? 'Stamping…' : 'Stamp my passport'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
