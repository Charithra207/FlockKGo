import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.jsx'
import { useLang } from './i18n'
import { wakeApi } from './services/api'

wakeApi()

if (import.meta.env.PROD) {
  // Installable app + offline copies of places you've opened
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}))
  }
  // Page-view analytics (switch on "Web Analytics" in the Vercel project to collect)
  import('@vercel/analytics').then(({ inject }) => inject()).catch(() => {})
  // Error tracking, only when VITE_SENTRY_DSN is set (loaded on demand)
  if (import.meta.env.VITE_SENTRY_DSN) {
    import('@sentry/react').then((Sentry) => Sentry.init({
      dsn: import.meta.env.VITE_SENTRY_DSN,
      sendDefaultPii: false,
      tracesSampleRate: 0.05,
    })).catch(() => {})
  }
}

try { document.documentElement.lang = useLang.getState().lang } catch { /* ignore */ }

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
      <Toaster position="top-right" />
    </BrowserRouter>
  </StrictMode>,
)
