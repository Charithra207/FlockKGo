/**
 * Link previews for WhatsApp / Instagram / X / Telegram / Slack.
 * vercel.json sends only link-preview bots here (by user agent); people get
 * the normal app. We look up the profile or spot and return its title,
 * description and image as Open Graph tags.
 */
const SITE = 'https://flock-k-go.vercel.app'
const DEFAULT_IMAGE = `${SITE}/og-image.png`

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

async function api(path) {
  const base = (process.env.VITE_API_URL || '').replace(/\/$/, '')
  if (!base.startsWith('http')) return null
  try {
    const r = await fetch(base + path, {
      headers: process.env.VITE_API_KEY ? { 'X-API-Key': process.env.VITE_API_KEY } : {},
      signal: AbortSignal.timeout(6000),
    })
    return r.ok ? await r.json() : null
  } catch {
    return null
  }
}

function photo(url) {
  if (!url) return null
  if (url.startsWith('http')) return url
  const base = (process.env.VITE_API_URL || '').replace(/\/v1\/?$/, '')
  return base + url
}

async function describe(path) {
  let m = path.match(/^\/u\/([a-z0-9_]{3,30})\/wrapped/)
  if (m) {
    const year = new Date().getFullYear()
    const w = await api(`/users/${m[1]}/wrapped?year=${year}`)
    if (w) {
      return {
        title: `${w.display_name}'s ${w.period.label} FlockGo Wrapped`,
        description: `${w.stamps} places stamped, ${w.km} km, ${w.districts.length} districts. Travel personality: ${w.personality.title}.`,
        image: photo(w.top_places?.find((p) => p.trip_photo_url)?.trip_photo_url) || DEFAULT_IMAGE,
      }
    }
  }
  m = path.match(/^\/u\/([a-z0-9_]{3,30})\/?$/)
  if (m) {
    const p = await api(`/users/${m[1]}`)
    if (p && !p.private) {
      return {
        title: `${p.display_name} (@${p.username}) on FlockGo`,
        description: `${p.stats.been} places stamped across ${p.stats.districts_explored} of 31 Karnataka districts. ${p.bio || ''}`.trim(),
        image: photo(p.avatar_url) || DEFAULT_IMAGE,
      }
    }
    if (p) return { title: `${p.display_name} on FlockGo`, description: 'A Karnataka travel passport.', image: DEFAULT_IMAGE }
  }
  m = path.match(/^\/spots\/([0-9a-f-]{36})\/?$/)
  if (m) {
    const s = await api(`/spots/${m[1]}`)
    if (s) {
      const where = `${s.destination ? `${s.destination}, ` : ''}${s.district}`
      return s.locked
        ? { title: `A hidden ${s.category} near ${where}`, description: 'A local shared this hidden gem on FlockGo. Share a spot you love to unlock it.', image: DEFAULT_IMAGE }
        : { title: `${s.name} · ${where}`, description: (s.description || `A ${s.category} in ${s.district}, Karnataka.`).slice(0, 200), image: photo(s.photo_url) || DEFAULT_IMAGE }
    }
  }
  return null
}

export default async function handler(req, res) {
  const path = String(req.query.path || '/').split('?')[0]
  const d = (await describe(path)) || {
    title: 'FlockGo: Karnataka, by locals',
    description: 'Hidden spots shared by locals, group trips decided together, and your Karnataka travel passport.',
    image: DEFAULT_IMAGE,
  }
  const url = SITE + path
  res.setHeader('Content-Type', 'text/html; charset=utf-8')
  res.setHeader('Cache-Control', 'public, s-maxage=600, stale-while-revalidate=3600')
  res.status(200).send(`<!doctype html><html><head><meta charset="utf-8">
<title>${esc(d.title)}</title>
<meta name="description" content="${esc(d.description)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="FlockGo">
<meta property="og:url" content="${esc(url)}"><meta property="og:title" content="${esc(d.title)}">
<meta property="og:description" content="${esc(d.description)}"><meta property="og:image" content="${esc(d.image)}">
<meta name="twitter:card" content="summary_large_image">
</head><body><a href="${esc(url)}">${esc(d.title)}</a></body></html>`)
}
