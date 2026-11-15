import { Compass, Gift, Lock, UserRound } from 'lucide-react'
import { Link, NavLink } from 'react-router-dom'
import useAuthStore from '../../store/authStore'

export default function Navbar() {
  const { token, user } = useAuthStore()
  const link = ({ isActive }) =>
    `inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-semibold ${isActive ? 'text-primary' : 'text-slate-500 hover:text-primary'}`

  return (
    <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-3 sm:px-6 lg:px-8">
        <Link to="/" className="text-xl font-bold text-primary">FlockGo</Link>
        <div className="flex items-center gap-1 sm:gap-2">
          <NavLink to="/explore" className={link}>
            <Compass className="h-4 w-4" /> <span className="hidden sm:inline">Explore</span>
          </NavLink>
          <NavLink to="/spots/share" className={link}>
            <Gift className="h-4 w-4" /> <span className="hidden sm:inline">Share a spot</span>
          </NavLink>
          {token ? (
            <NavLink to="/me" className={link}>
              <UserRound className="h-4 w-4" />
              <span className="inline-flex items-center gap-0.5 rounded-full bg-accent/10 px-2 py-0.5 text-xs text-accent">
                <Lock className="h-3 w-3" /> {user?.unlock_credits ?? 0}
              </span>
            </NavLink>
          ) : (
            <NavLink to="/login" className={link}>Log in</NavLink>
          )}
          <Link to="/create" className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:opacity-90 sm:px-4">
            Plan a trip
          </Link>
        </div>
      </nav>
    </header>
  )
}
