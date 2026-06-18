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
import Dashboard from '../pages/Dashboard'
import VendorPage from '../pages/VendorPage'

// Central route table. Public, authenticated, and vendor-only routes; the auth guard
// (AC-08) and role gate are applied via ProtectedRoute.
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
      <Route path="/dashboard" element={<ProtectedRoute role={ROLES.VENDOR}><Dashboard /></ProtectedRoute>} />

      {/* Vendor-only */}
      <Route path="/vendor" element={<ProtectedRoute role={ROLES.VENDOR}><VendorPage /></ProtectedRoute>} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default AppRoutes
