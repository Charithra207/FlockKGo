import { useEffect, useState } from 'react'
import StatusBadge from './StatusBadge'
import { getTrip } from '../../services/tripService'

export default function TripCard({ trip }) {
  const [details, setDetails] = useState(null)

  // The summary endpoint only returns id/name/status/organizer.
  // Fetch the full trip to get trip_month and duration_days.
  useEffect(() => {
    if (trip?.id) {
      getTrip(trip.id)
        .then(setDetails)
        .catch(() => {}) // non-critical — card still renders without it
    }
  }, [trip?.id])

  const full = { ...trip, ...details }

  return (
    <div className="rounded-2xl bg-white p-6 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-primary">{full?.name}</h1>
        <StatusBadge status={full?.status} />
      </div>
      <p className="text-sm text-slate-500">Organizer: {full?.organizer_name}</p>
      {(full?.trip_month || full?.duration_days) && (
        <p className="text-sm text-slate-500">
          {[full.trip_month, full.duration_days && `${full.duration_days} days`]
            .filter(Boolean)
            .join(' · ')}
        </p>
      )}
    </div>
  )
}
