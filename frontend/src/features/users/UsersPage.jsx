import { useCallback, useEffect, useState } from 'react'

import { useAuth } from '../../app/providers/AuthProvider.jsx'
import { useToast } from '../../app/providers/ToastProvider.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import ConfirmDialog from '../../components/ui/ConfirmDialog.jsx'
import InputDialog from '../../components/ui/InputDialog.jsx'
import EmptyState from '../../components/ui/EmptyState.jsx'
import Input from '../../components/ui/Input.jsx'
import Spinner from '../../components/ui/Spinner.jsx'
import { formatDate, roleBadgeClass } from '../../lib/format.js'
import { api } from '../../lib/api.js'

const emptyUser = { email: '', password: '', full_name: '', role: 'customer' }

/** Admin-only user management: create accounts, change roles, deactivate, delete. */
export default function UsersPage() {
  const toast = useToast()
  const { user: me } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [draft, setDraft] = useState(emptyUser)
  const [deletingUser, setDeletingUser] = useState(null)
  const [passwordUser, setPasswordUser] = useState(null)

  const load = useCallback(async () => {
    try {
      setUsers(await api.listUsers(100))
    } catch (err) {
      toast.error(err.message || 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  const createUser = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api.createUser({ ...draft, email: draft.email.trim().toLowerCase() })
      toast.success(`Account created for ${draft.email.trim().toLowerCase()}.`)
      setDraft(emptyUser)
      setShowForm(false)
      await load()
    } catch (err) {
      toast.error(err.message || 'Failed to create the user')
    } finally {
      setBusy(false)
    }
  }

  const patchUser = async (userId, payload, successMessage) => {
    setBusy(true)
    try {
      await api.updateUser(userId, payload)
      toast.success(successMessage)
      await load()
    } catch (err) {
      toast.error(err.message || 'Update failed')
    } finally {
      setBusy(false)
    }
  }

  const openDeleteUser = (user) => setDeletingUser(user)

  const deleteUser = async () => {
    if (!deletingUser) return
    setBusy(true)
    try {
      await api.deleteUser(deletingUser.id)
      toast.success(`Deleted ${deletingUser.email}.`)
      await load()
    } catch (err) {
      toast.error(err.message || 'Delete failed')
    } finally {
      setBusy(false)
      setDeletingUser(null)
    }
  }

  const openResetPassword = (user) => setPasswordUser(user)

  const resetPassword = async (newPassword) => {
    if (!passwordUser) return
    await patchUser(
      passwordUser.id,
      { password: newPassword },
      `Password updated for ${passwordUser.email}.`,
    )
    setPasswordUser(null)
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">User management</h2>
          <p className="text-xs text-slate-400">Admin only — accounts, roles and access.</p>
        </div>
        <Button onClick={() => setShowForm((value) => !value)}>
          {showForm ? 'Close form' : 'Create user'}
        </Button>
      </div>

      {showForm && (
        <form
          onSubmit={createUser}
          className="grid gap-3 rounded-2xl border border-slate-800/70 bg-slate-900/40 p-4 sm:grid-cols-2"
        >
          <Input
            type="email"
            value={draft.email}
            onChange={(e) => setDraft({ ...draft, email: e.target.value })}
            placeholder="Email address"
            required
          />
          <Input
            type="password"
            value={draft.password}
            onChange={(e) => setDraft({ ...draft, password: e.target.value })}
            placeholder="Password (min 8 chars)"
            required
            minLength={8}
          />
          <Input
            value={draft.full_name}
            onChange={(e) => setDraft({ ...draft, full_name: e.target.value })}
            placeholder="Full name (optional)"
          />
          <select
            value={draft.role}
            onChange={(e) => setDraft({ ...draft, role: e.target.value })}
            className="h-11 rounded-xl border border-slate-700 bg-slate-950/60 px-4 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none"
          >
            <option value="customer">customer</option>
            <option value="agent">agent</option>
            <option value="admin">admin</option>
          </select>
          <Button
            type="submit"
            variant="solid"
            disabled={busy}
            className="sm:col-span-2 sm:justify-self-end"
          >
            {busy ? 'Creating…' : 'Create user'}
          </Button>
        </form>
      )}

      {loading ? (
        <Spinner label="Loading users…" />
      ) : users.length === 0 ? (
        <EmptyState
          icon="👥"
          title="No users yet"
          hint="Create customer, agent or admin accounts here."
        />
      ) : (
        <ul className="space-y-2">
          {users.map((user) => (
            <li key={user.id} className="rounded-2xl border border-slate-800/70 bg-slate-900/40 p-3 sm:p-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge className={roleBadgeClass(user.role)}>{user.role}</Badge>
                <span className="min-w-0 max-w-full break-all text-sm font-medium text-slate-100">
                  {user.email}
                </span>
                {user.full_name && <span className="text-xs text-slate-400">{user.full_name}</span>}
                <span className="text-xs text-slate-500">joined {formatDate(user.created_at)}</span>
                <span
                  className={`ml-auto text-[11px] uppercase tracking-wide ${
                    user.is_active ? 'text-emerald-300' : 'text-rose-300'
                  }`}
                >
                  {user.is_active ? 'active' : 'deactivated'}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <select
                  value={user.role}
                  onChange={(e) =>
                    patchUser(user.id, { role: e.target.value }, `Role updated for ${user.email}.`)
                  }
                  disabled={busy || user.id === me?.id}
                  className="h-9 rounded-lg border border-slate-700 bg-slate-950/60 px-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none disabled:opacity-40"
                >
                  <option value="customer">customer</option>
                  <option value="agent">agent</option>
                  <option value="admin">admin</option>
                </select>
                <Button
                  variant="outline"
                  onClick={() =>
                    patchUser(
                      user.id,
                      { is_active: !user.is_active },
                      `${user.email} ${user.is_active ? 'deactivated' : 'reactivated'}.`,
                    )
                  }
                  disabled={busy || user.id === me?.id}
                >
                  {user.is_active ? 'Deactivate' : 'Reactivate'}
                </Button>
                <Button variant="outline" onClick={() => openResetPassword(user)} disabled={busy}>
                  Set password
                </Button>
                <Button
                  variant="danger"
                  onClick={() => openDeleteUser(user)}
                  disabled={busy || user.id === me?.id}
                >
                  Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={deletingUser !== null}
        title={`Delete ${deletingUser?.email || 'this user'}?`}
        message="The account is removed permanently. Their past conversations remain in the archive."
        confirmLabel="Delete user"
        busy={busy}
        onConfirm={deleteUser}
        onCancel={() => setDeletingUser(null)}
      />

      <InputDialog
        open={passwordUser !== null}
        title="Set new password"
        message={`Choose a new password for ${passwordUser?.email || 'this user'} (min 8 chars).`}
        label="New password"
        type="password"
        placeholder="Min 8 characters"
        minLength={8}
        confirmLabel="Update password"
        busy={busy}
        onConfirm={resetPassword}
        onCancel={() => setPasswordUser(null)}
      />
    </section>
  )
}

