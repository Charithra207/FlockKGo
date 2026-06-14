import { motion } from 'framer-motion'
import { Bird, ListTodo, Sparkles, ArrowRight } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'

const STORAGE_KEY = 'flockgo_recent_trips'

/** Persist a trip id+name so the home page can show recent trips. */
export function saveRecentTrip(id, name) {
  try {
    const existing = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    const updated = [{ id, name }, ...existing.filter((t) => t.id !== id)].slice(0, 5)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
  } catch {
    // localStorage unavailable — silently ignore
  }
}

function RecentTrips() {
  const [trips, setTrips] = useState([])

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
      setTrips(stored)
    } catch {
      setTrips([])
    }
  }, [])

  if (trips.length === 0) return null

  return (
    <section>
      <h2 className="mb-3 text-lg font-bold text-slate-700">Recent Trips</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {trips.map((t) => (
          <Link
            key={t.id}
            to={`/trip/${t.id}`}
            className="flex items-center justify-between rounded-2xl bg-white px-5 py-4 shadow-card hover:shadow-md transition-shadow"
          >
            <span className="truncate font-medium text-slate-700">{t.name}</span>
            <ArrowRight className="ml-2 h-4 w-4 shrink-0 text-slate-400" />
          </Link>
        ))}
      </div>
    </section>
  )
}

export default function Home() {
  const navigate = useNavigate()

  const steps = [
    { icon: <Bird className="h-6 w-6" />, title: 'Create your trip & invite your flock' },
    { icon: <ListTodo className="h-6 w-6" />, title: 'Everyone shares their travel vibe' },
    { icon: <Sparkles className="h-6 w-6" />, title: 'AI picks the perfect destination' },
  ]

  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="rounded-3xl bg-white p-10 text-center shadow-card">
        <motion.div
          animate={{ y: [0, -8, 0] }}
          transition={{ repeat: Infinity, duration: 2.5, ease: 'easeInOut' }}
          className="text-6xl"
          aria-hidden="true"
        >
          🐦
        </motion.div>
        <h1 className="mt-4 text-4xl font-extrabold text-primary md:text-5xl">
          Stop the group chat chaos.
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-slate-500">
          FlockGo uses AI and ranked-choice voting to decide where your crew goes — no arguments, no spreadsheets.
        </p>
        <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <button
            onClick={() => navigate('/create')}
            className="rounded-xl bg-accent px-7 py-3 font-semibold text-white hover:opacity-90 transition-opacity"
          >
            Start Planning
          </button>
          <a
            href="#how-it-works"
            className="text-sm font-medium text-primary underline-offset-2 hover:underline"
          >
            How it works
          </a>
        </div>
      </section>

      {/* Recent trips — only visible if localStorage has data */}
      <RecentTrips />

      {/* How it works */}
      <section id="how-it-works">
        <h2 className="mb-4 text-center text-lg font-bold text-slate-600 uppercase tracking-wide text-xs">
          How it works
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {steps.map((s, idx) => (
            <div
              key={s.title}
              className="rounded-2xl bg-white p-6 shadow-card"
            >
              <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                {s.icon}
              </div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Step {idx + 1}
              </p>
              <h3 className="font-bold text-slate-700">{s.title}</h3>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
