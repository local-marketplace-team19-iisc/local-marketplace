import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute'
import { ROLES } from '../utils/constants'
import HomePage from '../pages/HomePage'
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
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="/product/:id" element={<ProductPage />} />

      {/* Authenticated */}
      {/* /chat is the marketplace agent (customer shopping journey). It must
          not be reachable while signed out — an anonymous visitor was being
          shown the agent. Require auth; login redirects back here afterwards. */}
      <Route path="/chat" element={<ProtectedRoute><ChatbotPage /></ProtectedRoute>} />
      <Route path="/favorites" element={<ProtectedRoute><FavoritesPage /></ProtectedRoute>} />
      {/* /orders is the customer cart + history page. Vendors hit the
          "Orders" tab on /vendor instead (different endpoint, different
          shape). Role-gating here prevents a vendor who clicks an old
          link from triggering a /api/orders 403 storm. */}
      <Route path="/orders" element={<ProtectedRoute role={ROLES.CUSTOMER}><OrdersPage /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute role={ROLES.VENDOR}><Dashboard /></ProtectedRoute>} />

      {/* Vendor-only */}
      <Route path="/vendor" element={<ProtectedRoute role={ROLES.VENDOR}><VendorPage /></ProtectedRoute>} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default AppRoutes
