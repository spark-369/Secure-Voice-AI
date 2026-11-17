import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../../app/providers/AuthProvider.jsx'
import { roleBadgeClass } from '../../lib/format.js'
import Badge from '../ui/Badge.jsx'
import StatusPill from '../ui/StatusPill.jsx'
import BottomNav from './BottomNav.jsx'

const NAV = [
  { to: '/', label: '🎙️ Voice Console', end: true },
  { to: '/dashboard', label: '🧭 Agent Dashboard', roles: ['agent', 'admin'] },
  { to: '/knowledge', label: '📚 Knowledge', roles: ['admin'] },
  { to: '/users', label: '👥 Users', roles: ['admin'] },
]

export default function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const role = user?.role || 'customer'

  const signOut = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-10 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-3 py-3 sm:px-4">
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="SecureVoice AI" className="h-9 w-9" />
            <div>
              <h1 className="text-sm font-semibold tracking-tight text-white">SecureVoice AI</h1>
              <p className="text-[11px] text-slate-400">Autonomous customer care</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <StatusPill />
            <Badge className={`hidden sm:inline-flex ${roleBadgeClass(role)}`}>{role}</Badge>
            <button
              onClick={() => navigate('/profile')}
              title="Profile settings"
              className="hidden max-w-[160px] truncate text-xs text-slate-400 hover:text-slate-200 lg:inline-block"
            >
              {user?.email}
            </button>
            <button
              onClick={signOut}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-rose-500/50 hover:text-rose-200"
            >
              Sign out
            </button>
          </div>

          <nav className="hidden items-center gap-1 rounded-xl bg-slate-900/70 p-1 md:flex">
            {NAV.filter((item) => !item.roles || item.roles.includes(role)).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                    isActive
                      ? 'bg-indigo-500/90 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-3 pb-[calc(env(safe-area-inset-bottom)+5.5rem)] pt-4 sm:px-4 sm:pb-10 sm:pt-6">
        <Outlet />
      </main>

      <BottomNav />

      <footer className="hidden border-t border-slate-800/60 py-4 text-center text-xs text-slate-500 md:block">
        SecureVoice AI · Private, voice-first customer care · Speech stays in your browser — only
        text reaches the server
      </footer>
    </div>
  )
}
