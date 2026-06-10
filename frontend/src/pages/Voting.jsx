import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { useParams } from 'react-router-dom'
import DraggableRankList from '../components/voting/DraggableRankList'
import VoteProgress from '../components/voting/VoteProgress'
import LoadingSpinner from '../components/common/LoadingSpinner'
import useVoting from '../hooks/useVoting'
import { getRecommendations } from '../services/votingService'
import useUserStore from '../store/userStore'

export default function Voting() {
  const { tripId } = useParams()
  const { participantId, setParticipant } = useUserStore()
  const [nameInput, setNameInput] = useState('')
  const [items, setItems] = useState([])
  const [itemsLoading, setItemsLoading] = useState(true)
  const [itemsError, setItemsError] = useState('')
  const { hasVoted, submitVote, voteStatus, loading } = useVoting(tripId, participantId)

  useEffect(() => {
    getRecommendations(tripId)
      .then((recs) => {
        // Normalise to the shape dnd-kit needs: { id, name, ... }
        const normalised = recs.map((r) => ({
          ...r,
          // backend returns destination_name; give it a short `name` alias too
          name: r.destination_name ?? r.name,
        }))
        setItems(normalised)
      })
      .catch((e) => setItemsError(e.message))
      .finally(() => setItemsLoading(false))
  }, [tripId])

  // Identify participant by name if no ID is stored yet
  if (!participantId) {
    return (
      <div className="mx-auto max-w-sm rounded-2xl bg-white p-6 shadow-card">
        <h1 className="mb-3 text-xl font-bold text-primary">Who are you?</h1>
        <p className="mb-4 text-sm text-slate-500">
          Enter your name so we can record your vote correctly.
        </p>
        <input
          className="w-full rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-primary"
          value={nameInput}
          onChange={(e) => setNameInput(e.target.value)}
          placeholder="Your name"
          onKeyDown={(e) => e.key === 'Enter' && nameInput && setParticipant(`manual-${nameInput}`, nameInput)}
          aria-label="Your name"
        />
        <button
          onClick={() => nameInput && setParticipant(`manual-${nameInput}`, nameInput)}
          disabled={!nameInput.trim()}
          className="mt-3 w-full rounded-xl bg-primary px-4 py-2 font-semibold text-white disabled:opacity-50 hover:opacity-90"
        >
          Continue
        </button>
      </div>
    )
  }

  if (itemsLoading) return <LoadingSpinner message="Loading destinations to rank…" />

  if (itemsError) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-3xl">😕</p>
        <h2 className="mt-2 text-lg font-bold text-red-600">Couldn't load recommendations</h2>
        <p className="mt-1 text-sm text-slate-500">{itemsError}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white"
        >
          Retry
        </button>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-3xl">🤖</p>
        <h2 className="mt-2 text-lg font-bold text-primary">No recommendations yet</h2>
        <p className="mt-1 text-sm text-slate-500">
          The AI hasn't generated destinations for this trip yet.
        </p>
      </div>
    )
  }

  const handleSubmitVote = () => {
    submitVote({
      participant_id: participantId,
      ranked_choices: items.map((item, index) => ({
        rank: index + 1,
        recommendation_id: item.id,
      })),
    })
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl font-bold text-primary">Rank your favorites</h1>
        <p className="mt-1 text-sm text-slate-500">Drag to rank these destinations — top is most preferred</p>
      </div>

      <DraggableRankList items={items} setItems={setItems} />

      <button
        disabled={hasVoted || loading}
        onClick={handleSubmitVote}
        className="w-full rounded-xl bg-accent px-5 py-3 font-semibold text-white disabled:opacity-50 hover:opacity-90 sm:w-auto"
        aria-label={hasVoted ? 'Vote already submitted' : 'Submit your ranking'}
      >
        {loading ? 'Submitting…' : hasVoted ? "You've voted! Waiting for others…" : 'Submit My Rankings'}
      </button>

      <VoteProgress voted={voteStatus.voted_count} total={voteStatus.total_count} />
    </div>
  )
}
