import { useCallback, useEffect, useState } from 'react'

import { useAuth } from '../../app/providers/AuthProvider.jsx'
import { useToast } from '../../app/providers/ToastProvider.jsx'
import ConfirmDialog from '../../components/ui/ConfirmDialog.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Spinner from '../../components/ui/Spinner.jsx'
import { api } from '../../lib/api.js'
import AlertCard from './components/AlertCard.jsx'
import RaiseAlertForm from './components/RaiseAlertForm.jsx'

const STATUS_FILTERS = ['open', 'acknowledged', 'resolved', 'all']

export default function AgentDashboardPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const toast = useToast()

  const [alerts, setAlerts] = useState([])
  const [summary, setSummary] = useState(null)
  const [statusFilter, setStatusFilter] = useState('open')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [updating, setUpdating] = useState(null)
  const [deletingAlert, setDeletingAlert] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      const params =
        statusFilter === 'all' ? { limit: 50 } : { status: statusFilter, limit: 50 }
      const [list, summaryData] = await Promise.all([api.listAlerts(params), api.alertSummary()])
      setAlerts(list)
      setSummary(summaryData)
    } catch (err) {
      setError(err.message || 'Failed to load alerts')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    load()
    const timer = setInterval(load, 15000)
    return () => clearInterval(timer)
  }, [load])

  const updateStatus = async (alertId, status) => {
    setUpdating(alertId)
    try {
      await api.updateAlert(alertId, { status })
      toast.success(`Alert ${status}.`)
      await load()
    } catch (err) {
      setError(err.message || 'Update failed')
      toast.error(err.message || 'Update failed')
    } finally {
      setUpdating(null)
    }
  }

  const createAlert = async (payload, reset) => {
    setError(null)
    setUpdating('create')
    try {
      await api.createAlert(payload)
      reset()
      setShowForm(false)
      toast.success('Alert raised — the queue has been refreshed.')
      await load()
    } catch (err) {
      toast.error(err.message || 'Failed to create the alert')
    } finally {
      setUpdating(null)
    }
  }

  const openDeleteAlert = (alertId) => setDeletingAlert(alertId)

  const deleteAlert = async () => {
    if (deletingAlert === null) return
    setUpdating(deletingAlert)
    try {
      await api.deleteAlert(deletingAlert)
      toast.success('Alert deleted.')
      await load()
    } catch (err) {
      toast.error(err.message || 'Delete failed')
    } finally {
      setUpdating(null)
      setDeletingAlert(null)
    }
  }

  const cards = [
    { label: 'Open alerts', value: summary?.open_alerts ?? '—', accent: 'text-rose-300' },
    { label: 'High severity open', value: summary?.high_severity_open ?? '—', accent: 'text-amber-300' },
    { label: 'Resolved', value: summary?.resolved_alerts ?? '—', accent: 'text-emerald-300' },
    { label: 'Sessions', value: summary?.total_sessions ?? '—', accent: 'text-indigo-300' },
    { label: 'Messages', value: summary?.total_messages ?? '—', accent: 'text-cyan-300' },
  ]

  return (
    <section className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {cards.map((card) => (
          <div key={card.label} className="rounded-2xl border border-slate-800/70 bg-slate-900/40 p-4">
            <p className={`text-2xl font-semibold ${card.accent}`}>{card.value}</p>
            <p className="mt-1 text-xs text-slate-400">{card.label}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-white">Alert queue</h2>
        <div className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:flex-row sm:items-center">
          <button
            onClick={() => setShowForm((value) => !value)}
            className="hidden whitespace-nowrap rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 md:inline-block"
          >
            {showForm ? 'Close form' : 'Raise alert'}
          </button>
          <div className="no-scrollbar flex justify-start gap-1 overflow-x-auto rounded-xl bg-slate-900/70 p-1 sm:justify-center">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter}
                onClick={() => setStatusFilter(filter)}
                className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs capitalize transition ${
                  statusFilter === filter
                    ? 'bg-indigo-500/90 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</div>
      )}

      {showForm && (
        <>
          {/* Scrim + bottom sheet on mobile; inline card on desktop */}
          <div
            className="fixed inset-0 z-40 bg-black/50 md:hidden"
            onClick={() => setShowForm(false)}
          />
          <div className="fixed inset-x-0 bottom-0 z-50 md:static md:inset-auto">
            <div className="animate-sheet-up max-h-[75dvh] overflow-y-auto rounded-t-3xl border-t border-x border-slate-700/80 bg-slate-900 px-4 pt-3 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-2xl shadow-black/50 md:rounded-2xl md:border md:p-4 md:shadow-lg md:max-h-none md:overflow-visible">
              <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-slate-600 md:hidden" />
              <div className="mb-3 flex items-center justify-between md:hidden">
                <h3 className="text-sm font-semibold text-white">Raise alert</h3>
                <button
                  onClick={() => setShowForm(false)}
                  aria-label="Close"
                  className="grid h-8 w-8 place-items-center rounded-full border border-slate-700 text-xs text-slate-300 hover:border-slate-500"
                >
                  ✕
                </button>
              </div>
              <RaiseAlertForm
                busy={updating === 'create'}
                onSubmit={createAlert}
                onCancel={() => setShowForm(false)}
              />
            </div>
          </div>
        </>
      )}

      {/* Android-style floating action button (mobile only) */}
      <button
        onClick={() => setShowForm((value) => !value)}
        aria-label="Raise alert"
        className="fixed bottom-[calc(env(safe-area-inset-bottom)+4.5rem)] right-4 z-40 grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-indigo-500 to-cyan-500 text-2xl text-white shadow-xl shadow-indigo-500/30 transition hover:brightness-110 md:hidden"
      >
        {showForm ? '✕' : '＋'}
      </button>

      {loading ? (
        <Spinner label="Loading alerts…" />
      ) : alerts.length === 0 ? (
        <EmptyState
          icon="🛡️"
          title="No alerts here"
          hint="Conversations that need attention — automatically detected or raised manually — will appear in this queue."
        />
      ) : (
        <ul className="space-y-3">
          {alerts.map((alert) => (
            <li key={alert.id}>
              <AlertCard
                alert={alert}
                isAdmin={isAdmin}
                updating={updating}
                onUpdate={updateStatus}
                onDelete={openDeleteAlert}
              />
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={deletingAlert !== null}
        title="Delete this alert?"
        message="This permanently removes the alert record. The customer's conversation stays intact."
        confirmLabel="Delete alert"
        busy={updating !== null}
        onConfirm={deleteAlert}
        onCancel={() => setDeletingAlert(null)}
      />
    </section>
  )
}
