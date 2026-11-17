import { useEffect, useState } from 'react'
import api from './api'

let cached = null
let pending = null

/** Which optional features the server has switched on (Google, email, captcha). */
export function loadAuthConfig() {
  if (cached) return Promise.resolve(cached)
  if (!pending) {
    pending = api.get('/auth/config')
      .then((r) => (cached = r.data))
      .catch(() => (cached = { email: false, google_client_id: null, captcha_site_key: null }))
  }
  return pending
}

export function useAuthConfig() {
  const [cfg, setCfg] = useState(cached)
  useEffect(() => { loadAuthConfig().then(setCfg) }, [])
  return cfg
}

export const accountApi = {
  forgot: (email) => api.post('/auth/forgot', { email }).then((r) => r.data),
  reset: (token, password) => api.post('/auth/reset', { token, password }).then((r) => r.data),
  verify: (token) => api.post('/auth/verify', { token }).then((r) => r.data),
  resendVerify: () => api.post('/auth/verify/send').then((r) => r.data),
  google: (credential) => api.post('/auth/google', { credential }).then((r) => r.data),
  adminResetLink: (email) => api.post('/auth/admin/reset-link', { email }).then((r) => r.data),
}

const scripts = {}
export function loadScript(src) {
  if (!scripts[src]) {
    scripts[src] = new Promise((resolve, reject) => {
      const el = document.createElement('script')
      el.src = src
      el.async = true
      el.onload = resolve
      el.onerror = () => reject(new Error('Could not load ' + src))
      document.head.appendChild(el)
    })
  }
  return scripts[src]
}
