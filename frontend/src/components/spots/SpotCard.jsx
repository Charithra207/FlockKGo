import { Lock, MapPin, ShieldCheck, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { catName, CATEGORY_META, photoSrc, spotTitle } from '../../services/spotsService'
import { categoryColor } from './SpotMap'
import { useT } from '../../i18n'

export default function SpotCard({ spot }) {
  const meta = CATEGORY_META[spot.category] || CATEGORY_META.other
  const t = useT()
  return (
    <Link
      to={`/spots/${spot.id}`}
      className="group flex flex-col gap-2 rounded-2xl bg-white p-4 shadow-card transition-shadow hover:shadow-md"
    >
      {!spot.locked && spot.photo_url && (
        <img src={photoSrc(spot.photo_url)} alt="" loading="lazy" className="-mx-4 -mt-4 mb-1 h-36 w-[calc(100%+2rem)] max-w-none rounded-t-2xl object-cover" />
      )}
      <div className="flex items-center justify-between gap-2">
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
          style={{ backgroundColor: categoryColor(spot.category) }}
        >
          {meta.emoji} {catName(spot.category)}
        </span>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          {spot.featured && (
            <span className="inline-flex items-center gap-0.5 font-semibold text-amber-600">
              <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" /> {t('card.famous')}
            </span>
          )}
          {spot.vouch_count > 0 && (
            <span className="inline-flex items-center gap-0.5">
              <ShieldCheck className="h-3.5 w-3.5 text-success" /> {spot.vouch_count}
            </span>
          )}
        </div>
      </div>

      <h3 className="flex items-center gap-1.5 font-bold leading-snug text-slate-800 group-hover:text-primary">
        {spot.locked && <Lock className="h-4 w-4 shrink-0 text-accent" />}
        <span className={spot.locked ? 'italic text-slate-500' : ''}>{spotTitle(spot)}</span>
      </h3>

      <p className="flex items-center gap-1 text-sm text-slate-500">
        <MapPin className="h-3.5 w-3.5 shrink-0" />
        {spot.destination ? `${spot.destination}, ` : ''}{spot.district}
        {spot.distance_km != null && <span className="ml-auto text-xs">{spot.distance_km} km</span>}
      </p>

      {!spot.locked && spot.description && (
        <p className="line-clamp-2 text-sm text-slate-500">{spot.description}</p>
      )}
      {spot.locked && (
        <p className="text-xs font-medium text-accent">{t('card.unlockHint')}</p>
      )}
    </Link>
  )
}
