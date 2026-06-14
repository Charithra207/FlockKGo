import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="border-t bg-white py-6 text-center text-sm text-slate-400">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 sm:flex-row sm:justify-between sm:px-6 lg:px-8">
        <Link to="/" className="font-semibold text-primary">
          FlockGo 🐦
        </Link>
        <p>Group travel, decided by AI.</p>
      </div>
    </footer>
  )
}
