import { Link, useParams } from 'react-router-dom'
import LoadingSpinner from '../components/common/LoadingSpinner'
import DestinationCard from '../components/recommendations/DestinationCard'
import useRecommendations from '../hooks/useRecommendations'

// Human-readable status messages shown while waiting for ML to finish
const STATUS_MESSAGES = {
  running_ml: 'Clustering preferences… scoring destinations… consulting AI travel expert…',
  collecting_preferences: 'Waiting for all surveys to be submitted…',
  processing: 'Analysis in progress…',
}

export default function Recommendations() {
  const { tripId } = useParams()
  const { recommendations, status, loading, error } = useRecommendations(tripId)

  if (loading || (status !== 'voting' && status !== 'completed')) {
    return (
      <LoadingSpinner
        message={STATUS_MESSAGES[status] || 'Preparing recommendations…'}
      />
    )
  }

  if (error) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-3xl">😕</p>
        <h2 className="mt-2 text-lg font-bold text-red-600">Couldn't load recommendations</h2>
        <p className="mt-1 text-sm text-slate-500">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white"
        >
          Retry
        </button>
      </div>
    )
  }

  if (recommendations.length === 0) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-3xl">🤖</p>
        <h2 className="mt-2 text-lg font-bold text-primary">No recommendations yet</h2>
        <p className="mt-1 text-sm text-slate-500">
          The AI hasn't generated destinations for this trip yet.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl font-bold text-primary">AI has spoken 🤖</h1>
        <p className="mt-1 text-sm text-slate-500">
          Destinations ranked by how well they match your group's preferences
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {recommendations.map((r) => (
          <DestinationCard key={r.id} rec={r} />
        ))}
      </div>

      <Link
        to={`/trip/${tripId}/vote`}
        className="inline-block rounded-xl bg-accent px-5 py-3 font-semibold text-white hover:opacity-90"
      >
        Start Voting →
      </Link>
    </div>
  )
}
