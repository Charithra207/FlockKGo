import api from './api'

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

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function categoryLabel(c) {
  const m = CATEGORY_META[c] || CATEGORY_META.other
  return `${m.emoji} ${m.label}`
}

export function directionsUrl(lat, lng) {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
}
