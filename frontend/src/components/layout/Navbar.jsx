import { Compass, Gift, LogIn, Lock, ShieldCheck, UserRound } from 'lucide-react'
import { useEffect } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useLang, useT } from '../../i18n'
import { authApi } from '../../services/spotsService'
import useAuthStore from '../../store/authStore'

export default function Navbar() {
  const { token, user, setUser } = useAuthStore()

  // Refresh credits / admin status once per page load.
  useEffect(() => {
    if (token) authApi.me().then(setUser).catch(() => {})
  }, [token, setUser])

  const t = useT()
  const { lang, setLang } = useLang()
  const link = ({ isActive }) =>
    `inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-semibold ${isActive ? 'text-primary' : 'text-slate-500 hover:text-primary'}`

  return (
    <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-3 sm:px-6 lg:px-8">
        <Link to="/" className="text-xl font-bold text-primary">FlockGo</Link>
        <div className="flex items-center gap-1 sm:gap-2">
          <NavLink to="/explore" className={link}>
            <Compass className="h-4 w-4" /> <span className="hidden sm:inline">{t('nav.explore')}</span>
          </NavLink>
          <NavLink to="/spots/share" className={link}>
            <Gift className="h-4 w-4" /> <span className="hidden sm:inline">{t('nav.share')}</span>
          </NavLink>
          {token && user?.is_admin && (
            <NavLink to="/admin/spots" className={link} title="Review spots">
              <ShieldCheck className="h-4 w-4" /> <span className="hidden md:inline">Admin</span>
            </NavLink>
          )}
          {token ? (
            <NavLink to="/me" className={link} title="My account">
              <UserRound className="h-4 w-4" />
              <span className="hidden max-w-[8rem] truncate md:inline">{user?.display_name || 'Me'}</span>
              <span className="inline-flex items-center gap-0.5 rounded-full bg-accent/10 px-2 py-0.5 text-xs text-accent" title="Unlock credits">
                <Lock className="h-3 w-3" /> {user?.unlock_credits ?? 0}
              </span>
            </NavLink>
          ) : (
            <NavLink
              to="/login"
              className="inline-flex items-center gap-1.5 rounded-lg border-2 border-primary px-3 py-1.5 text-sm font-semibold text-primary hover:bg-primary hover:text-white"
            >
              <LogIn className="h-4 w-4" /> {t('nav.login')}
            </NavLink>
          )}
          <button
            onClick={() => setLang(lang === 'kn' ? 'en' : 'kn')}
            className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold text-slate-600 hover:border-primary hover:text-primary"
            aria-label="Switch language"
          >
            {lang === 'kn' ? 'EN' : 'ಕನ್ನಡ'}
          </button>
          <Link to="/create" className="hidden rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:opacity-90 sm:inline-block sm:px-4">
            {t('nav.plan')}
          </Link>
        </div>
      </nav>
    </header>
  )
}
