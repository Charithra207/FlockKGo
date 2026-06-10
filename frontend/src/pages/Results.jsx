import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ConfettiEffect from '../components/common/ConfettiEffect'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { getResults } from '../services/votingService'

export default function Results() {
  const { tripId } = useParams()
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    setError('')
    getResults(tripId)
      .then((data) => setResults(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [tripId])

  if (loading) return <LoadingSpinner message="Counting the votes…" />

  if (error) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-3xl">😕</p>
        <h2 className="mt-2 text-lg font-bold text-red-600">Couldn't load results</h2>
        <p className="mt-1 text-sm text-slate-500">{error}</p>
        <button
          onClick={load}
          className="mt-4 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!results) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-3xl">🗳️</p>
        <h2 className="mt-2 text-lg font-bold text-primary">No results yet</h2>
        <p className="mt-1 text-sm text-slate-500">Voting may still be in progress.</p>
      </div>
    )
  }

  // Winner can be an object (backend returns full destination details) or a string
  const winnerName =
    typeof results.winner === 'object'
      ? results.winner?.destination_name
      : results.winner

  const winnerDetails =
    typeof results.winner === 'object' ? results.winner : null

  return (
    <div className="space-y-5">
      <ConfettiEffect />

      {/* Winner card */}
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-2xl font-medium text-slate-600">Your flock is going to…</p>
        <h1 className="mt-2 text-5xl font-extrabold text-primary">{winnerName}</h1>
        {winnerDetails?.country && (
          <p className="mt-1 text-lg text-slate-500">{winnerDetails.country}</p>
        )}
        {winnerDetails?.why_recommended && (
          <p className="mx-auto mt-3 max-w-md text-sm text-slate-500 italic">
            "{winnerDetails.why_recommended}"
          </p>
        )}
        {winnerDetails?.estimated_budget_range && (
          <p className="mt-2 text-sm font-medium text-slate-600">
            Budget: {winnerDetails.estimated_budget_range}
          </p>
        )}
      </div>

      {/* Stats row */}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl bg-white p-4 text-center shadow-card">
          <p className="text-2xl font-bold text-primary">{results.total_voters}</p>
          <p className="text-xs text-slate-500">Voters</p>
        </div>
        <div className="rounded-xl bg-white p-4 text-center shadow-card">
          <p className="text-2xl font-bold text-primary">{results.rounds_taken}</p>
          <p className="text-xs text-slate-500">IRV Rounds</p>
        </div>
        <div className="rounded-xl bg-white p-4 text-center shadow-card">
          <p className="text-2xl font-bold text-primary">{results.ai_agreement ? '✓' : '✕'}</p>
          <p className="text-xs text-slate-500">AI Agreement</p>
        </div>
      </div>

      {/* Round-by-round breakdown */}
      {results.rounds?.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-bold text-slate-700">Round breakdown</h2>
          {results.rounds.map((r) => (
            <details key={r.round} className="rounded-xl bg-white p-4 shadow-card">
              <summary className="cursor-pointer text-sm font-semibold text-slate-700">
                Round {r.round}
                {r.eliminated && (
                  <span className="ml-2 text-xs font-normal text-slate-400">
                    — eliminated: {r.eliminated}
                  </span>
                )}
              </summary>
              <ul className="mt-3 space-y-1">
                {Object.entries(r.votes || {}).map(([dest, count]) => (
                  <li key={dest} className="flex items-center justify-between text-sm">
                    <span>{dest}</span>
                    <span className="font-semibold">{count} votes</span>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <Link
          to="/create"
          className="rounded-xl bg-accent px-5 py-3 font-semibold text-white hover:opacity-90"
        >
          Plan Another Trip
        </Link>
        <Link
          to="/"
          className="rounded-xl border px-5 py-3 font-semibold text-slate-600 hover:bg-slate-50"
        >
          Home
        </Link>
      </div>
    </div>
  )
}
