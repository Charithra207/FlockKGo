import { ShieldAlert } from 'lucide-react'
import { SAFETY_META } from '../../services/spotsService'

const MONSOON = [6, 7, 8, 9]
const WET_KINDS = ['waterfall', 'trek', 'viewpoint', 'lake', 'beach']

/** Safety notes locals added, plus an automatic monsoon warning for wet-season risks. */
export default function SafetyNotes({ spot }) {
  const notes = spot.safety || []
  const month = new Date().getMonth() + 1
  const monsoonNow = MONSOON.includes(month) && WET_KINDS.includes(spot.category) && !notes.includes('monsoon_danger')
  if (!notes.length && !monsoonNow && !spot.permit_required) return null
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-bold text-amber-800"><ShieldAlert className="h-4 w-4" /> Before you go</p>
      <ul className="space-y-1.5 text-sm text-amber-900">
        {monsoonNow && (
          <li>🌧️ <b>Monsoon season:</b> water levels change fast and rocks get slippery. Don't go near the edge or into the water, and check if the area is open.</li>
        )}
        {spot.permit_required && !notes.includes('forest_permission') && <li>📝 <b>Permission needed:</b> check entry rules before you go.</li>}
        {notes.map((k) => SAFETY_META[k] && (
          <li key={k}>{SAFETY_META[k].emoji} <b>{SAFETY_META[k].label}:</b> {SAFETY_META[k].tip}</li>
        ))}
      </ul>
    </div>
  )
}
