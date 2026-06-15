import { AnimatePresence, motion } from 'framer-motion'
import { Route, Routes, useLocation } from 'react-router-dom'
import ErrorBoundary from './components/common/ErrorBoundary'
import Footer from './components/layout/Footer'
import Navbar from './components/layout/Navbar'
import CreateTrip from './pages/CreateTrip'
import Home from './pages/Home'
import NotFound from './pages/NotFound'
import Recommendations from './pages/Recommendations'
import Results from './pages/Results'
import Survey from './pages/Survey'
import TripDashboard from './pages/TripDashboard'
import Voting from './pages/Voting'

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
