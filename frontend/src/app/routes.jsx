import { Route, Routes } from 'react-router-dom'

import NotFound from '../components/feedback/NotFound.jsx'
import RequireAuth, { RequireRole } from '../components/layout/ProtectedRoute.jsx'
import AuthScreen from '../features/auth/AuthScreen.jsx'
import AgentDashboardPage from '../features/dashboard/AgentDashboardPage.jsx'
import KnowledgePage from '../features/knowledge/KnowledgePage.jsx'
import ProfilePage from '../features/profile/ProfilePage.jsx'
import UsersPage from '../features/users/UsersPage.jsx'
import VoiceConsolePage from '../features/chat/VoiceConsolePage.jsx'

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<AuthScreen />} />

      <Route element={<RequireAuth />}>
        <Route path="/" element={<VoiceConsolePage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route
          path="/dashboard"
          element={
            <RequireRole roles={['agent', 'admin']}>
              <AgentDashboardPage />
            </RequireRole>
          }
        />
        <Route
          path="/knowledge"
          element={
            <RequireRole roles={['admin']}>
              <KnowledgePage />
            </RequireRole>
          }
        />
        <Route
          path="/users"
          element={
            <RequireRole roles={['admin']}>
              <UsersPage />
            </RequireRole>
          }
        />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
