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

// Vendor product workflow (feature 006): create a product from a typed/spoken
// description, and delete the vendor's own product by description. The backend
// parses the catalog fields and scopes both operations to the current vendor.
export function createProductFromDescription(description_text) {
  return apiRequest('POST', API_ROUTES.productsFromDescription, { body: { description_text } })
}

export function deleteProductByDescription(description_text) {
  return apiRequest('POST', API_ROUTES.productsDeleteByDescription, { body: { description_text } })
}
