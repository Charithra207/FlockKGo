import { useCallback, useEffect, useState } from 'react'
import { getSurveyStatus } from '../services/surveyService'

/**
 * Polls GET /trips/{id}/survey-status on an interval and returns live
 * submitted/total counts plus a per-participant submitted map.
 *
 * Stops polling once all participants have submitted.
 */
export default function useSurveyStatus(tripId, intervalMs = 5000) {
  const [submittedCount, setSubmittedCount] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  const [submittedMap, setSubmittedMap] = useState({}) // { participantId: bool }
  const [allSubmitted, setAllSubmitted] = useState(false)

  const poll = useCallback(async () => {
    if (!tripId) return
    try {
      const data = await getSurveyStatus(tripId)
      setSubmittedCount(data.submitted_count ?? 0)
      setTotalCount(data.total_count ?? 0)
      setAllSubmitted(Boolean(data.all_submitted))

      // Build a quick lookup map from the participants array
      const map = {}
      for (const p of data.participants ?? []) {
        map[String(p.id)] = Boolean(p.submitted)
      }
      setSubmittedMap(map)
    } catch {
      // silent — polling errors shouldn't toast on every tick
    }
  }, [tripId])

  useEffect(() => {
    if (!tripId) return
    poll()
    const timer = setInterval(() => {
      // Stop polling once everyone is in
      if (!allSubmitted) poll()
    }, intervalMs)
    return () => clearInterval(timer)
  }, [tripId, intervalMs, poll, allSubmitted])

  return { submittedCount, totalCount, allSubmitted, submittedMap }
}
