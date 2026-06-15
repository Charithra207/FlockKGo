import { CheckCircle2, Clock3, Copy, Check } from 'lucide-react'
import { useState } from 'react'

function CopyLinkButton({ surveyToken }) {
  const [copied, setCopied] = useState(false)

  if (!surveyToken) return null

  const handleCopy = () => {
    const link = `${window.location.origin}/survey/${surveyToken}`
    navigator.clipboard.writeText(link).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs text-slate-500 hover:bg-slate-50 transition-colors"
      aria-label="Copy survey link"
    >
      {copied ? (
        <><Check className="h-3 w-3 text-emerald-500" /> Copied</>
      ) : (
        <><Copy className="h-3 w-3" /> Copy link</>
      )}
    </button>
  )
}

export default function ParticipantList({ participants = [], submittedMap = {} }) {
  if (participants.length === 0) return null

  return (
    <div className="rounded-2xl bg-white p-4 shadow-card">
      <h2 className="mb-3 text-sm font-semibold text-slate-600">Participants</h2>
      <div className="space-y-2">
        {participants.map((p) => {
          // Prefer live data from submittedMap if available, fall back to the
          // survey_submitted field that came from the summary endpoint
          const hasSubmitted =
            String(p.id) in submittedMap
              ? submittedMap[String(p.id)]
              : Boolean(p.survey_submitted)

          return (
            <div
              key={p.id}
              className="flex items-center justify-between rounded-xl border px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-slate-800">{p.name}</p>
                {p.email && (
                  <p className="truncate text-xs text-slate-400">{p.email}</p>
                )}
              </div>

              <div className="ml-3 flex shrink-0 items-center gap-2">
                {!hasSubmitted && (
                  <CopyLinkButton surveyToken={p.survey_token} />
                )}
                {hasSubmitted ? (
                  <span className="inline-flex items-center gap-1 text-sm font-medium text-emerald-600">
                    <CheckCircle2 className="h-4 w-4" />
                    Submitted
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-sm text-amber-500">
                    <Clock3 className="h-4 w-4" />
                    Pending
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
