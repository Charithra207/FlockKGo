import { Loader2 } from 'lucide-react'

const variants = {
  collecting_preferences: 'bg-blue-100 text-blue-700',
  running_ml: 'bg-amber-100 text-amber-700',
  voting: 'bg-purple-100 text-purple-700',
  completed: 'bg-emerald-100 text-emerald-700',
}

const labels = {
  collecting_preferences: 'Collecting Preferences',
  running_ml: 'Analyzing...',
  voting: 'Voting Open',
  completed: 'Trip Decided!',
}

export default function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${variants[status] || 'bg-slate-100'}`}>
      {status === 'running_ml' && <Loader2 className="h-3 w-3 animate-spin" />}
      {labels[status] || status}
    </span>
  )
}
