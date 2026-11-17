import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../../app/providers/AuthProvider.jsx'
import AppShell from './AppShell.jsx'

/** Auth gate: renders the app shell (with nested routes) only when signed in. */
export default function RequireAuth() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <AppShell />
}

/** Role gate for nested route elements (redirects home when forbidden). */
export function RequireRole({ roles, children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (!roles.includes(user.role)) return <Navigate to="/" replace />
  return children
}

/** Convenience re-export so route tables read naturally. */
export { Outlet }
