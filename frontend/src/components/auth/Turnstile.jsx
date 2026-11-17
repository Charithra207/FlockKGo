import { useEffect, useRef } from 'react'
import { loadScript, useAuthConfig } from '../../services/authConfig'

/** Cloudflare "I'm human" check. Renders nothing unless the server has it switched on. */
export default function Turnstile({ onToken }) {
  const cfg = useAuthConfig()
  const box = useRef(null)
  const siteKey = cfg?.captcha_site_key
  useEffect(() => {
    if (!siteKey || !box.current) return
    let id
    loadScript('https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit').then(() => {
      if (!box.current || !window.turnstile) return
      id = window.turnstile.render(box.current, {
        sitekey: siteKey,
        callback: (t) => onToken(t),
        'expired-callback': () => onToken(null),
      })
    }).catch(() => {})
    return () => { if (id && window.turnstile) window.turnstile.remove(id) }
  }, [siteKey]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!siteKey) return null
  return <div ref={box} className="min-h-[65px]" />
}

/** Hidden field people never see; simple bots fill it in. */
export function Honeypot({ value, onChange }) {
  return (
    <input
      type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true"
      value={value} onChange={(e) => onChange(e.target.value)}
      style={{ position: 'absolute', left: '-10000px', width: 1, height: 1, opacity: 0 }}
    />
  )
}
