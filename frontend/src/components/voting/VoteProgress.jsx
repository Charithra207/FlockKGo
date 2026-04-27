import ProgressBar from '../common/ProgressBar'

export default function VoteProgress({ voted, total }) {
  const percent = total ? (voted / total) * 100 : 0
  return (
    <div className="rounded-xl bg-white p-4 shadow-card">
      <p className="mb-2 text-sm font-semibold">{voted} of {total} people have voted</p>
      <ProgressBar value={percent} />
    </div>
  )
}
