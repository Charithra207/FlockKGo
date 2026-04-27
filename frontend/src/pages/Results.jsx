import { Link, useParams } from 'react-router-dom'
import ConfettiEffect from '../components/common/ConfettiEffect'
import { DEV_MODE } from '../utils/constants'
import { MOCK_RESULTS } from '../utils/mockData'

export default function Results() {
  const { tripId } = useParams()
  const results = MOCK_RESULTS
  if (!DEV_MODE) {
    // Real endpoint integration is wired in services; fallback used for resilient first render.
  }
  return (
    <div className="space-y-5">
      <ConfettiEffect />
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-2xl">🎉 Your flock is going to...</p>
        <h1 className="mt-2 text-5xl font-extrabold text-primary">{results.winner}</h1>
        <p className="mt-2 text-muted">Trip {tripId} winner by ranked choice voting</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl bg-white p-4 shadow-card">Total voters: {results.total_voters}</div>
        <div className="rounded-xl bg-white p-4 shadow-card">Rounds taken: {results.rounds_taken}</div>
        <div className="rounded-xl bg-white p-4 shadow-card">AI agreement: {results.ai_agreement ? '✓' : '✕'}</div>
      </div>
      <div className="space-y-2">{results.rounds.map((r) => <details key={r.round} className="rounded-xl bg-white p-4 shadow-card"><summary>Round {r.round} (eliminated: {r.eliminated})</summary><pre className="mt-2 text-xs">{JSON.stringify(r.votes, null, 2)}</pre></details>)}</div>
      <div className="flex gap-3">
        <button className="rounded-xl bg-primary px-4 py-2 text-white">Plan Your Trip</button>
        <Link to="/create" className="rounded-xl bg-accent px-4 py-2 text-white">Start a New Trip</Link>
      </div>
    </div>
  )
}
