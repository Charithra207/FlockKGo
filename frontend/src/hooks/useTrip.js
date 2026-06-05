import { useCallback, useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { getTripSummary } from '../services/tripService'
import { DEV_MODE } from '../utils/constants'
import { MOCK_PARTICIPANTS, MOCK_TRIP } from '../utils/mockData'

export default function useTrip(tripId) {
  const [trip, setTrip] = useState(null)
  const [participants, setParticipants] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refetch = useCallback(async () => {
    try {
      setLoading(true)
      if (DEV_MODE) {
        setTrip({ ...MOCK_TRIP, id: tripId || MOCK_TRIP.id })
        setParticipants(MOCK_PARTICIPANTS)
        return
      }
      const summary = await getTripSummary(tripId)
      setTrip(summary.trip)
      setParticipants(summary.participants)
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
