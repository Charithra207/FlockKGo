/**
 * Shown on TripDashboard while the ML pipeline is running.
 * Displays an animated pulse + elapsed time so users know it's still alive.
 */
export default function MLStatusBanner({ elapsedSec = 0 }) {
  const mins = Math.floor(elapsedSec / 60)
  const secs = elapsedSec % 60
  const elapsed = mins > 0
    ? `${mins}m ${secs}s`
    : `${secs}s`

  const stages = [
    { label: 'Clustering preferences', threshold: 0 },
    { label: 'Scoring destinations', threshold: 5 },
    { label: 'Consulting AI travel expert', threshold: 12 },
  ]

  // Show the most advanced stage based on elapsed time
  const currentStage = [...stages].reverse().find((s) => elapsedSec >= s.threshold) ?? stages[0]

  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
      <div className="flex items-center gap-3">
        <div className="relative flex h-3 w-3 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
          <span className="relative inline-flex h-3 w-3 rounded-full bg-amber-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-amber-800">{currentStage.label}…</p>
          <p className="text-xs text-amber-600">This usually takes 15–30 seconds</p>
        </div>
        <span className="shrink-0 rounded-lg bg-amber-100 px-2 py-1 text-xs font-mono text-amber-700">
          {elapsed}
        </span>
      </div>
    </div>
  )
}
