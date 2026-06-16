import { useCallback } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { Copy, Check } from 'lucide-react'
import { useState } from 'react'
import LoadingSpinner from '../components/common/LoadingSpinner'
import ProgressBar from '../components/common/ProgressBar'
import ParticipantList from '../components/trip/ParticipantList'
import TripCard from '../components/trip/TripCard'
import MLStatusBanner from '../components/trip/MLStatusBanner'
import useTrip from '../hooks/useTrip'
import useSurveyStatus from '../hooks/useSurveyStatus'
import useAnalysisPoller from '../hooks/useAnalysisPoller'
import { runAnalysis } from '../services/tripService'

function CopyLinkButton({ url }) {
  const [copied, setCopied] = useState(false)
  const handle = () => {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={handle}
      className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-50"
      aria-label="Copy trip link"
    >
      {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
      {copied ? 'Copied!' : 'Copy trip link'}
    </button>
  )
}

export default function TripDashboard() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const { trip, participants, loading, error, refetch } = useTrip(tripId)

  // Live survey progress — polls every 5s, stops once all submitted
  const { submittedCount, totalCount, allSubmitted, submittedMap } = useSurveyStatus(
    trip ? tripId : null,
  )

  // When ML finishes, silently re-fetch the trip so the status badge flips,
  // then navigate to recommendations automatically
  const handleAnalysisComplete = useCallback(
    (newStatus) => {
      refetch({ silent: true }).finally(() => {
        if (newStatus === 'voting') {
          navigate(`/trip/${tripId}/recs`)
        }
      })
    },
    [refetch, navigate, tripId],
  )

  // Polls /analysis every 4s while status === 'running_ml'
  const { isPolling, elapsedSec } = useAnalysisPoller(
    tripId,
    trip?.status,
    handleAnalysisComplete,
  )

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

  // Use live counts from useSurveyStatus; fall back to summary data
  const submitted = totalCount > 0 ? submittedCount : participants.filter((p) => p.survey_submitted).length
  const total = totalCount > 0 ? totalCount : participants.length
  const pct = total ? (submitted / total) * 100 : 0
  const canGenerate = total >= 2 && allSubmitted

  const handleGenerateRecs = async () => {
    try {
      await runAnalysis(tripId)
      // Silent refetch flips the status badge without a full-page spinner
      await refetch({ silent: true })
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <TripCard trip={trip} />
        </div>
      </div>

      {/* Share link */}
      <div className="flex items-center gap-2">
        <CopyLinkButton url={`${window.location.origin}/trip/${tripId}`} />
      </div>

      {/* ML running banner with elapsed timer */}
      {isPolling && <MLStatusBanner elapsedSec={elapsedSec} />}

      {/* Live survey progress */}
      <div className="rounded-2xl bg-white p-6 shadow-card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-bold">Survey Progress</h2>
          <p className="text-sm text-slate-500">{submitted}/{total} submitted</p>
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
