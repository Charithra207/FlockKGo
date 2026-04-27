import { useEffect } from 'react'
import confetti from 'canvas-confetti'

export default function ConfettiEffect() {
  useEffect(() => {
    confetti({ particleCount: 160, spread: 90, origin: { y: 0.6 }, colors: ['#1E3A5F', '#FF6B6B'] })
  }, [])
  return null
}
