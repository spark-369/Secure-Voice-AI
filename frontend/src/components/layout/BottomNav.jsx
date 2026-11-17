import { NavLink } from 'react-router-dom'

import { useAuth } from '../../app/providers/AuthProvider.jsx'

const ITEMS = [
  { to: '/', label: 'Console', icon: '🎙️', end: true },
  { to: '/dashboard', label: 'Alerts', icon: '🧭', roles: ['agent', 'admin'] },
  { to: '/knowledge', label: 'Knowledge', icon: '📚', roles: ['admin'] },
  { to: '/users', label: 'Users', icon: '👥', roles: ['admin'] },
  { to: '/profile', label: 'Profile', icon: '⚙️' },
]

/** Android-style bottom navigation bar (mobile only; the top nav takes over at md+). */
export default function BottomNav() {
  const { user } = useAuth()
  const role = user?.role || 'customer'

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-800/70 bg-slate-950/95 backdrop-blur md:hidden">
      <div
        className="mx-auto flex max-w-md items-stretch justify-around px-2"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        {ITEMS.filter((item) => !item.roles || item.roles.includes(role)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex min-w-[4.5rem] flex-col items-center gap-0.5 px-2 py-2.5 text-[10px] font-medium transition ${
                isActive ? 'text-indigo-300' : 'text-slate-500 hover:text-slate-300'
              }`
            }
          >
            <span className="text-lg leading-none">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
