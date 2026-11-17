export default function AlertBanner({ alert, onViewDashboard, onDismiss }) {
  if (!alert) return null
  const high = alert.severity >= 0.75
  return (
    <div
      className={`flex flex-wrap items-center gap-3 rounded-2xl border p-4 ${
        high ? 'border-rose-500/40 bg-rose-500/10' : 'border-amber-500/40 bg-amber-500/10'
      }`}
    >
      <span className="text-lg">{high ? '🚨' : '⚠️'}</span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-white">
          {high ? 'High-severity issue detected' : 'Issue flagged for review'} — {alert.category}
        </p>
        <p className="text-xs text-slate-300">
          Confidence {(alert.confidence * 100).toFixed(0)}% · severity{' '}
          {(alert.severity * 100).toFixed(0)}% · a human specialist has been notified
        </p>
      </div>
      <button
        onClick={onViewDashboard}
        className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/20"
      >
        Open dashboard
      </button>
      <button onClick={onDismiss} className="text-xs text-slate-400 hover:text-slate-200">
        Dismiss
      </button>
    </div>
  )
}
