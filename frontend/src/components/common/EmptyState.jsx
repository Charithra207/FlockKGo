/**
 * Reusable empty-state block.
 *
 * Props:
 *   emoji    – big visual (default 🐦)
 *   title    – bold heading
 *   message  – supporting text (optional)
 *   action   – { label, onClick } or { label, href } (optional)
 */
export default function EmptyState({ emoji = '🐦', title, message, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-white px-8 py-12 text-center shadow-card">
      <span className="text-5xl" role="img" aria-hidden="true">{emoji}</span>
      <h3 className="text-lg font-bold text-slate-700">{title}</h3>
      {message && <p className="max-w-xs text-sm text-slate-400">{message}</p>}
      {action && (
        action.href ? (
          <a
            href={action.href}
            className="mt-1 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            {action.label}
          </a>
        ) : (
          <button
            onClick={action.onClick}
            className="mt-1 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white hover:opacity-90"
          >
            {action.label}
          </button>
        )
      )}
    </div>
  )
}
