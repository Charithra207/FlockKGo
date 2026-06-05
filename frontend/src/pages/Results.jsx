import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ConfettiEffect from '../components/common/ConfettiEffect'
import { getResults } from '../services/votingService'
import { DEV_MODE } from '../utils/constants'
import { MOCK_RESULTS } from '../utils/mockData'

export default function Results() {
  const { tripId } = useParams()
  const [results, setResults] = useState(DEV_MODE ? MOCK_RESULTS : null)
  const [loading, setLoading] = useState(!DEV_MODE)

  useEffect(() => {
    if (DEV_MODE) return
    getResults(tripId)
      .then((data) => setResults(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [tripId])

  if (loading) {
    return <div className="rounded-2xl bg-white p-8 text-center shadow-card"><p className="text-muted">Loading results...</p></div>
  }

  if (!results) {
    return <div className="rounded-2xl bg-white p-8 text-center shadow-card"><p className="text-muted">No results available yet.</p></div>
  }

  return (
    <div className="space-y-5">
      <ConfettiEffect />
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-2xl">🎉 Your flock is going to...</p>
        <h1 className="mt-2 text-5xl font-extrabold text-primary">{results.winner?.destination_name ?? results.winner}</h1>
        <p className="mt-2 text-muted">Trip {tripId} winner by ranked choice voting</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl bg-white p-4 shadow-card">Total voters: {results.total_voters}</div>
        <div className="rounded-xl bg-white p-4 shadow-card">Rounds taken: {results.rounds_taken}</div>
        <div className="rounded-xl bg-white p-4 shadow-card">AI agreement: {results.ai_agreement ? '✓' : '✕'}</div>
      </div>
      <div className="space-y-2">{results.rounds?.map((r) => <details key={r.round} className="rounded-xl bg-white p-4 shadow-card"><summary>Round {r.round} (eliminated: {r.eliminated})</summary><pre className="mt-2 text-xs">{JSON.stringify(r.votes, null, 2)}</pre></details>)}</div>
      <div className="flex gap-3">
        <button className="rounded-xl bg-primary px-4 py-2 text-white">Plan Your Trip</button>
        <Link to="/create" className="rounded-xl bg-accent px-4 py-2 text-white">Start a New Trip</Link>
      </div>
    </div>
  )
}
