// Product REST calls (C-03), including vendor CRUD (AC-13/14/15).
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function listProducts(params) {
  return apiRequest('GET', API_ROUTES.products, { params })
}

export function getProduct(id) {
  return apiRequest('GET', API_ROUTES.product(id))
}

export function createProduct(body) {
  return apiRequest('POST', API_ROUTES.products, { body })
}

export function updateProduct(id, body) {
  return apiRequest('PUT', API_ROUTES.product(id), { body })
}

export function deleteProduct(id) {
  return apiRequest('DELETE', API_ROUTES.product(id))
}
