import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { getAnalysisStatus } from '../services/tripService'
import { getRecommendations } from '../services/votingService'

/**
 * Polls GET /trips/{id}/analysis until status === 'voting', then fetches
 * recommendations. Uses a ref-based timer so it doesn't restart on every
 * render and doesn't depend on DEV_MODE mock data.
 */
export default function useRecommendations(tripId) {
  const [recommendations, setRecommendations] = useState([])
  const [status, setStatus] = useState('processing')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Keep a ref so the recursive setTimeout doesn't capture stale closure
  const stopped = useRef(false)

  useEffect(() => {
    stopped.current = false

    const load = async () => {
      if (stopped.current || !tripId) return
      try {
        const analysis = await getAnalysisStatus(tripId)
        setStatus(analysis.status)

        if (analysis.status === 'voting' || analysis.status === 'completed') {
          const recs = await getRecommendations(tripId)
          setRecommendations(recs)
          setLoading(false)
          return // done — no more polling
        }

        // Still running — check again in 3s
        if (!stopped.current) {
          setTimeout(load, 3000)
        }
      } catch (e) {
        if (!stopped.current) {
          setError(e.message)
          toast.error(e.message)
          setLoading(false)
        }
      }
    }

    load()

    return () => {
      stopped.current = true
    }
  }, [tripId])

  return { recommendations, status, loading, error }
}
