import { useEffect, useState } from 'react'

import { api } from '../../lib/api.js'

const STATES = {
  checking: { dot: 'bg-slate-400', label: 'Checking API…', wrap: 'border-slate-700 text-slate-300' },
  online: { dot: 'bg-emerald-400', label: 'API online', wrap: 'border-emerald-500/40 text-emerald-300' },
  offline: { dot: 'bg-rose-500', label: 'API offline', wrap: 'border-rose-500/40 text-rose-300' },
}

/** Polls `/health` (public) and shows a live backend status pill. */
export default function StatusPill() {
  const [state, setState] = useState('checking')

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        await api.health()
        if (!cancelled) setState('online')
      } catch {
        if (!cancelled) setState('offline')
      }
    }
    check()
    const timer = setInterval(check, 30000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  const config = STATES[state]
  return (
    <span
      className={`hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs sm:inline-flex ${config.wrap}`}
    >
      <span className={`h-2 w-2 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}
