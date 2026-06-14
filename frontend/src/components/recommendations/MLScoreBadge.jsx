export default function MLScoreBadge({ score }) {
  const pct = !score ? 0 : score > 1 ? Math.round(score) : Math.round(score * 100)
  return (
    <span className="rounded-full bg-primary/10 px-2 py-1 text-xs font-semibold text-primary">
      {pct}% fit
    </span>
  )
}
