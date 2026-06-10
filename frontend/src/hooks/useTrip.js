import { useCallback, useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { getTripSummary } from '../services/tripService'

/**
 * Fetches trip + participants from GET /trips/{id}/summary.
 * The summary endpoint already includes survey_submitted on each participant,
 * so no extra survey-status call is needed.
 */
export default function useTrip(tripId) {
  const [trip, setTrip] = useState(null)
  const [participants, setParticipants] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refetch = useCallback(async () => {
    if (!tripId) return
    try {
      setLoading(true)
      const summary = await getTripSummary(tripId)

      // getTripSummary returns {} if trip not found — treat that as 404
      if (!summary?.trip) {
        setTrip(null)
        setParticipants([])
        setError('')
        return
      }

      setTrip(summary.trip)
      setParticipants(summary.participants ?? [])
      setError('')
    } catch (e) {
      setError(e.message)
      toast.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [tripId])

  useEffect(() => {
    if (tripId) refetch()
  }, [tripId, refetch])

  return { trip, participants, loading, error, refetch }
}
