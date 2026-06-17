import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { getTripSummary } from '../services/tripService'

/**
 * Fetches trip + participants from GET /trips/{id}/summary.
 *
 * `refetch` has two modes:
 *   - silent (default for background polling): doesn't set loading=true,
 *     so no spinner flash during auto-refresh
 *   - loud (first load): sets loading=true so the page shows a spinner
 */
export default function useTrip(tripId) {
  const [trip, setTrip] = useState(null)
  const [participants, setParticipants] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Track whether this is the very first load
  const initialised = useRef(false)

  const refetch = useCallback(
    async ({ silent = false } = {}) => {
      if (!tripId) return
      // Only show the full-page spinner on the first load
      if (!silent && !initialised.current) setLoading(true)
      try {
        const summary = await getTripSummary(tripId)

        if (!summary?.trip) {
          setTrip(null)
          setParticipants([])
          setError('')
          return
        }

        setTrip(summary.trip)
        setParticipants(summary.participants ?? [])
        setError('')
        initialised.current = true
      } catch (e) {
        setError(e.message)
        // Only toast on explicit (non-silent) fetches to avoid spam
        if (!silent) toast.error(e.message)
      } finally {
        setLoading(false)
      }
    },
    [tripId],
  )

  useEffect(() => {
    if (tripId) refetch()
  }, [tripId, refetch])

  return { trip, participants, loading, error, refetch }
}
