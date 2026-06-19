// Product search REST call (C-03). Results power AC-09/AC-10.
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function searchProducts(query) {
  return apiRequest('GET', API_ROUTES.search, { params: { q: query } })
}

// Image-based search (AC-09, D8): uploads an image; the backend (mocked) returns matched
// products. Sent as multipart/form-data.
export function searchByImage(file) {
  const fd = new FormData()
  fd.append('image', file)
  return apiRequest('POST', API_ROUTES.searchImage, { body: fd })
}
