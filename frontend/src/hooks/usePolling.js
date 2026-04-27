import { useEffect, useRef } from 'react'

export default function usePolling(fn, interval, condition = () => false) {
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    let stopped = false
    const run = async () => {
      const done = await fnRef.current()
      if (!stopped && !condition(done)) setTimeout(run, interval)
    }
    run()
    return () => {
      stopped = true
    }
  }, [condition, interval])
}
