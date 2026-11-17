import { Link } from 'react-router-dom'
import { useT } from '../../i18n'

export default function Footer() {
  const t = useT()
  return (
    <footer className="border-t bg-white py-6 text-center text-sm text-slate-400">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 sm:flex-row sm:justify-between sm:px-6 lg:px-8">
        <Link to="/" className="font-semibold text-primary">
          FlockGo 🐦
        </Link>
        <p>{t('footer.tag')}</p>
        <p className="flex flex-wrap items-center justify-center gap-x-3 text-xs">
          <Link to="/privacy" className="underline">Privacy</Link>
          <Link to="/terms" className="underline">Terms</Link>
          <span>Map data ©{' '}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="underline">
            OpenStreetMap contributors
          </a></span>
        </p>
      </div>
    </footer>
  )
}
