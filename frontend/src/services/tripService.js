import api from './api'

export const createTrip = (data) => api.post('/trips', data).then((r) => r.data)
export const getTrip = (tripId) => api.get(`/trips/${tripId}`).then((r) => r.data)
export const getTripSummary = (tripId) => api.get(`/trips/${tripId}/summary`).then((r) => r.data)
export const addParticipant = (tripId, data) => api.post(`/trips/${tripId}/participants`, data).then((r) => r.data)
export const getParticipants = (tripId) => api.get(`/trips/${tripId}/participants`).then((r) => r.data?.participants ?? r.data)
export const runAnalysis = (tripId) => api.post(`/trips/${tripId}/run-analysis`).then((r) => r.data)
export const getAnalysisStatus = (tripId) => api.get(`/trips/${tripId}/analysis`).then((r) => r.data)

