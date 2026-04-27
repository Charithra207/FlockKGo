import { AnimatePresence, motion } from 'framer-motion'
import { Route, Routes, useLocation } from 'react-router-dom'
import ErrorBoundary from './components/common/ErrorBoundary'
import Footer from './components/layout/Footer'
import Navbar from './components/layout/Navbar'
import CreateTrip from './pages/CreateTrip'
import Home from './pages/Home'
import Recommendations from './pages/Recommendations'
import Results from './pages/Results'
import Survey from './pages/Survey'
import TripDashboard from './pages/TripDashboard'
import Voting from './pages/Voting'

const pageTransition = { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -12 } }

export default function App() {
  const location = useLocation()
  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
          <AnimatePresence mode="wait">
            <motion.div key={location.pathname} {...pageTransition} transition={{ duration: 0.25 }}>
              <Routes location={location}>
                <Route path="/" element={<Home />} />
                <Route path="/create" element={<CreateTrip />} />
                <Route path="/trip/:tripId" element={<TripDashboard />} />
                <Route path="/survey/:token" element={<Survey />} />
                <Route path="/trip/:tripId/recs" element={<Recommendations />} />
                <Route path="/trip/:tripId/vote" element={<Voting />} />
                <Route path="/trip/:tripId/results" element={<Results />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </main>
        <Footer />
      </div>
    </ErrorBoundary>
  )
}
