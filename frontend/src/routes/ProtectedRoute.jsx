import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

// Guards routes that require authentication (AC-08). Optionally enforces a role
// (e.g. vendor-only pages). Unauthenticated users are sent to /login, preserving
// the intended destination so login can redirect back.
function ProtectedRoute({ children, role }) {
  const { isAuthenticated, user } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  if (role && user?.role !== role) {
    return <Navigate to="/" replace />
  }
  return children
}

export default ProtectedRoute
