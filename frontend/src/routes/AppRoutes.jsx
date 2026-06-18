import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute'
import { ROLES } from '../utils/constants'
import LoginPage from '../pages/LoginPage'
import RegisterPage from '../pages/RegisterPage'

// Central route table. Pages are filled in across Phases 4–7; until a page exists it
// renders this placeholder so routing + the ProtectedRoute guard (AC-08) are verifiable.
function Placeholder({ title }) {
  return (
    <div className="container" style={{ padding: '32px 0' }}>
      <h1>{title}</h1>
      <p>This page is implemented in a later phase.</p>
    </div>
  )
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<Placeholder title="Home" />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/search" element={<Placeholder title="Search" />} />
      <Route path="/product/:id" element={<Placeholder title="Product" />} />
      <Route path="/chat" element={<Placeholder title="Chatbot" />} />

      {/* Authenticated */}
      <Route path="/favorites" element={<ProtectedRoute><Placeholder title="Favorites" /></ProtectedRoute>} />
      <Route path="/orders" element={<ProtectedRoute><Placeholder title="Orders" /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute><Placeholder title="Dashboard" /></ProtectedRoute>} />

      {/* Vendor-only */}
      <Route path="/vendor" element={<ProtectedRoute role={ROLES.VENDOR}><Placeholder title="Vendor" /></ProtectedRoute>} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default AppRoutes
