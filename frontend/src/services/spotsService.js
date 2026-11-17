import api from './api'
import { MONTHS_KN, translate, useLang } from '../i18n'

export const authApi = {
  register: (body) => api.post('/auth/register', body).then((r) => r.data),
  login: (body) => api.post('/auth/login', body).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
}

export const spotsApi = {
  meta: () => api.get('/spots/meta').then((r) => r.data),
  list: (params) => api.get('/spots', { params }).then((r) => r.data),
  get: (id) => api.get(`/spots/${id}`).then((r) => r.data),
  mine: () => api.get('/spots/mine').then((r) => r.data),
  submit: (body) => api.post('/spots', body).then((r) => r.data),
  edit: (id, body) => api.patch(`/spots/${id}`, body).then((r) => r.data),
  uploadPhoto: (blob) => {
    const fd = new FormData()
    fd.append('file', blob, 'photo.jpg')
    return api.post('/photos', fd, { timeout: 60_000 }).then((r) => r.data)
  },
  unlock: (id) => api.post(`/spots/${id}/unlock`).then((r) => r.data),
  vouch: (id) => api.post(`/spots/${id}/vouch`).then((r) => r.data),
  pending: () => api.get('/admin/spots/pending').then((r) => r.data),
  review: (id, action, note) =>
    api.post(`/admin/spots/${id}/review`, { action, note }).then((r) => r.data),
}

export const CATEGORY_META = {
  cafe: { label: 'Cafe', emoji: '☕' },
  viewpoint: { label: 'Viewpoint', emoji: '🌄' },
  waterfall: { label: 'Waterfall', emoji: '💧' },
  trek: { label: 'Trek', emoji: '🥾' },
  beach: { label: 'Beach', emoji: '🏖️' },
  lake: { label: 'Lake', emoji: '🏞️' },
  temple: { label: 'Temple', emoji: '🛕' },
  heritage: { label: 'Heritage', emoji: '🏛️' },
  food: { label: 'Local food', emoji: '🍛' },
  stay: { label: 'Stay', emoji: '🏡' },
  wildlife: { label: 'Wildlife', emoji: '🐘' },
  other: { label: 'Other', emoji: '📍' },
}

export const SAFETY_META = {
  monsoon_danger: { emoji: '🌊', label: 'Dangerous in monsoon', tip: 'Strong currents and flash floods from June to September. Stay well back from the water.' },
  slippery: { emoji: '⚠️', label: 'Slippery rocks', tip: 'Wear shoes with grip. Moss makes rocks very slippery.' },
  steep: { emoji: '⛰️', label: 'Steep climb', tip: 'Steep or exposed path. Not for small kids or after dark.' },
  no_swimming: { emoji: '🚫', label: 'No swimming', tip: 'Deep or fast water. Do not enter.' },
  no_network: { emoji: '📵', label: 'No phone network', tip: 'Tell someone your plan and download offline maps first.' },
  forest_permission: { emoji: '🌳', label: 'Forest permission needed', tip: 'Inside a forest or reserve: entry may need a permit and is often closed in monsoon.' },
  wildlife: { emoji: '🐘', label: 'Wildlife area', tip: 'Elephants and bison move here. Keep quiet, keep distance, leave before dusk.' },
  private_property: { emoji: '🏡', label: 'Private land nearby', tip: 'Ask before entering estates or farms.' },
  no_facilities: { emoji: '🚻', label: 'No food or toilets', tip: 'Carry water and snacks, and bring your trash back.' },
}

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const lang = () => useLang.getState().lang

export function catName(c) {
  return translate(lang(), `cat.${CATEGORY_META[c] ? c : 'other'}`)
}

export function categoryLabel(c) {
  const m = CATEGORY_META[c] || CATEGORY_META.other
  return `${m.emoji} ${catName(c)}`
}

export function monthNames() {
  return lang() === 'kn' ? MONTHS_KN : MONTHS
}

/** Locked spots get a generic title; build it in the viewer's language. */
export function spotTitle(spot) {
  if (!spot.locked) {
    // In Kannada mode, use the Kannada name when the map data has one.
    const kn = spot.extra?.['name:kn']
    return lang() === 'kn' && kn ? kn : spot.name
  }
  return translate(lang(), 'card.hiddenName', { cat: catName(spot.category), place: spot.destination || spot.district })
}

export function directionsUrl(lat, lng) {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
}

/** Uploaded photos are served by the API (/v1/photos/<id>); resolve against its origin. */
export function photoSrc(url) {
  if (!url) return null
  if (!url.startsWith('/v1/')) return url
  const base = import.meta.env.VITE_API_URL || ''
  return base.startsWith('http') ? new URL(base).origin + url : url
}

/** Shrink a photo in the browser to max 1600px JPEG (~200 KB) before upload. */
export async function resizeImage(file, maxSide = 1600, quality = 0.82) {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close?.()
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not read that image'))), 'image/jpeg', quality),
  )
}
