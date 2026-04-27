import { Link, useParams } from 'react-router-dom'
import LoadingSpinner from '../components/common/LoadingSpinner'
import DestinationCard from '../components/recommendations/DestinationCard'
import useRecommendations from '../hooks/useRecommendations'

export default function Recommendations() {
  const { tripId } = useParams()
  const { recommendations, status, loading } = useRecommendations(tripId)

  if (loading && status !== 'complete') return <LoadingSpinner message="Clustering preferences... Scoring destinations... Consulting AI travel expert..." />

  return (
    <div className="space-y-5">
      <h1 className="text-3xl font-bold text-primary">AI has spoken 🤖</h1>
      <div className="rounded-2xl bg-primary/5 p-4 text-sm text-primary">Group compatibility score is high. Your flock has 2 major preference clusters and one clear overlap path.</div>
      <div className="grid gap-4 md:grid-cols-2">{recommendations.map((r) => <DestinationCard key={r.id} rec={r} />)}</div>
      <Link to={`/trip/${tripId}/vote`} className="inline-block rounded-xl bg-accent px-5 py-3 font-semibold text-white">Start Voting</Link>
    </div>
  )
}
