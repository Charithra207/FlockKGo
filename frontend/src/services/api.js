import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/v1',
})

api.interceptors.request.use((config) => {
  if (import.meta.env.DEV) {
    console.info('[API]', config.method?.toUpperCase(), config.url)
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error?.response?.data?.detail
    let message
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail)) {
      // FastAPI validation errors — extract readable message
      message = detail.map((e) => `${e.loc?.slice(-1)[0] ?? 'field'}: ${e.msg}`).join(', ')
    } else if (detail && typeof detail === 'object') {
      message = JSON.stringify(detail)
    } else {
      message = error.message || 'Request failed'
    }
    return Promise.reject(new Error(message))
  },
)

export default api
