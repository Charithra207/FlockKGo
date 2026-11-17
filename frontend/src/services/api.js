/**
 * api.js — Axios instance for all FlockGo API calls.
 *
 * AUTH HEADER INJECTION
 * ---------------------
 * Production deployments require an X-API-Key header on every request.
 * The key is read from the VITE_API_KEY environment variable at build time.
 *
 * In local dev (no VITE_API_KEY set), the header is omitted — the FastAPI
 * backend runs with API_SECRET_KEY unset, which disables auth enforcement.
 *
 * To set up for production:
 *   1. Add VITE_API_KEY=<your_flockgo_key> to the Vercel environment variables.
 *   2. The key is the raw "flockgo_..." string returned by POST /admin/api-keys.
 *
 * VITE_API_URL defaults to '/v1' so Vite's dev proxy forwards to localhost:8000.
 * In production, set VITE_API_URL to your Render web service URL (https://...).
 */

import axios from 'axios'
import useAuthStore from '../store/authStore'

const API_BASE = import.meta.env.VITE_API_URL || '/v1'

const api = axios.create({
  baseURL: API_BASE,
  // The free Render server sleeps when idle and needs ~50 s to wake up,
  // so allow 90 s before giving up.
  timeout: 90_000,
})

/**
 * Wake the API as soon as the site opens, so it's awake by the time the
 * user clicks anything. /health doesn't touch the database.
 */
export function wakeApi() {
  const healthUrl = API_BASE.replace(/\/v1\/?$/, '') + '/health'
  fetch(healthUrl, { cache: 'no-store' }).catch(() => {})
}

// ── Request interceptor: inject auth + debug logging ─────────────────────────
api.interceptors.request.use((config) => {
  // Attach API key if configured — required in production
  const apiKey = import.meta.env.VITE_API_KEY
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
  }
  // Logged-in account (spots: share / unlock / vouch)
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  if (import.meta.env.DEV) {
    console.info(
      '[API]',
      config.method?.toUpperCase(),
      config.url,
      apiKey ? '🔑 authed' : '🔓 open',
    )
  }

  return config
})

// ── Response interceptor: normalise FastAPI error shapes ─────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const detail = error?.response?.data?.detail

    let message
    if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail)) {
      // FastAPI 422 validation errors — join field names + messages
      message = detail
        .map((e) => `${e.loc?.slice(-1)[0] ?? 'field'}: ${e.msg}`)
        .join(', ')
    } else if (detail && typeof detail === 'object') {
      message = JSON.stringify(detail)
    } else if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
      message = 'The server is waking up (free hosting sleeps when idle). Please try again in a few seconds.'
    } else if (!error?.response) {
      message = 'Could not reach the server. Check your internet and try again.'
    } else {
      message = error.message || 'Request failed'
    }

    const usedUserToken = Boolean(error?.config?.headers?.Authorization)
    if ((status === 401 || status === 403) && /API key/i.test(message)) {
      // Client API key problem (X-API-Key) — a deployment config issue.
      message = `Auth error (${status}): ${message}. Check VITE_API_KEY is set correctly.`
    } else if (status === 401 && usedUserToken) {
      // Expired / invalid login: drop it so the UI shows "Log in" again.
      useAuthStore.getState().logout()
      message = 'Your session expired. Please log in again.'
    }

    const err = new Error(message)
    err.status = status
    return Promise.reject(err)
  },
)

export default api
