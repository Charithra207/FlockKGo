export default function MLScoreBadge({ score }) {
  return <span className="rounded-full bg-primary/10 px-2 py-1 text-xs font-semibold text-primary">ML {Math.round((score || 0) * 100)}%</span>
}
