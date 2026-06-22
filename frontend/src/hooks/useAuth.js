// Convenience hook to read the Auth context with a clear error if used outside provider.
import { useContext } from 'react'
import { AuthContext } from '../store/authContext'

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>.')
  return ctx
}
