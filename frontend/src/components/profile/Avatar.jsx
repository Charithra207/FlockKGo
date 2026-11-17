import { photoSrc } from '../../services/spotsService'

const GRADIENTS = [
  'from-orange-400 to-rose-500', 'from-emerald-400 to-teal-600', 'from-sky-400 to-indigo-600',
  'from-amber-300 to-orange-600', 'from-fuchsia-400 to-purple-600', 'from-lime-400 to-green-600',
]

function hash(s) {
  let h = 0
  for (const c of s || '') h = (h * 31 + c.charCodeAt(0)) | 0
  return Math.abs(h)
}

export default function Avatar({ user, size = 40, className = '' }) {
  const name = user?.display_name || user?.username || '?'
  const initials = name.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  const style = { width: size, height: size, fontSize: Math.round(size * 0.38) }
  if (user?.avatar_url) {
    return <img src={photoSrc(user.avatar_url)} alt="" style={style} className={`shrink-0 rounded-full object-cover ${className}`} />
  }
  return (
    <div
      style={style}
      className={`grid shrink-0 place-items-center rounded-full bg-gradient-to-br font-black text-white ${GRADIENTS[hash(user?.username || name) % GRADIENTS.length]} ${className}`}
    >
      {initials}
    </div>
  )
}
