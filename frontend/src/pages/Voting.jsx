import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { useParams } from 'react-router-dom'
import DraggableRankList from '../components/voting/DraggableRankList'
import VoteProgress from '../components/voting/VoteProgress'
import useVoting from '../hooks/useVoting'
import { getRecommendations } from '../services/votingService'
import useUserStore from '../store/userStore'
import { DEV_MODE } from '../utils/constants'
import { MOCK_RECOMMENDATIONS } from '../utils/mockData'

export default function Voting() {
  const { tripId } = useParams()
  const { participantId, setParticipant } = useUserStore()
  const [nameInput, setNameInput] = useState('')
  const [items, setItems] = useState([])
  const { hasVoted, submitVote, voteStatus, loading } = useVoting(tripId, participantId)

  useEffect(() => {
    ;(DEV_MODE ? Promise.resolve(MOCK_RECOMMENDATIONS) : getRecommendations(tripId)).then(setItems).catch((e) => toast.error(e.message))
  }, [tripId])

  if (!participantId) {
    return <div className="rounded-2xl bg-white p-6 shadow-card"><h1 className="mb-3 text-xl font-bold">Identify yourself to vote</h1><input className="w-full rounded-xl border p-3" value={nameInput} onChange={(e) => setNameInput(e.target.value)} placeholder="Your name" /><button onClick={() => nameInput && setParticipant(`manual-${nameInput}`, nameInput)} className="mt-3 rounded-xl bg-primary px-4 py-2 text-white">Continue</button></div>
  }

  return (
    <div className="space-y-5">
      <h1 className="text-3xl font-bold text-primary">Rank your favorites</h1>
      <p className="text-muted">Drag to rank these destinations from most to least preferred</p>
      <DraggableRankList items={items} setItems={setItems} />
      <button disabled={hasVoted || loading} onClick={() => submitVote(items.map((i) => i.id))} className="rounded-xl bg-accent px-5 py-3 font-semibold text-white disabled:opacity-50">{hasVoted ? "You've voted! Waiting for others..." : 'Submit My Rankings'}</button>
      <VoteProgress voted={voteStatus.voted_count} total={voteStatus.total_count} />
    </div>
  )
}
