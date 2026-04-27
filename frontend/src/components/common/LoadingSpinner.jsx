export default function LoadingSpinner({ message = 'Loading flock data...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-10">
      <div className="text-4xl animate-pulse">🐦</div>
      <div className="mt-3 h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      <p className="mt-3 text-sm text-muted">{message}</p>
    </div>
  )
}
