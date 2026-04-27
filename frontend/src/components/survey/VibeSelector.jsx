import { Check } from 'lucide-react'
import { motion } from 'framer-motion'
import { VIBES } from '../../utils/constants'

export default function VibeSelector({ selected, onToggle }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {VIBES.map((vibe) => {
        const active = selected.includes(vibe.key)
        return (
          <motion.button key={vibe.key} whileTap={{ scale: 0.98 }} onClick={() => onToggle(vibe.key)} className={`rounded-xl border p-4 text-left transition ${active ? 'border-accent bg-red-50' : 'border-slate-200 bg-white'}`}>
            <div className="text-2xl">{vibe.emoji}</div>
            <div className="mt-1 flex items-center justify-between text-sm font-semibold">
              {vibe.label}
              {active && <Check className="h-4 w-4 text-accent" />}
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}
