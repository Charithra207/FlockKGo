import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { getAnalysisStatus } from '../services/tripService'
import { getRecommendations } from '../services/votingService'
import { DEV_MODE } from '../utils/constants'
import { MOCK_RECOMMENDATIONS } from '../utils/mockData'

export default function useRecommendations(tripId) {
  const [recommendations, setRecommendations] = useState([])
  const [status, setStatus] = useState('processing')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let timer
    const load = async () => {
      try {
        if (DEV_MODE) {
          setRecommendations(MOCK_RECOMMENDATIONS)
          setStatus('voting')
          return
        }
        const analysis = await getAnalysisStatus(tripId)
        setStatus(analysis.status)
        if (analysis.status === 'voting') {
          const recs = await getRecommendations(tripId)
          setRecommendations(recs)
          setLoading(false)
          return
        }
        timer = setTimeout(load, 3000)
      } catch (e) {
        setError(e.message)
        toast.error(e.message)
      } finally {
        setLoading(false)
      }
    }
    if (tripId) load()
    return () => clearTimeout(timer)
  }, [tripId])

  return { recommendations, status, loading, error }
}
