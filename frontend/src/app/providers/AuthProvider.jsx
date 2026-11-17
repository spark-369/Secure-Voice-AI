import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api } from '../../lib/api.js'
import { auth, onUnauthorized } from '../../lib/auth.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => auth.getUser())

  // Any unrecoverable 401 (expired refresh token) drops back to the login gate.
  useEffect(() => onUnauthorized(() => setUser(null)), [])

  const login = useCallback(async (email, password) => {
    const profile = await api.login(email, password)
    setUser(profile)
    return profile
  }, [])

  const register = useCallback(async (payload) => api.register(payload), [])

  const logout = useCallback(() => {
    auth.logout()
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    try {
      const profile = await api.me()
      auth.saveUser(profile)
      setUser(profile)
      return profile
    } catch {
      return null
    }
  }, [])

  const value = useMemo(() => {
    const role = user?.role || 'customer'
    return {
      user,
      login,
      register,
      logout,
      refreshUser,
      isStaff: role === 'agent' || role === 'admin',
      isAdmin: role === 'admin',
    }
  }, [user, login, register, logout, refreshUser])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
