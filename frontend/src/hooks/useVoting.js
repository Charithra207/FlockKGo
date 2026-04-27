import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { getVoteStatus, submitVote as submitVoteService } from '../services/votingService'
import { DEV_MODE } from '../utils/constants'

export default function useVoting(tripId, participantId) {
  const [hasVoted, setHasVoted] = useState(false)
  const [voteStatus, setVoteStatus] = useState({ voted_count: 0, total_count: 0 })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let timer
    const poll = async () => {
      if (!tripId) return
      try {
        if (DEV_MODE) {
          setVoteStatus({ voted_count: 3, total_count: 5 })
          return
        }
        const status = await getVoteStatus(tripId)
        setVoteStatus(status)
        setHasVoted(Boolean(status?.voters?.includes(participantId)))
      } catch (e) {
        toast.error(e.message)
      } finally {
        timer = setTimeout(poll, 5000)
      }
    }
    poll()
    return () => clearTimeout(timer)
  }, [participantId, tripId])

  const submitVote = async (ranking) => {
    try {
      setLoading(true)
      if (!DEV_MODE) await submitVoteService(tripId, { participant_id: participantId, ranking })
      setHasVoted(true)
      toast.success('Vote submitted!')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  return { hasVoted, submitVote, voteStatus, loading }
}
