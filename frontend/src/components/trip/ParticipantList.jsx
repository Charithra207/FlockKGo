import { CheckCircle2, Clock3 } from 'lucide-react'

export default function ParticipantList({ participants = [] }) {
  return (
    <div className="space-y-2">
      {participants.map((p) => (
        <div key={p.id} className="flex items-center justify-between rounded-xl border bg-white p-3">
          <p className="font-medium">{p.name}</p>
          {p.survey_submitted ? (
            <span className="inline-flex items-center gap-1 text-sm text-success"><CheckCircle2 className="h-4 w-4" /> Submitted</span>
          ) : (
            <span className="inline-flex items-center gap-1 text-sm text-warning"><Clock3 className="h-4 w-4" /> Pending</span>
          )}
        </div>
      ))}
    </div>
  )
}
