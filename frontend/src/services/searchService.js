// Product search REST call (C-03). Results power AC-09/AC-10.
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function searchProducts(query) {
  return apiRequest('GET', API_ROUTES.search, { params: { q: query } })
}
