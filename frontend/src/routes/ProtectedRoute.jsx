import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

// Guards routes that require authentication (AC-08). Optionally enforces a role
// (e.g. vendor-only pages). Unauthenticated users are sent to /login, preserving
// the intended destination so login can redirect back.
//
// IMPORTANT: when AuthProvider is still rehydrating a cached session
// (`status === 'loading'`), we must NOT redirect — otherwise a page refresh
// while signed in flickers through /login before /auth/me resolves. Render a
// neutral placeholder until auth state settles.
function ProtectedRoute({ children, role }) {
  const { isAuthenticated, status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="loading-screen" role="status" aria-live="polite">
        Restoring your session…
      </div>
    )
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  if (role && user?.role !== role) {
    return <Navigate to="/" replace />
  }
  return children
}

export default ProtectedRoute
