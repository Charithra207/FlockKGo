import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * Logged-in account (for spots: share / unlock / vouch).
 * Separate from userStore, which tracks per-trip participants.
 */
const useAuthStore = create(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      setCredits: (unlock_credits) =>
        set((s) => (s.user ? { user: { ...s.user, unlock_credits } } : {})),
      logout: () => set({ token: null, user: null }),
    }),
    { name: 'flockgo-auth' },
  ),
)

export default useAuthStore
