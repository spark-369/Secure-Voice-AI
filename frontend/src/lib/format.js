/** Shared display formatters (dates, badges, initials). */

export function formatTime(value) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function formatDateTime(value) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

export function formatDate(value) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return ''
  }
}

export function severityClass(severity) {
  if (severity >= 0.75) return 'border-rose-500/40 bg-rose-500/10 text-rose-300'
  if (severity >= 0.5) return 'border-amber-500/40 bg-amber-500/10 text-amber-300'
  return 'border-slate-600 bg-slate-800/60 text-slate-300'
}

export function roleBadgeClass(role) {
  if (role === 'admin') return 'bg-rose-500/10 text-rose-300 border-rose-500/40'
  if (role === 'agent') return 'bg-amber-500/10 text-amber-300 border-amber-500/40'
  return 'bg-slate-700/40 text-slate-300 border-slate-600'
}

export function initials(nameOrEmail) {
  const source = (nameOrEmail || '').trim()
  if (!source) return '?'
  const parts = source.split(/[\s@._-]+/).filter(Boolean)
  return (parts[0]?.[0] + (parts[1]?.[0] || '')).toUpperCase()
}
