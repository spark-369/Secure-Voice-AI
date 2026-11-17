import Badge from '../../../components/ui/Badge.jsx'
import Button from '../../../components/ui/Button.jsx'
import Card from '../../../components/ui/Card.jsx'
import { formatDateTime, severityClass } from '../../../lib/format.js'

/** One alert in the queue, incl. the full customer profile strip. */
export default function AlertCard({ alert, isAdmin, updating, onUpdate, onDelete }) {
  const providerLabel =
    alert.provider === 'manual' ? 'raised manually' : 'detected automatically'
  return (
    <Card className="p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge className={severityClass(alert.severity)}>
          {alert.category} · {(alert.severity * 100).toFixed(0)}%
        </Badge>
        <span className="text-xs text-slate-500">session {alert.session_id.slice(0, 8)}</span>
        {(alert.customer_email || alert.customer_name) && (
          <span className="text-xs text-indigo-300">
            👤 {alert.customer_name || alert.customer_email}
          </span>
        )}
        <span className="text-xs text-slate-500">
          confidence {(alert.confidence * 100).toFixed(0)}%
        </span>
        <span className="text-xs text-slate-500">{providerLabel}</span>
        <span className="ml-auto text-xs text-slate-500">{formatDateTime(alert.created_at)}</span>
      </div>

      {alert.customer && (
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-slate-800/60 bg-slate-950/40 px-3 py-2 text-[11px] text-slate-400">
          <span className="min-w-0 max-w-[180px] truncate font-medium text-slate-200">
            {alert.customer.full_name || alert.customer.email}
          </span>
          <span className="min-w-0 max-w-[200px] truncate">{alert.customer.email}</span>
          <span>member since {formatDateTime(alert.customer.member_since).split(',')[0]}</span>
          <span>{alert.customer.total_sessions} sessions</span>
          <span>{alert.customer.total_messages} messages</span>
          <span>{alert.customer.total_alerts} alerts</span>
          {alert.customer.last_activity && (
            <span>last activity {formatDateTime(alert.customer.last_activity)}</span>
          )}
          {!alert.customer.is_active && (
            <span className="text-rose-300">account deactivated</span>
          )}
        </div>
      )}

      {alert.summary && (
        <p className="mt-2 line-clamp-2 text-sm text-slate-300">“{alert.summary}”</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {alert.status !== 'acknowledged' && alert.status !== 'resolved' && (
          <Button
            variant="outline"
            onClick={() => onUpdate(alert.id, 'acknowledged')}
            disabled={updating === alert.id}
            className="!border-amber-500/40 !bg-amber-500/10 !text-amber-200 hover:!bg-amber-500/20"
          >
            Acknowledge
          </Button>
        )}
        {alert.status !== 'resolved' && (
          <Button
            variant="outline"
            onClick={() => onUpdate(alert.id, 'resolved')}
            disabled={updating === alert.id}
            className="!border-emerald-500/40 !bg-emerald-500/10 !text-emerald-200 hover:!bg-emerald-500/20"
          >
            Resolve
          </Button>
        )}
        {alert.status === 'resolved' && (
          <Button variant="outline" onClick={() => onUpdate(alert.id, 'open')} disabled={updating === alert.id}>
            Reopen
          </Button>
        )}
        {isAdmin && (
          <Button variant="danger" onClick={() => onDelete(alert.id)} disabled={updating === alert.id}>
            Delete
          </Button>
        )}
        <span className="ml-auto text-[11px] uppercase tracking-wide text-slate-500">
          {alert.status}
        </span>
      </div>
    </Card>
  )
}
