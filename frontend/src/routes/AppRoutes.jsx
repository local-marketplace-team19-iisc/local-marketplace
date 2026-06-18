import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute'
import { ROLES } from '../utils/constants'
import LoginPage from '../pages/LoginPage'
import RegisterPage from '../pages/RegisterPage'
import SearchPage from '../pages/SearchPage'
import ProductPage from '../pages/ProductPage'
import FavoritesPage from '../pages/FavoritesPage'
import OrdersPage from '../pages/OrdersPage'
import ChatbotPage from '../pages/ChatbotPage'

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
      <Route path="/" element={<SearchPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="/product/:id" element={<ProductPage />} />
      <Route path="/chat" element={<ChatbotPage />} />

      {/* Authenticated */}
      <Route path="/favorites" element={<ProtectedRoute><FavoritesPage /></ProtectedRoute>} />
      <Route path="/orders" element={<ProtectedRoute><OrdersPage /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute><Placeholder title="Dashboard" /></ProtectedRoute>} />

      {/* Vendor-only */}
      <Route path="/vendor" element={<ProtectedRoute role={ROLES.VENDOR}><Placeholder title="Vendor" /></ProtectedRoute>} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default AppRoutes
