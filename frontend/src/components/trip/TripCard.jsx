import StatusBadge from './StatusBadge'

export default function TripCard({ trip }) {
  return (
    <div className="rounded-2xl bg-white p-6 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-primary">{trip?.name}</h1>
        <StatusBadge status={trip?.status} />
      </div>
      <p className="text-sm text-muted">Organizer: {trip?.organizer_name}</p>
      <p className="text-sm text-muted">When: {trip?.trip_month}, {trip?.duration_days} days</p>
    </div>
  )
}
