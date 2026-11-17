import ErrorBoundary from '../components/feedback/ErrorBoundary.jsx'
import AppRoutes from './routes.jsx'

export default function App() {
  return (
    <ErrorBoundary>
      <AppRoutes />
    </ErrorBoundary>
  )
}
