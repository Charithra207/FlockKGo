import { Link, useParams } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import LoadingSpinner from '../components/common/LoadingSpinner'
import ProgressBar from '../components/common/ProgressBar'
import ParticipantList from '../components/trip/ParticipantList'
import TripCard from '../components/trip/TripCard'
import useTrip from '../hooks/useTrip'
import { getSurveyStatus } from '../services/surveyService'
import { runAnalysis } from '../services/tripService'

export default function TripDashboard() {
  const { tripId } = useParams()
  const { trip, participants, loading, refetch } = useTrip(tripId)

  if (loading) return <LoadingSpinner />
  if (!trip) return <p>Trip not found.</p>

  const submitted = participants.filter((p) => p.survey_submitted).length
  const pct = participants.length ? (submitted / participants.length) * 100 : 0
  const allSurveysSubmitted = participants.length >= 2 && submitted === participants.length

  const handleCheckSurveyStatus = async () => {
    try {
      await refetch()
      const status = await getSurveyStatus(tripId)
      const done = status.submitted_count >= 2 && status.submitted_count === status.total_count
      if (!done) {
        toast(`Survey progress: ${status.submitted_count}/${status.total_count}`)
        return
      }

      await runAnalysis(tripId)
      await refetch()
      toast.success('All surveys are in. Recommendations are ready!')
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <div className="space-y-5">
      <TripCard trip={trip} />
      <div className="rounded-2xl bg-white p-6 shadow-card">
        <div className="mb-2 flex items-center justify-between"><h2 className="text-lg font-bold">Survey Progress</h2><p className="text-sm text-muted">{submitted}/{participants.length}</p></div>
        <ProgressBar value={pct} />
      </div>
      <ParticipantList participants={participants} />
      <div className="flex flex-wrap gap-3">
        {trip.status === 'collecting_preferences' && (
          <button onClick={handleCheckSurveyStatus} className="rounded-xl bg-primary px-4 py-2 text-white">
            {allSurveysSubmitted ? 'Generate Recommendations' : 'Check Survey Status'}
          </button>
        )}
        {trip.status === 'running_ml' && <button className="rounded-xl bg-amber-500 px-4 py-2 text-white">AI is analyzing...</button>}
        {trip.status === 'voting' && <Link to={`/trip/${trip.id}/recs`} className="rounded-xl bg-primary px-4 py-2 text-white">View Recommendations</Link>}
        {trip.status === 'completed' && <Link to={`/trip/${trip.id}/results`} className="rounded-xl bg-emerald-600 px-4 py-2 text-white">See Results</Link>}
      </div>
    </div>
  )
}
