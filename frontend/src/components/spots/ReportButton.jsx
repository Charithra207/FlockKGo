import { Flag, X } from 'lucide-react'
import { useState } from 'react'
import toast from 'react-hot-toast'
import { useLocation, useNavigate } from 'react-router-dom'
import api from '../../services/api'
import useAuthStore from '../../store/authStore'

const REASONS = [
  ['closed', 'Closed / no longer exists'],
  ['wrong_location', 'Pin is in the wrong place'],
  ['unsafe', 'Unsafe (dangerous, landslide, closed by forest dept)'],
  ['private_property', "Private property: people shouldn't go"],
  ['crowded', 'Getting too crowded: should be a hidden gem again'],
  ['spam', 'Fake or spam'],
  ['other', 'Something else'],
]

export default function ReportButton({ spotId }) {
  const { token } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('closed')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  async function send() {
    setBusy(true)
    try {
      const r = await api.post(`/spots/${spotId}/report`, { reason, note: note || undefined }).then((x) => x.data)
      toast.success(r.hidden_for_review ? 'Thanks. It is now hidden until an admin checks it.' : 'Thanks for letting us know.')
      setOpen(false)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        onClick={() => (token ? setOpen(true) : navigate(`/login?next=${encodeURIComponent(location.pathname)}`))}
        className="inline-flex items-center gap-1 text-xs font-semibold text-slate-400 hover:text-red-500"
      >
        <Flag className="h-3.5 w-3.5" /> Report a problem
      </button>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-end justify-center bg-slate-900/50 sm:items-center sm:p-4" onClick={() => setOpen(false)}>
          <div className="w-full max-w-md space-y-3 rounded-t-3xl bg-white p-5 shadow-2xl sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-extrabold text-slate-800">What's wrong?</h3>
              <button onClick={() => setOpen(false)} aria-label="Close"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-1.5">
              {REASONS.map(([k, label]) => (
                <label key={k} className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm ${reason === k ? 'border-primary bg-primary/5' : 'border-slate-200'}`}>
                  <input type="radio" name="reason" checked={reason === k} onChange={() => setReason(k)} /> {label}
                </label>
              ))}
            </div>
            <textarea
              value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={2}
              placeholder="Anything that would help (optional)"
              className="w-full rounded-xl border border-slate-200 p-3 text-sm focus:border-primary focus:outline-none"
            />
            <button disabled={busy} onClick={send} className="w-full rounded-xl bg-red-500 py-2.5 font-semibold text-white disabled:opacity-50">
              {busy ? 'Sending…' : 'Send report'}
            </button>
          </div>
        </div>
      )}
    </>
  )
}
