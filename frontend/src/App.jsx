import { AnimatePresence, motion } from 'framer-motion'
import { Route, Routes, useLocation } from 'react-router-dom'
import ErrorBoundary from './components/common/ErrorBoundary'
import Footer from './components/layout/Footer'
import Navbar from './components/layout/Navbar'
import AdminSpots from './pages/AdminSpots'
import CreateTrip from './pages/CreateTrip'
import EditProfile from './pages/EditProfile'
import Explore from './pages/Explore'
import Home from './pages/Home'
import Login from './pages/Login'
import MySpots from './pages/MySpots'
import NotFound from './pages/NotFound'
import Profile from './pages/Profile'
import Recommendations from './pages/Recommendations'
import Results from './pages/Results'
import ShareSpot from './pages/ShareSpot'
import SpotDetail from './pages/SpotDetail'
import Survey from './pages/Survey'
import TripCompanion from './pages/TripCompanion'
import TripDashboard from './pages/TripDashboard'
import Voting from './pages/Voting'
import Wrapped from './pages/Wrapped'

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
}

/** Wraps a page element in its own ErrorBoundary so one crash stays isolated. */
function Page({ children }) {
  return <ErrorBoundary>{children}</ErrorBoundary>
}

export default function App() {
  const location = useLocation()
  return (
    // Top-level boundary catches anything that slips through
    <ErrorBoundary>
      <div className="min-h-screen bg-slate-50">
        <Navbar />
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
                <Route path="/spots/share"          element={<Page><ShareSpot /></Page>} />
                <Route path="/spots/:spotId"        element={<Page><SpotDetail /></Page>} />
                <Route path="/spots/:spotId/edit"   element={<Page><ShareSpot /></Page>} />
                <Route path="/login"                element={<Page><Login /></Page>} />
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
