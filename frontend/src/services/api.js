/**
 * api.js — Axios instance for all PackVote+ API calls.
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

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/v1',
  // Timeout after 30 s — prevents hung requests during ML pipeline polling
  timeout: 30_000,
})

// ── Request interceptor: inject auth + debug logging ─────────────────────────
api.interceptors.request.use((config) => {
  // Attach API key if configured — required in production
  const apiKey = import.meta.env.VITE_API_KEY
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
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
    } else {
      message = error.message || 'Request failed'
    }

    // Surface auth failures clearly so developers know to check VITE_API_KEY
    if (status === 401 || status === 403) {
      message = `Auth error (${status}): ${message}. Check VITE_API_KEY is set correctly.`
    }

    return Promise.reject(new Error(message))
  },
)

export default api
