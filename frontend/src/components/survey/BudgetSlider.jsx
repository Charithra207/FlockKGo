import { formatBudgetRange } from '../../utils/formatters'

export default function BudgetSlider({ min, max, onChange }) {
  return (
    <div>
      <p className="mb-2 text-lg font-semibold">{formatBudgetRange(min, max)}</p>
      <div className="space-y-3">
        <input type="range" min="0" max="10000" step="100" value={min} onChange={(e) => onChange(Math.min(Number(e.target.value), max), max)} className="w-full accent-accent" />
        <input type="range" min="0" max="10000" step="100" value={max} onChange={(e) => onChange(min, Math.max(Number(e.target.value), min))} className="w-full accent-primary" />
      </div>
      <div className="mt-2 flex justify-between text-xs text-muted"><span>Budget</span><span>Mid-range</span><span>Luxury</span></div>
    </div>
  )
}
