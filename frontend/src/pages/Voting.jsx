import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { useParams } from 'react-router-dom'
import DraggableRankList from '../components/voting/DraggableRankList'
import VoteProgress from '../components/voting/VoteProgress'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { getRecommendations, getVoteStatus, submitVote } from '../services/votingService'
import api from '../services/api'

export default function Voting() {
  const { tripId } = useParams()

  // Recommendations
  const [items, setItems] = useState([])
  const [itemsLoading, setItemsLoading] = useState(true)
  const [itemsError, setItemsError] = useState('')

  // Participant identity — resolved by name lookup against real DB participants
  const [nameInput, setNameInput] = useState('')
  const [participantId, setParticipantId] = useState(null)
  const [participantName, setParticipantName] = useState('')
  const [identityError, setIdentityError] = useState('')

  // Vote state
  const [hasVoted, setHasVoted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [voteStatus, setVoteStatus] = useState({ voted_count: 0, total_count: 0 })

  // Load recommendations once
  useEffect(() => {
    getRecommendations(tripId)
      .then((recs) => {
        const normalised = (Array.isArray(recs) ? recs : []).map((r) => ({
          ...r,
          name: r.destination_name ?? r.name,
        }))
        setItems(normalised)
      })
      .catch((e) => setItemsError(e.message))
      .finally(() => setItemsLoading(false))
  }, [tripId])

  // Poll vote status every 5s
  useEffect(() => {
    let timer
    const poll = async () => {
      try {
        const status = await getVoteStatus(tripId)
        setVoteStatus(status)
        // If we know who we are, check if this participant already voted
        if (participantId) {
          const me = status?.participants?.find((p) => p.id === participantId)
          if (me?.has_voted) setHasVoted(true)
        }
      } catch {
        // silent — don't spam toasts on poll errors
      } finally {
        timer = setTimeout(poll, 5000)
      }
    }
    poll()
    return () => clearTimeout(timer)
  }, [tripId, participantId])

  // Resolve a typed name to a real participant UUID
  const handleIdentify = async () => {
    const name = nameInput.trim()
    if (!name) return
    setIdentityError('')
    try {
      const res = await api.get(`/trips/${tripId}/participants`)
      const participants = res.data?.participants ?? res.data ?? []
      const match = participants.find(
        (p) => p.name.toLowerCase() === name.toLowerCase()
      )
      if (!match) {
        setIdentityError(`No participant named "${name}" found in this trip. Check the name and try again.`)
        return
      }
      setParticipantId(match.id)
      setParticipantName(match.name)
    } catch (e) {
      setIdentityError(e.message)
    }
  }

  const handleSubmitVote = async () => {
    if (!participantId) {
      toast.error('Please identify yourself first')
      return
    }
    if (items.length === 0) {
      toast.error('No destinations to vote on')
      return
    }
    setSubmitting(true)
    try {
      await submitVote(tripId, {
        participant_id: participantId,
        ranked_choices: items.map((item, index) => ({
          rank: index + 1,
          recommendation_id: item.id,
        })),
      })
      setHasVoted(true)
      toast.success('Vote submitted! Your ranking has been saved.')
    } catch (e) {
      toast.error(e.message || 'Failed to submit vote. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Identity gate ─────────────────────────────────────────────────────────
  if (!participantId) {
    return (
      <div className="mx-auto max-w-sm rounded-2xl bg-white p-6 shadow-card">
        <h1 className="mb-3 text-xl font-bold text-primary">Who are you?</h1>
        <p className="mb-4 text-sm text-slate-500">
          Enter your name exactly as your organizer added you to the trip.
        </p>
        <input
          className="w-full rounded-xl border p-3 focus:outline-none focus:ring-2 focus:ring-primary"
          value={nameInput}
          onChange={(e) => setNameInput(e.target.value)}
          placeholder="Your name"
          onKeyDown={(e) => e.key === 'Enter' && handleIdentify()}
          aria-label="Your name"
        />
        {identityError && (
          <p className="mt-2 text-xs text-red-500">{identityError}</p>
        )}
        <button
          onClick={handleIdentify}
          disabled={!nameInput.trim()}
          className="mt-3 w-full rounded-xl bg-primary px-4 py-2 font-semibold text-white disabled:opacity-50 hover:opacity-90"
        >
          Continue
        </button>
      </div>
    )
  }

  // ── Loading / error states ────────────────────────────────────────────────
  if (itemsLoading) return <LoadingSpinner message="Loading destinations to rank..." />

  if (itemsError) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-card">
        <p className="text-3xl">😕</p>
        <h2 className="mt-2 text-lg font-bold text-red-600">Could not load recommendations</h2>
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
          The AI has not generated destinations for this trip yet.
        </p>
      </div>
    )
  }

  // ── Voting UI ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl font-bold text-primary">Rank your favorites</h1>
        <p className="mt-1 text-sm text-slate-500">
          Voting as <span className="font-semibold">{participantName}</span> — drag to rank, top is most preferred
        </p>
      </div>

      <DraggableRankList items={items} setItems={setItems} />

      {hasVoted ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm font-semibold text-emerald-700">
          ✓ Your vote has been submitted! Waiting for others...
        </div>
      ) : (
        <button
          disabled={submitting}
          onClick={handleSubmitVote}
          className="w-full rounded-xl bg-accent px-5 py-3 font-semibold text-white disabled:opacity-50 hover:opacity-90 sm:w-auto"
          aria-label="Submit your ranking"
        >
          {submitting ? 'Submitting...' : 'Submit My Rankings'}
        </button>
      )}

      <VoteProgress voted={voteStatus.voted_count} total={voteStatus.total_count} />
    </div>
  )
}
