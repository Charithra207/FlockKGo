import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div className="text-7xl">🐦</div>
      <h1 className="text-4xl font-extrabold text-primary">404</h1>
      <p className="text-lg font-semibold text-slate-700">Page not found</p>
      <p className="max-w-sm text-sm text-slate-500">
        This page flew away. Maybe the trip link expired or the URL is wrong.
      </p>
      <Link
        to="/"
        className="mt-2 rounded-xl bg-primary px-6 py-3 font-semibold text-white hover:opacity-90"
      >
        Back to Home
      </Link>
    </div>
  )
}
