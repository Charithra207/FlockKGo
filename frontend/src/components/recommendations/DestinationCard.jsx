import { formatCurrency } from '../../utils/formatters'

export default function DestinationCard({ rec }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-card">
      <h3 className="text-xl font-bold text-primary">{rec.country_flag} {rec.name}</h3>
      <p className="mt-1 text-sm italic text-muted">{rec.why}</p>
      <span className="mt-3 inline-flex rounded-full bg-emerald-100 px-3 py-1 text-xs text-emerald-700">{formatCurrency(rec.budget_min)} - {formatCurrency(rec.budget_max)}</span>
      <div className="mt-3 flex flex-wrap gap-2">{rec.activities?.map((a) => <span key={a} className="rounded-full bg-slate-100 px-2 py-1 text-xs">{a}</span>)}</div>
      <div className="mt-4">
        <p className="text-xs font-semibold text-muted">Group Fit Score: {rec.ml_score}%</p>
        <div className="mt-1 h-2 rounded bg-slate-200"><div className="h-2 rounded bg-primary" style={{ width: `${rec.ml_score}%` }} /></div>
      </div>
      {rec.concern && <div className="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-700">{rec.concern}</div>}
    </div>
  )
}
