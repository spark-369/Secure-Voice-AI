import { useEffect } from 'react'

import Button from './Button.jsx'

/**
 * Android-style confirmation dialog.
 * Mobile: slides up from the bottom as a sheet (drag handle + safe-area).
 * Desktop (sm+): centered modal card with row buttons.
 */
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  confirmVariant = 'danger',
  busy = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onCancel?.()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 sm:items-center"
      onClick={onCancel}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{ paddingBottom: 'calc(1.25rem + env(safe-area-inset-bottom))' }}
        className="animate-sheet-up w-full max-w-md rounded-t-3xl border border-slate-700/80 bg-slate-900 p-5 shadow-2xl shadow-black/50 sm:rounded-3xl sm:p-6 sm:pb-6"
      >
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-slate-600 sm:hidden" />
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <p className="mt-2 text-xs leading-relaxed text-slate-400">{message}</p>
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={onCancel} className="w-full sm:w-auto">
            Cancel
          </Button>
          <Button
            variant={confirmVariant}
            onClick={onConfirm}
            disabled={busy}
            className="w-full sm:w-auto"
          >
            {busy ? 'Working…' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
