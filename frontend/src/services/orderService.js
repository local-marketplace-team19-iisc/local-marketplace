// Order REST calls (C-03). A cart can span multiple vendors; the backend returns one
// order number (master SPEC §3).
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function listOrders() {
  return apiRequest('GET', API_ROUTES.orders)
}

export function placeOrder(items) {
  return apiRequest('POST', API_ROUTES.orders, { body: { items } })
}
