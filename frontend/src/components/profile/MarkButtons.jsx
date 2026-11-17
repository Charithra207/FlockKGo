import { Plane, Stamp } from 'lucide-react'
import { useState } from 'react'
import toast from 'react-hot-toast'
import { useLocation, useNavigate } from 'react-router-dom'
import { profileApi } from '../../services/profileService'
import StampDialog from './StampDialog'
import useAuthStore from '../../store/authStore'
import { useT } from '../../i18n'

/**
 * "Stamp my passport" (been) / "Bucket list" (want) toggles.
 * Pass spotId or destinationId, the current value and an onChange(newValue).
 * compact = icon-only round buttons (for cards).
 */
export function useMark({ spotId, destinationId, value, onChange }) {
  const { token } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [busy, setBusy] = useState(false)
  const [dialog, setDialog] = useState(false)

  async function save(next, extras = {}) {
    setBusy(true)
    onChange?.(next) // optimistic
    try {
      const r = await profileApi.mark({
        spot_id: spotId || undefined,
        destination_id: destinationId || undefined,
        status: next,
        ...extras,
      })
      onChange?.(next, r)
      if (next === 'been') toast.success(r.photo_verified ? 'Verified stamp! 📸 Photo taken right here' : 'Stamped! Added to your passport', { icon: '🛂' })
      else if (next === 'want') toast.success('Added to your bucket list', { icon: '✈️' })
    } catch (e) {
      onChange?.(value) // roll back
      toast.error(e.message)
      throw e
    } finally {
      setBusy(false)
    }
  }

  function toggle(kind) {
    if (!token) {
      navigate(`/login?next=${encodeURIComponent(location.pathname)}`)
      return
    }
    if (kind === 'been' && value !== 'been') {
      setDialog(true) // date + photo first
      return
    }
    save(value === kind ? null : kind).catch(() => {})
  }
  return { toggle, busy, dialog, closeDialog: () => setDialog(false), stamp: (extras) => save('been', extras) }
}

export default function MarkButtons({ spotId, destinationId, value, onChange, compact = false, placeName = '' }) {
  const t = useT()
  const { toggle, busy, dialog, closeDialog, stamp } = useMark({ spotId, destinationId, value, onChange })
  const stampDialog = dialog && <StampDialog placeName={placeName} onClose={closeDialog} onStamp={stamp} />
  const been = value === 'been'
  const want = value === 'want'

  if (compact) {
    const base = 'grid h-8 w-8 place-items-center rounded-full shadow-md ring-1 transition-transform hover:scale-110 disabled:opacity-60'
    return (
      <div className="flex gap-1.5">
        {stampDialog}
        <button
          type="button" disabled={busy} onClick={() => toggle('been')}
          title={been ? t('mark.unstamp') : t('mark.stamp')} aria-pressed={been}
          className={`${base} ${been ? 'bg-orange-700 text-white ring-orange-800' : 'bg-white/95 text-orange-700 ring-slate-200'}`}
        >
          <Stamp className="h-4 w-4" />
        </button>
        <button
          type="button" disabled={busy} onClick={() => toggle('want')}
          title={want ? t('mark.unwant') : t('mark.want')} aria-pressed={want}
          className={`${base} ${want ? 'bg-primary text-amber-300 ring-primary' : 'bg-white/95 text-primary ring-slate-200'}`}
        >
          <Plane className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {stampDialog}
      <button
        type="button" disabled={busy} onClick={() => toggle('been')} aria-pressed={been}
        className={`inline-flex items-center gap-2 rounded-xl border-2 px-4 py-2 text-sm font-bold uppercase tracking-wide transition disabled:opacity-60 ${
          been ? 'border-orange-700 bg-orange-700 text-white' : 'border-dashed border-orange-700/60 text-orange-700 hover:bg-orange-50'
        }`}
      >
        <Stamp className="h-4 w-4" /> {been ? t('mark.stamped') : t('mark.stamp')}
      </button>
      <button
        type="button" disabled={busy} onClick={() => toggle('want')} aria-pressed={want}
        className={`inline-flex items-center gap-2 rounded-xl border-2 px-4 py-2 text-sm font-bold uppercase tracking-wide transition disabled:opacity-60 ${
          want ? 'border-primary bg-primary text-amber-300' : 'border-dashed border-primary/50 text-primary hover:bg-slate-100'
        }`}
      >
        <Plane className="h-4 w-4" /> {want ? t('mark.onList') : t('mark.want')}
      </button>
    </div>
  )
}
