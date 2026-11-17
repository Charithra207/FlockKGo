import { motion } from 'framer-motion'
import { Plane } from 'lucide-react'

/**
 * The two "marks", styled like real travel documents instead of ticks:
 *   been → an ink passport stamp that thunks down onto the card
 *   want → a little boarding pass for your bucket list
 */

export function shortDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' }).toUpperCase()
  } catch {
    return ''
  }
}

/**
 * tone: 'ink' (orange ink, for light backgrounds) | 'light' (for photos / dark cards)
 * verified: photo taken at the place → gold VERIFIED stamp
 */
export function PassportStamp({ date, size = 'md', animate = true, verified = false, tone = 'ink', className = '' }) {
  const big = size === 'lg'
  const sm = size === 'sm'
  const toneClass = verified ? (tone === 'light' ? 'stamp-gold-light' : 'stamp-gold') : tone === 'light' ? 'stamp-light' : 'stamp-ink'
  return (
    <motion.div
      initial={animate ? { scale: 1.8, opacity: 0, rotate: -24 } : false}
      animate={{ scale: 1, opacity: 1, rotate: -12 }}
      transition={{ type: 'spring', stiffness: 420, damping: 18 }}
      className={`${toneClass} pointer-events-none select-none ${className}`}
      aria-label={verified ? 'Visited (photo verified)' : 'Visited'}
    >
      <div
        className={`flex flex-col items-center rounded-full border-[3px] border-double border-current text-center font-black uppercase leading-none ${tone === 'light' ? 'bg-slate-900/45 backdrop-blur-[2px]' : ''} ${
          big ? 'h-24 w-24 justify-center gap-1 text-sm' : sm ? 'h-11 w-11 justify-center text-[7px]' : 'h-16 w-16 justify-center gap-0.5 text-[10px]'
        }`}
      >
        <span className={`tracking-[0.2em] ${sm ? 'hidden' : ''}`}>★ KA ★</span>
        <span className={`tracking-widest ${big ? 'text-base' : sm ? 'text-[8px]' : 'text-xs'}`}>{verified ? (sm ? '✓' : 'VERIFIED') : 'BEEN'}</span>
        {!sm && <span className="text-[8px] font-bold tracking-wider opacity-80">{shortDate(date) || 'THERE'}</span>}
      </div>
    </motion.div>
  )
}

export function BoardingPass({ size = 'md', animate = true, className = '' }) {
  const sm = size === 'sm'
  return (
    <motion.div
      initial={animate ? { y: -14, opacity: 0, rotate: 0 } : false}
      animate={{ y: 0, opacity: 1, rotate: 4 }}
      transition={{ type: 'spring', stiffness: 380, damping: 20 }}
      className={`ticket pointer-events-none select-none ${className}`}
      aria-label="On my bucket list"
    >
      <div className={`flex items-center gap-1.5 font-black uppercase tracking-wider ${sm ? 'px-2 py-1 text-[8px]' : 'px-3 py-1.5 text-[10px]'}`}>
        <Plane className={sm ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        <span className="border-l border-dashed border-amber-300/60 pl-1.5">{sm ? 'SOON' : 'BUCKET LIST'}</span>
      </div>
    </motion.div>
  )
}
