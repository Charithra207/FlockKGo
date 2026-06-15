/**
 * Displays a single destination recommendation.
 *
 * ml_score from the backend is a raw float (e.g. 0.86 or 86.0 depending on
 * the model run). We normalise it to 0–100 for display.
 */
function normaliseScore(score) {
  if (!score) return 0
  // If value > 1 it's already on a 0–100 scale
  return score > 1 ? Math.round(score) : Math.round(score * 100)
}

export default function DestinationCard({ rec }) {
  const score = normaliseScore(rec.ml_score)

  return (
    <div className="rounded-2xl bg-white p-5 shadow-card flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-xl font-bold text-primary leading-tight">
          {rec.destination_name}
          {rec.country && (
            <span className="ml-2 text-base font-normal text-slate-400">{rec.country}</span>
          )}
        </h3>
        {rec.rank && (
          <span className="shrink-0 rounded-full bg-primary/10 px-2 py-1 text-xs font-bold text-primary">
            #{rec.rank}
          </span>
        )}
      </div>

      {/* Why recommended */}
      {rec.why_recommended && (
        <p className="text-sm italic text-slate-500">{rec.why_recommended}</p>
      )}

      {/* Budget */}
      {rec.estimated_budget_range && (
        <span className="inline-flex w-fit rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">
          {rec.estimated_budget_range}
        </span>
      )}

      {/* Activities */}
      {rec.best_activities?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {rec.best_activities.map((a) => (
            <span key={a} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
              {a}
            </span>
          ))}
        </div>
      )}

      {/* ML score bar */}
      <div className="mt-auto">
        <div className="mb-1 flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-500">Group Fit Score</p>
          <p className="text-xs font-bold text-primary">{score}%</p>
        </div>
        <div className="h-2 w-full rounded-full bg-slate-200">
          <div
            className="h-2 rounded-full bg-primary transition-all"
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      {/* Concerns */}
      {rec.potential_concerns && (
        <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
          ⚠ {rec.potential_concerns}
        </div>
      )}
    </div>
  )
}
