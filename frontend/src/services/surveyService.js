import api from './api'

export const getSurveyInfo = (token) => api.get(`/survey/${token}`).then((r) => r.data)
export const submitSurvey = (token, data) => api.post(`/survey/${token}/submit`, data).then((r) => r.data)
export const getSurveyStatus = (tripId) => api.get(`/trips/${tripId}/survey-status`).then((r) => r.data)
