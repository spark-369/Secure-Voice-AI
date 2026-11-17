/**
 * Fetch wrapper around the SecureVoice AI REST API with JWT authentication.
 *
 * - Attaches `Authorization: Bearer <access token>` to every authed request.
 * - On 401, silently rotates the token pair via /auth/refresh and retries once.
 * - If the refresh also fails, clears the session and notifies the app.
 *
 * Base URL: VITE_API_BASE_URL (defaults to `/api/v1`, proxied by Vite/Nginx).
 */
import { auth, onUnauthorized } from './auth.js'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function refreshTokens() {
  const refreshToken = auth.getRefreshToken()
  if (!refreshToken) return false
  try {
    const response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!response.ok) return false
    auth.save(await response.json())
    return true
  } catch {
    return false
  }
}

async function request(path, { method = 'GET', body, signal, authed = true, retry = true } = {}) {
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'
  if (authed) {
    const token = auth.getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch {
    throw new ApiError('Backend unreachable — is the API running?', 0)
  }

  if (response.status === 204) return null

  let data = null
  try {
    data = await response.json()
  } catch {
    /* empty or non-JSON body */
  }

  if (!response.ok) {
    if (response.status === 401 && authed && retry) {
      if (await refreshTokens()) {
        return request(path, { method, body, signal, authed, retry: false })
      }
      auth.logout()
      throw new ApiError(data?.detail || 'Session expired — please sign in again.', 401)
    }
    const detail =
      (data && (data.detail || data.message)) || `Request failed (${response.status})`
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), response.status)
  }
  return data
}

export { onUnauthorized }

export const api = {
  // -- authentication -----------------------------------------------------------
  login: async (email, password) => {
    const tokens = await request('/auth/login', {
      method: 'POST',
      body: { email, password },
      authed: false,
    })
    auth.save(tokens)
    const me = await request('/auth/me')
    auth.saveUser(me)
    return me
  },
  register: (payload) =>
    request('/auth/register', { method: 'POST', body: payload, authed: false }),
  me: () => request('/auth/me'),
  updateProfile: (payload) => request('/auth/me', { method: 'PATCH', body: payload }),
  logout: () => auth.logout(),

  // -- admin: users -------------------------------------------------------------
  listUsers: (limit = 100) => request(`/users?limit=${limit}`),
  createUser: (payload) => request('/users', { method: 'POST', body: payload }),
  updateUser: (userId, payload) =>
    request(`/users/${userId}`, { method: 'PATCH', body: payload }),
  deleteUser: (userId) => request(`/users/${userId}`, { method: 'DELETE' }),

  // -- health ---------------------------------------------------------------------
  health: () => request('/health', { authed: false }),
  ready: () => request('/health/ready', { authed: false }),

  // -- sessions ---------------------------------------------------------------------
  createSession: (payload = {}) => request('/sessions', { method: 'POST', body: payload }),
  getSession: (sessionId) => request(`/sessions/${sessionId}`),
  closeSession: (sessionId) => request(`/sessions/${sessionId}/close`, { method: 'POST' }),
  updateSession: (sessionId, payload) =>
    request(`/sessions/${sessionId}`, { method: 'PATCH', body: payload }),
  deleteSession: (sessionId) => request(`/sessions/${sessionId}`, { method: 'DELETE' }),
  listSessions: (limit = 20) => request(`/sessions?limit=${limit}`),

  // -- chat ---------------------------------------------------------------------------
  sendMessage: ({ sessionId, text }) =>
    request('/chat/message', {
      method: 'POST',
      body: { text, session_id: sessionId || null },
    }),

  // -- alerts ---------------------------------------------------------------------------
  listAlerts: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(
        ([, value]) => value !== undefined && value !== null && value !== '',
      ),
    ).toString()
    return request(`/alerts${query ? `?${query}` : ''}`)
  },
  updateAlert: (alertId, payload) =>
    request(`/alerts/${alertId}`, { method: 'PATCH', body: payload }),
  alertSummary: () => request('/alerts/summary'),
  createAlert: (payload) => request('/alerts', { method: 'POST', body: payload }),
  deleteAlert: (alertId) => request(`/alerts/${alertId}`, { method: 'DELETE' }),

  // -- knowledge base ---------------------------------------------------------------------
  listDocuments: () => request('/knowledge/documents'),
  knowledgeStats: () => request('/knowledge/stats'),
  ingestDefault: () => request('/knowledge/ingest-default', { method: 'POST', body: {} }),
  ingestDocuments: (payload) => request('/knowledge/ingest', { method: 'POST', body: payload }),
  updateDocument: (documentId, payload) =>
    request(`/knowledge/documents/${documentId}`, { method: 'PATCH', body: payload }),
  deleteDocument: (documentId) =>
    request(`/knowledge/documents/${documentId}`, { method: 'DELETE' }),
}
