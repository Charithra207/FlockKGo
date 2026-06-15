import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { getAnalysisStatus } from '../services/tripService'

/**
 * Polls GET /trips/{id}/analysis every `intervalMs` while the trip status is
 * `running_ml`. Stops automatically when the status changes to something else
 * (typically `voting`).
 *
 * Returns:
 *   isPolling   – true while actively waiting for ML to finish
 *   elapsedSec  – seconds since polling started (for the UI timer)
 *   lastStatus  – latest status string from the analysis endpoint
 */
export default function useAnalysisPoller(tripId, currentStatus, onComplete, intervalMs = 4000) {
  const [isPolling, setIsPolling] = useState(false)
  const [elapsedSec, setElapsedSec] = useState(0)
  const [lastStatus, setLastStatus] = useState(currentStatus)

  const startedAt = useRef(null)
  const timerRef = useRef(null)
  const tickRef = useRef(null)

  useEffect(() => {
    // Only poll when running_ml
    if (currentStatus !== 'running_ml') {
      setIsPolling(false)
      clearInterval(timerRef.current)
      clearInterval(tickRef.current)
      startedAt.current = null
      setElapsedSec(0)
      return
    }

    setIsPolling(true)
    startedAt.current = Date.now()

    // Elapsed-time ticker (every second)
    tickRef.current = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt.current) / 1000))
    }, 1000)

    // Status poller
    const poll = async () => {
      if (!tripId) return
      try {
        const data = await getAnalysisStatus(tripId)
        setLastStatus(data.status)

        if (data.status !== 'running_ml') {
          // ML finished — clean up and notify parent
          clearInterval(timerRef.current)
          clearInterval(tickRef.current)
          setIsPolling(false)
          toast.success(
            data.status === 'voting'
              ? '✅ Analysis complete! Recommendations are ready.'
              : '⚠ Analysis finished with an unexpected status.',
          )
          onComplete?.(data.status)
        }
      } catch {
        // silent — don't toast on every failed poll tick
      }
    }

    poll() // immediate first check
    timerRef.current = setInterval(poll, intervalMs)

    return () => {
      clearInterval(timerRef.current)
      clearInterval(tickRef.current)
    }
  }, [tripId, currentStatus, intervalMs, onComplete])

  return { isPolling, elapsedSec, lastStatus }
}
