/**
 * Draws a 1080×1920 "FlockGo Wrapped" story card on a canvas, ready for
 * Instagram stories. Photos are drawn if they load (CORS-enabled API);
 * otherwise colourful tiles are used instead.
 */
import { photoSrc } from '../services/spotsService'

const W = 1080
const H = 1920
const FONT = '"Noto Sans", "Noto Sans Kannada", system-ui, sans-serif'

const TILE_COLORS = ['#f97316', '#0ea5e9', '#10b981', '#a855f7', '#eab308', '#ef4444', '#14b8a6', '#6366f1', '#ec4899']

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function cover(ctx, img, x, y, w, h) {
  const s = Math.max(w / img.width, h / img.height)
  const iw = img.width * s
  const ih = img.height * s
  ctx.drawImage(img, x + (w - iw) / 2, y + (h - ih) / 2, iw, ih)
}

function fitText(ctx, text, maxW, size, weight = 900) {
  let s = size
  do {
    ctx.font = `${weight} ${s}px ${FONT}`
    s -= 4
  } while (ctx.measureText(text).width > maxW && s > 24)
}

function stamp(ctx, cx, cy, r, label, sub, color) {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(-0.21)
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = 8
  ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.stroke()
  ctx.lineWidth = 3
  ctx.beginPath(); ctx.arc(0, 0, r - 14, 0, Math.PI * 2); ctx.stroke()
  ctx.textAlign = 'center'
  ctx.font = `900 ${r * 0.22}px ${FONT}`
  ctx.fillText('★ KA ★', 0, -r * 0.3)
  ctx.font = `900 ${r * 0.34}px ${FONT}`
  ctx.fillText(label, 0, r * 0.12)
  ctx.font = `800 ${r * 0.17}px ${FONT}`
  ctx.fillText(sub, 0, r * 0.45)
  ctx.restore()
}

async function draw(w, { withPhotos }) {
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')

  // Background
  const g = ctx.createLinearGradient(0, 0, W, H)
  g.addColorStop(0, '#0f2440')
  g.addColorStop(0.55, '#1e3a5f')
  g.addColorStop(1, '#c2410c')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, W, H)
  ctx.globalAlpha = 0.08
  ctx.strokeStyle = '#fff'
  ctx.lineWidth = 40
  ctx.beginPath(); ctx.arc(W - 60, 260, 240, 0, Math.PI * 2); ctx.stroke()
  ctx.beginPath(); ctx.arc(120, H - 260, 300, 0, Math.PI * 2); ctx.stroke()
  ctx.globalAlpha = 1

  // Header
  ctx.fillStyle = '#fcd34d'
  ctx.font = `800 34px ${FONT}`
  ctx.fillText('F L O C K G O   W R A P P E D', 80, 150)
  ctx.fillStyle = '#ffffff'
  fitText(ctx, w.period.label, 760, 120)
  ctx.fillText(w.period.label, 80, 290)
  ctx.font = `600 44px ${FONT}`
  ctx.fillStyle = 'rgba(255,255,255,0.8)'
  ctx.fillText(`${w.display_name}'s Karnataka`, 80, 360)

  stamp(ctx, W - 190, 250, 120, 'BEEN', `${w.stamps} STAMPS`, '#fcd34d')

  // Big stats
  const stats = [
    [String(w.stamps), w.stamps === 1 ? 'place stamped' : 'places stamped'],
    [`${w.km.toLocaleString('en-IN')} km`, 'between them'],
    [`${w.districts.length}`, `district${w.districts.length === 1 ? '' : 's'}${w.new_districts.length ? ` · ${w.new_districts.length} new` : ''}`],
  ]
  let y = 520
  for (const [big, small] of stats) {
    ctx.fillStyle = '#ffffff'
    ctx.font = `900 120px ${FONT}`
    ctx.fillText(big, 80, y)
    ctx.fillStyle = '#fcd34d'
    ctx.font = `700 40px ${FONT}`
    ctx.fillText(small, 80, y + 56)
    y += 210
  }

  // Personality
  roundRect(ctx, 60, 1110, W - 120, 190, 36)
  ctx.fillStyle = 'rgba(255,255,255,0.12)'
  ctx.fill()
  ctx.fillStyle = 'rgba(255,255,255,0.7)'
  ctx.font = `700 32px ${FONT}`
  ctx.fillText('YOUR TRAVEL PERSONALITY', 100, 1170)
  ctx.fillStyle = '#ffffff'
  fitText(ctx, w.personality.title, W - 200, 76)
  ctx.fillText(w.personality.title, 100, 1258)

  // Photo grid (up to 6)
  const tiles = w.top_places.slice(0, 6)
  const cols = 3
  const gap = 18
  const tw = (W - 120 - gap * (cols - 1)) / cols
  const th = 200
  for (let i = 0; i < tiles.length; i++) {
    const x = 60 + (i % cols) * (tw + gap)
    const ty = 1340 + Math.floor(i / cols) * (th + gap)
    ctx.save()
    roundRect(ctx, x, ty, tw, th, 28)
    ctx.clip()
    ctx.fillStyle = TILE_COLORS[i % TILE_COLORS.length]
    ctx.fillRect(x, ty, tw, th)
    const t = tiles[i]
    let drew = false
    if (withPhotos && t.trip_photo_url) {
      const img = await loadImage(photoSrc(t.trip_photo_url))
      if (img) { cover(ctx, img, x, ty, tw, th); drew = true }
    }
    const grad = ctx.createLinearGradient(0, ty + th * 0.4, 0, ty + th)
    grad.addColorStop(0, 'rgba(0,0,0,0)')
    grad.addColorStop(1, 'rgba(0,0,0,0.75)')
    ctx.fillStyle = grad
    ctx.fillRect(x, ty, tw, th)
    ctx.fillStyle = '#fff'
    fitText(ctx, t.name, tw - 36, drew ? 30 : 34, 800)
    ctx.fillText(t.name, x + 18, ty + th - 24)
    ctx.restore()
  }

  // Footer
  ctx.textAlign = 'center'
  if (w.top_percent) {
    ctx.fillStyle = '#fcd34d'
    ctx.font = `900 40px ${FONT}`
    ctx.fillText(`TOP ${w.top_percent}% OF EXPLORERS`, W / 2, H - 100)
  }
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  fitText(ctx, `flock-k-go.vercel.app/u/${w.username}`, W - 160, 32, 700)
  ctx.fillText(`flock-k-go.vercel.app/u/${w.username}`, W / 2, H - 48)
  ctx.textAlign = 'left'
  return canvas
}

/** Returns a PNG Blob. Falls back to no photos if an image taints the canvas. */
export async function makeWrappedImage(wrapped) {
  const toBlob = (c) => new Promise((resolve, reject) => {
    try {
      c.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not make the image'))), 'image/png')
    } catch (e) {
      reject(e)
    }
  })
  try {
    return await toBlob(await draw(wrapped, { withPhotos: true }))
  } catch {
    return toBlob(await draw(wrapped, { withPhotos: false }))
  }
}
