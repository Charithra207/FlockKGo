import { useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import LoadingSpinner from '../components/common/LoadingSpinner'
import ProgressBar from '../components/common/ProgressBar'
import ParticipantList from '../components/trip/ParticipantList'
import TripCard from '../components/trip/TripCard'
import useTrip from '../hooks/useTrip'
import useSurveyStatus from '../hooks/useSurveyStatus'
import { runAnalysis } from '../services/tripService'

export default function TripDashboard() {
  const { tripId } = useParams()
  const { trip, participants, loading, error, refetch } = useTrip(tripId)

  // Live survey progress — polls every 5s, stops once all submitted
  const { submittedCount, totalCount, allSubmitted, submittedMap } = useSurveyStatus(
    trip ? tripId : null
  )

  // Auto-poll trip status while ML pipeline is running
  const pollingRef = useRef(null)
  useEffect(() => {
    if (trip?.status === 'running_ml') {
      pollingRef.current = setInterval(() => {
        refetch().catch(() => {})
      }, 4000)
    } else {
      clearInterval(pollingRef.current)
    }
    return () => clearInterval(pollingRef.current)
  }, [trip?.status, refetch])

  if (loading) return <LoadingSpinner />

  if (error) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-2xl">😕</p>
        <h2 className="mt-2 text-lg font-bold text-red-600">Failed to load trip</h2>
        <p className="mt-1 text-sm text-slate-500">{error}</p>
        <button
          onClick={() => refetch()}
          className="mt-4 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!trip) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-4xl">🐦</p>
        <h2 className="mt-2 text-xl font-bold text-primary">Trip not found</h2>
        <p className="mt-1 text-sm text-slate-500">
          This trip doesn't exist or the link has expired.
        </p>
        <Link
          to="/create"
          className="mt-4 inline-block rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-white"
        >
          Create a new trip
        </Link>
      </div>
    )
  }

  // Use live counts from useSurveyStatus; fall back to what the summary gave us
  const submitted = totalCount > 0 ? submittedCount : participants.filter((p) => p.survey_submitted).length
  const total = totalCount > 0 ? totalCount : participants.length
  const pct = total ? (submitted / total) * 100 : 0
  const canGenerate = total >= 2 && allSubmitted

  const handleGenerateRecs = async () => {
    try {
      await runAnalysis(tripId)
      toast.success("Analysis started — AI is crunching your flock's preferences…")
      await refetch()
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <div className="space-y-5">
      <TripCard trip={trip} />

      {/* Live survey progress */}
      <div className="rounded-2xl bg-white p-6 shadow-card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-bold">Survey Progress</h2>
          <p className="text-sm text-slate-500">
            {submitted}/{total} submitted
          </p>
        </div>
        <ProgressBar value={pct} />
        {total === 0 && (
          <p className="mt-3 text-sm text-slate-400">
            No participants yet — add some from the Create page.
          </p>
        )}
      </div>

      {/* Participant list with live submitted state + copy links */}
      {participants.length > 0 && (
        <ParticipantList participants={participants} submittedMap={submittedMap} />
      )}

      {/* Action area */}
      <div className="flex flex-wrap gap-3">
        {trip.status === 'collecting_preferences' && (
          canGenerate ? (
            <button
              onClick={handleGenerateRecs}
              className="rounded-xl bg-primary px-4 py-2 font-semibold text-white hover:opacity-90"
            >
              Generate Recommendations
            </button>
          ) : (
            <p className="rounded-xl bg-slate-100 px-4 py-2 text-sm text-slate-500">
              Waiting for all {total} surveys…
            </p>
          )
        )}

        {trip.status === 'running_ml' && (
          <div className="flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700">
            <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
            AI is analyzing your flock's preferences…
          </div>
        )}

        {trip.status === 'voting' && (
          <Link
            to={`/trip/${trip.id}/recs`}
            className="rounded-xl bg-primary px-4 py-2 font-semibold text-white hover:opacity-90"
          >
            View Recommendations
          </Link>
        )}

        {trip.status === 'completed' && (
          <Link
            to={`/trip/${trip.id}/results`}
            className="rounded-xl bg-emerald-600 px-4 py-2 font-semibold text-white hover:opacity-90"
          >
            See Results 🎉
          </Link>
        )}
      </div>
    </div>
  )
}
