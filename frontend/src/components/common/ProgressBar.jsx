export default function ProgressBar({ value }) {
  return (
    <div className="h-2 w-full rounded-full bg-slate-200">
      <div className="h-2 rounded-full bg-accent transition-all" style={{ width: `${Math.min(100, value)}%` }} />
    </div>
  )
}
