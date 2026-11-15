import api from './api'

const get = (url, params) => api.get(url, { params }).then((r) => r.data)

export const companionApi = {
  dashboard: (tripId) => get(`/trips/${tripId}/dashboard`),

  checklist: (tripId) => get(`/trips/${tripId}/checklist`),
  suggestChecklist: (tripId) => api.post(`/trips/${tripId}/checklist/suggest`).then((r) => r.data),
  addItem: (tripId, body) => api.post(`/trips/${tripId}/checklist`, body).then((r) => r.data),
  patchItem: (tripId, itemId, body) => api.patch(`/trips/${tripId}/checklist/${itemId}`, body).then((r) => r.data),
  deleteItem: (tripId, itemId) => api.delete(`/trips/${tripId}/checklist/${itemId}`).then((r) => r.data),

  expenses: (tripId) => get(`/trips/${tripId}/expenses`),
  addExpense: (tripId, body) => api.post(`/trips/${tripId}/expenses`, body).then((r) => r.data),
  deleteExpense: (tripId, id) => api.delete(`/trips/${tripId}/expenses/${id}`).then((r) => r.data),
  settlement: (tripId) => get(`/trips/${tripId}/expenses/settlement`),

  itinerary: (tripId) => get(`/trips/${tripId}/itinerary`),
  travelOptions: (tripId, travel_date) => get(`/trips/${tripId}/travel-options`, travel_date ? { travel_date } : undefined),
  sos: (tripId) => get(`/trips/${tripId}/sos`),
}

export const inr = (n) => `₹${Number(n || 0).toLocaleString('en-IN')}`
