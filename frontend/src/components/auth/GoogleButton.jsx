import { useEffect, useRef } from 'react'
import toast from 'react-hot-toast'
import { accountApi, loadScript, useAuthConfig } from '../../services/authConfig'

/** "Sign in with Google". Renders nothing until GOOGLE_CLIENT_ID is set on the server. */
export default function GoogleButton({ onSession }) {
  const cfg = useAuthConfig()
  const box = useRef(null)
  const clientId = cfg?.google_client_id
  useEffect(() => {
    if (!clientId) return
    loadScript('https://accounts.google.com/gsi/client').then(() => {
      if (!box.current || !window.google?.accounts?.id) return
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async ({ credential }) => {
          try {
            onSession(await accountApi.google(credential))
          } catch (e) {
            toast.error(e.message)
          }
        },
      })
      window.google.accounts.id.renderButton(box.current, {
        theme: 'outline', size: 'large', shape: 'pill', text: 'continue_with', width: 320,
      })
    }).catch(() => {})
  }, [clientId]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!clientId) return null
  return (
    <div className="space-y-3">
      <div ref={box} className="flex justify-center" />
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <span className="h-px flex-1 bg-slate-200" /> or with email <span className="h-px flex-1 bg-slate-200" />
      </div>
    </div>
  )
}
