export default function DestinationCard({ rec }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-card">
      <h3 className="text-xl font-bold text-primary">{rec.country_flag} {rec.destination_name}</h3>
      <p className="mt-1 text-sm italic text-muted">{rec.why_recommended}</p>
      <span className="mt-3 inline-flex rounded-full bg-emerald-100 px-3 py-1 text-xs text-emerald-700">{rec.estimated_budget_range}</span>
      <div className="mt-3 flex flex-wrap gap-2">{rec.best_activities?.map((a) => <span key={a} className="rounded-full bg-slate-100 px-2 py-1 text-xs">{a}</span>)}</div>
      <div className="mt-4">
        <p className="text-xs font-semibold text-muted">Group Fit Score: {Math.round((rec.ml_score || 0) * 100)}%</p>
        <div className="mt-1 h-2 rounded bg-slate-200"><div className="h-2 rounded bg-primary" style={{ width: `${Math.round((rec.ml_score || 0) * 100)}%` }} /></div>
      </div>
      {rec.potential_concerns && <div className="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-700">{rec.potential_concerns}</div>}
    </div>
  )
}
