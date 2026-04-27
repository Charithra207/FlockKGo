import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useUserStore = create(
  persist(
    (set) => ({
      participantId: null,
      participantName: null,
      currentTripId: null,
      setParticipant: (participantId, participantName) => set({ participantId, participantName }),
      setCurrentTrip: (currentTripId) => set({ currentTripId }),
      clear: () => set({ participantId: null, participantName: null, currentTripId: null }),
    }),
    { name: 'flockgo-user' },
  ),
)

export default useUserStore
