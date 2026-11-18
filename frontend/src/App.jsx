import { AnimatePresence, motion } from 'framer-motion'
import { lazy, Suspense } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import LoadingSpinner from './components/common/LoadingSpinner'
import ErrorBoundary from './components/common/ErrorBoundary'
import Footer from './components/layout/Footer'
import Navbar from './components/layout/Navbar'
import VerifyBanner from './components/auth/VerifyBanner'
import Home from './pages/Home'
import NotFound from './pages/NotFound'

// Pages load on demand, so the first visit downloads much less.
const AdminSpots = lazy(() => import('./pages/AdminSpots'))
const ForgotPassword = lazy(() => import('./pages/AccountPages').then((m) => ({ default: m.ForgotPassword })))
const Privacy = lazy(() => import('./pages/AccountPages').then((m) => ({ default: m.Privacy })))
const ResetPassword = lazy(() => import('./pages/AccountPages').then((m) => ({ default: m.ResetPassword })))
const Terms = lazy(() => import('./pages/AccountPages').then((m) => ({ default: m.Terms })))
const VerifyEmail = lazy(() => import('./pages/AccountPages').then((m) => ({ default: m.VerifyEmail })))
const Collections = lazy(() => import('./pages/Collections'))
const CreateTrip = lazy(() => import('./pages/CreateTrip'))
const EditProfile = lazy(() => import('./pages/EditProfile'))
const Explore = lazy(() => import('./pages/Explore'))
const Login = lazy(() => import('./pages/Login'))
const MySpots = lazy(() => import('./pages/MySpots'))
const Profile = lazy(() => import('./pages/Profile'))
const Recommendations = lazy(() => import('./pages/Recommendations'))
const Results = lazy(() => import('./pages/Results'))
const ShareSpot = lazy(() => import('./pages/ShareSpot'))
const SpotDetail = lazy(() => import('./pages/SpotDetail'))
const Survey = lazy(() => import('./pages/Survey'))
const TripCompanion = lazy(() => import('./pages/TripCompanion'))
const TripDashboard = lazy(() => import('./pages/TripDashboard'))
const Voting = lazy(() => import('./pages/Voting'))
const Wrapped = lazy(() => import('./pages/Wrapped'))

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
}

/** Wraps a page element in its own ErrorBoundary so one crash stays isolated. */
function Page({ children }) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingSpinner message="Loading…" />}>{children}</Suspense>
    </ErrorBoundary>
  )
}

export default function App() {
  const location = useLocation()
  return (
    // Top-level boundary catches anything that slips through
    <ErrorBoundary>
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <VerifyBanner />
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              {...pageTransition}
              transition={{ duration: 0.25 }}
            >
              <Routes location={location}>
                <Route path="/"                     element={<Page><Home /></Page>} />
                <Route path="/create"               element={<Page><CreateTrip /></Page>} />
                <Route path="/trip/:tripId"         element={<Page><TripDashboard /></Page>} />
                <Route path="/survey/:token"        element={<Page><Survey /></Page>} />
                <Route path="/trip/:tripId/recs"    element={<Page><Recommendations /></Page>} />
                <Route path="/trip/:tripId/vote"    element={<Page><Voting /></Page>} />
                <Route path="/trip/:tripId/results" element={<Page><Results /></Page>} />
                <Route path="/trip/:tripId/plan"    element={<Page><TripCompanion /></Page>} />
                <Route path="/explore"              element={<Page><Explore /></Page>} />
                <Route path="/collections"          element={<Page><Collections /></Page>} />
                <Route path="/spots/share"          element={<Page><ShareSpot /></Page>} />
                <Route path="/spots/:spotId"        element={<Page><SpotDetail /></Page>} />
                <Route path="/spots/:spotId/edit"   element={<Page><ShareSpot /></Page>} />
                <Route path="/login"                element={<Page><Login /></Page>} />
                <Route path="/forgot-password"      element={<Page><ForgotPassword /></Page>} />
                <Route path="/reset-password"       element={<Page><ResetPassword /></Page>} />
                <Route path="/verify-email"         element={<Page><VerifyEmail /></Page>} />
                <Route path="/privacy"              element={<Page><Privacy /></Page>} />
                <Route path="/terms"                element={<Page><Terms /></Page>} />
                <Route path="/me"                   element={<Page><MySpots /></Page>} />
                <Route path="/admin/spots"          element={<Page><AdminSpots /></Page>} />
                <Route path="/u/:username"          element={<Page><Profile /></Page>} />
                <Route path="/u/:username/wrapped"  element={<Page><Wrapped /></Page>} />
                <Route path="/settings/profile"     element={<Page><EditProfile /></Page>} />
                <Route path="*"                     element={<NotFound />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </main>
        <Footer />
      </div>
    </ErrorBoundary>
  )
}
