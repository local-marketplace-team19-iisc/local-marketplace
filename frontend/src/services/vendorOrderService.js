// Vendor-scoped order history (C-03). Thin wrapper over apiClient — no business
// logic (C-04). The backend partitions the order so each vendor sees ONLY its
// own line items, even when the customer's checkout spanned multiple vendors.
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function listVendorOrders() {
  return apiRequest('GET', API_ROUTES.vendorOrders)
}
