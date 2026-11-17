/**
 * Token + session storage for SecureVoice AI.
 *
 * Access/refresh JWTs and the user profile live in localStorage; a global
 * "unauthorized" event lets the app switch back to the login screen when a
 * session expires and cannot be refreshed.
 */
const ACCESS_KEY = 'securevoice:access-token'
const REFRESH_KEY = 'securevoice:refresh-token'
const USER_KEY = 'securevoice:user'
// Kept in sync with the voice console — cleared on logout so the next user
// never inherits another user's conversation.
export const SESSION_STORAGE_KEY = 'securevoice:session-id'

const listeners = new Set()

function notifyLogout() {
  listeners.forEach((fn) => fn())
}

/** Subscribe to forced-logout events; returns an unsubscribe function. */
export function onUnauthorized(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Minimal base64url JWT payload decoder (no verification — display only). */
function decodeJwtPayload(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(base64))
  } catch {
    return null
  }
}

export const auth = {
  getUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY))
    } catch {
      return null
    }
  },
  saveUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
  getAccessToken() {
    return localStorage.getItem(ACCESS_KEY)
  },
  getRefreshToken() {
    return localStorage.getItem(REFRESH_KEY)
  },
  save({ access_token, refresh_token }) {
    localStorage.setItem(ACCESS_KEY, access_token)
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token)
    const claims = decodeJwtPayload(access_token)
    if (claims?.sub) {
      const existing = this.getUser() || {}
      this.saveUser({ ...existing, id: Number(claims.sub), role: claims.role })
    }
  },
  clear() {
    ;[ACCESS_KEY, REFRESH_KEY, USER_KEY, SESSION_STORAGE_KEY].forEach((key) =>
      localStorage.removeItem(key),
    )
  },
  logout() {
    this.clear()
    notifyLogout()
  },
}
