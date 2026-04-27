import api from './api'

export const getRecommendations = (tripId) => api.get(`/trips/${tripId}/recommendations`).then((r) => r.data)
export const submitVote = (tripId, data) => api.post(`/trips/${tripId}/votes`, data).then((r) => r.data)
export const getVoteStatus = (tripId) => api.get(`/trips/${tripId}/votes/status`).then((r) => r.data)
export const getResults = (tripId) => api.get(`/trips/${tripId}/results`).then((r) => r.data)
