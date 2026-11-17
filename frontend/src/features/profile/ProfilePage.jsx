import { useState } from 'react'

import { useAuth } from '../../app/providers/AuthProvider.jsx'
import { useToast } from '../../app/providers/ToastProvider.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Input from '../../components/ui/Input.jsx'
import { formatDate, roleBadgeClass } from '../../lib/format.js'
import { api } from '../../lib/api.js'

/** Self-service settings: profile name + password change. */
export default function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const toast = useToast()

  const [fullName, setFullName] = useState(user?.full_name || '')
  const [busyName, setBusyName] = useState(false)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [busyPassword, setBusyPassword] = useState(false)

  const saveName = async (event) => {
    event.preventDefault()
    setBusyName(true)
    try {
      await api.updateProfile({ full_name: fullName.trim() || null })
      await refreshUser()
      toast.success('Profile updated.')
    } catch (err) {
      toast.error(err.message || 'Update failed')
    } finally {
      setBusyName(false)
    }
  }

  const savePassword = async (event) => {
    event.preventDefault()
    setBusyPassword(true)
    try {
      await api.updateProfile({ current_password: currentPassword, password: newPassword })
      await refreshUser()
      toast.success('Password changed.')
      setCurrentPassword('')
      setNewPassword('')
    } catch (err) {
      toast.error(err.message || 'Password change failed')
    } finally {
      setBusyPassword(false)
    }
  }

  return (
    <section className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Profile & settings</h2>
        <p className="text-xs text-slate-400">Your account details and credentials.</p>
      </div>

      <Card className="p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-3">
          <Badge className={roleBadgeClass(user?.role)}>{user?.role}</Badge>
          <span className="min-w-0 max-w-full break-all text-sm font-medium text-slate-100">
            {user?.email}
          </span>
          <span className="ml-auto text-xs text-slate-500">
            member since {formatDate(user?.created_at)}
          </span>
        </div>
      </Card>

      <Card className="p-4 sm:p-5">
        <h3 className="text-sm font-semibold text-white">Display name</h3>
        <form onSubmit={saveName} className="mt-3 flex flex-wrap items-end gap-3">
          <Input
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="Full name"
            className="sm:max-w-xs"
          />
          <Button type="submit" variant="solid" disabled={busyName}>
            {busyName ? 'Saving…' : 'Save name'}
          </Button>
        </form>
      </Card>

      <Card className="p-4 sm:p-5">
        <h3 className="text-sm font-semibold text-white">Change password</h3>
        <form onSubmit={savePassword} className="mt-3 space-y-3">
          <Input
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            placeholder="Current password"
            required
            minLength={8}
            autoComplete="current-password"
          />
          <Input
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            placeholder="New password (min 8 chars)"
            required
            minLength={8}
            autoComplete="new-password"
          />
          <Button type="submit" variant="solid" disabled={busyPassword}>
            {busyPassword ? 'Updating…' : 'Change password'}
          </Button>
        </form>
      </Card>
    </section>
  )
}
