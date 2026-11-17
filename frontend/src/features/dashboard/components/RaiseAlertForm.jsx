import { useState } from 'react'

import Button from '../../../components/ui/Button.jsx'
import Input, { inputClass } from '../../../components/ui/Input.jsx'

/** Staff form for manually raising an alert on an existing session. */
export default function RaiseAlertForm({ busy, onSubmit, onCancel }) {
  const [sessionId, setSessionId] = useState('')
  const [category, setCategory] = useState('')
  const [severity, setSeverity] = useState(0.6)
  const [summary, setSummary] = useState('')

  const submit = (event) => {
    event.preventDefault()
    if (!sessionId.trim() || !category.trim()) return
    onSubmit(
      {
        session_id: sessionId.trim(),
        category: category.trim(),
        severity: Number(severity),
        summary: summary.trim() || null,
      },
      () => {
        setSessionId('')
        setCategory('')
        setSeverity(0.6)
        setSummary('')
      },
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
      <Input
        value={sessionId}
        onChange={(event) => setSessionId(event.target.value)}
        placeholder="Session ID (from a conversation)"
        required
        className="sm:col-span-2"
      />
      <Input
        value={category}
        onChange={(event) => setCategory(event.target.value)}
        placeholder="Category (e.g. billing, urgent escalation)"
        required
      />
      <label className="flex h-11 items-center gap-3 rounded-xl border border-slate-700 bg-slate-950/60 px-4 text-xs text-slate-300">
        Severity
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={severity}
          onChange={(event) => setSeverity(event.target.value)}
          className="flex-1 accent-indigo-500"
        />
        <span className="w-10 text-right font-mono">{Number(severity).toFixed(2)}</span>
      </label>
      <Input
        value={summary}
        onChange={(event) => setSummary(event.target.value)}
        placeholder="Summary (optional)"
        className="sm:col-span-2"
      />
      <div className="flex flex-col-reverse gap-2 sm:col-span-2 sm:flex-row sm:justify-end">
        {onCancel && (
          <Button variant="outline" onClick={onCancel} className="w-full sm:w-auto">
            Cancel
          </Button>
        )}
        <Button type="submit" variant="solid" disabled={busy} className="h-11 w-full sm:w-auto">
          {busy ? 'Raising…' : 'Raise alert'}
        </Button>
      </div>
    </form>
  )
}
