import { create } from 'zustand'

const useTripStore = create((set) => ({
  currentTrip: null,
  participants: [],
  recommendations: [],
  analysisStatus: 'not_started',
  setCurrentTrip: (trip) => set({ currentTrip: trip }),
  addParticipant: (participant) => set((s) => ({ participants: [...s.participants, participant] })),
  setParticipants: (participants) => set({ participants }),
  setRecommendations: (recommendations) => set({ recommendations }),
  setAnalysisStatus: (analysisStatus) => set({ analysisStatus }),
  reset: () => set({ currentTrip: null, participants: [], recommendations: [], analysisStatus: 'not_started' }),
}))

export default useTripStore
