import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/v1',
})

api.interceptors.request.use((config) => {
  if (import.meta.env.DEV) {
    console.info('[API]', config.method?.toUpperCase(), config.url)
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(new Error(error?.response?.data?.detail || error.message || 'Request failed')),
)

export default api
