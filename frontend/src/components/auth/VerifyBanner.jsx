import { MailCheck } from 'lucide-react'
import { useState } from 'react'
import toast from 'react-hot-toast'
import { accountApi, useAuthConfig } from '../../services/authConfig'
import useAuthStore from '../../store/authStore'

/** "Confirm your email" strip, only when email is set up and the account isn't verified. */
export default function VerifyBanner() {
  const { token, user } = useAuthStore()
  const cfg = useAuthConfig()
  const [sent, setSent] = useState(false)
  if (!token || !user || user.email_verified !== false || !cfg?.email) return null
  async function resend() {
    try {
      await accountApi.resendVerify()
      setSent(true)
      toast.success('Sent! Check your inbox (and spam).')
    } catch (e) {
      toast.error(e.message)
    }
  }
  return (
    <div className="border-b border-amber-200 bg-amber-50">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-2 text-sm text-amber-800 sm:px-6 lg:px-8">
        <MailCheck className="h-4 w-4" />
        <span>Confirm your email ({user.email}) {cfg.require_email_verification ? 'to share spots' : 'to keep your account safe'}.</span>
        <button onClick={resend} disabled={sent} className="font-semibold underline disabled:no-underline disabled:opacity-60">
          {sent ? 'Link sent' : 'Send the link again'}
        </button>
      </div>
    </div>
  )
}
