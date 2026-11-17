import { useEffect, useState } from 'react'

import Button from './Button.jsx'
import Input from './Input.jsx'

/**
 * Android-style single-input dialog (e.g. password resets).
 * Mobile: bottom sheet with drag handle + safe-area. Desktop: centered modal.
 */
export default function InputDialog({
  open,
  title,
  message,
  label = 'Value',
  placeholder = '',
  type = 'text',
  minLength = 0,
  confirmLabel = 'Save',
  busy = false,
  onConfirm,
  onCancel,
}) {
  const [value, setValue] = useState('')

  useEffect(() => {
    if (!open) return undefined
    setValue('')
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

  const submit = (event) => {
    event.preventDefault()
    if (value.length < minLength) return
    onConfirm?.(value)
  }

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
        {message && <p className="mt-2 text-xs leading-relaxed text-slate-400">{message}</p>}
        <form onSubmit={submit} className="mt-4 space-y-4">
          <Input
            type={type}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder={placeholder}
            required
            minLength={minLength}
            autoFocus
          />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={onCancel} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button
              type="submit"
              variant="solid"
              disabled={busy || value.length < minLength}
              className="w-full sm:w-auto"
            >
              {busy ? 'Saving…' : confirmLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
