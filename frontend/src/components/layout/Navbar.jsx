import { Link } from 'react-router-dom'

export default function Navbar() {
  return (
    <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <Link to="/" className="text-xl font-bold text-primary">FlockGo</Link>
        <Link to="/create" className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-90">Start Planning</Link>
      </nav>
    </header>
  )
}
