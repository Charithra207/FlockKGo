import { motion } from 'framer-motion'
import { Bird, ListTodo, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Home() {
  const steps = [
    { icon: <Bird />, title: 'Create your trip & invite your flock' },
    { icon: <ListTodo />, title: 'Everyone shares their travel vibe' },
    { icon: <Sparkles />, title: 'AI picks the perfect destination' },
  ]
  return (
    <div className="space-y-14">
      <section className="rounded-3xl bg-white p-10 text-center shadow-card">
        <motion.div animate={{ y: [0, -8, 0] }} transition={{ repeat: Infinity, duration: 2 }} className="text-5xl">🐦</motion.div>
        <h1 className="mt-3 text-4xl font-bold text-primary md:text-5xl">Stop the group chat chaos.</h1>
        <p className="mx-auto mt-4 max-w-2xl text-muted">FlockGo uses AI to decide where your crew goes.</p>
        <Link to="/create" className="mt-6 inline-block rounded-xl bg-accent px-6 py-3 font-semibold text-white">Start Planning</Link>
      </section>
      <section className="grid gap-4 md:grid-cols-3">
        {steps.map((s, idx) => (
          <div key={s.title} className="rounded-2xl bg-white p-6 shadow-card">
            <p className="mb-2 text-primary">{s.icon}</p>
            <p className="text-sm font-semibold text-slate-600">Step {idx + 1}</p>
            <h3 className="font-bold">{s.title}</h3>
          </div>
        ))}
      </section>
    </div>
  )
}
