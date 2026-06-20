// Auth REST calls (C-03). Thin wrappers over apiClient — no business logic (C-04).
import { apiRequest } from './apiClient'
import { API_ROUTES } from '../utils/constants'

export function register(payload) {
  return apiRequest('POST', API_ROUTES.register, { body: payload })
}

export function login(payload) {
  return apiRequest('POST', API_ROUTES.login, { body: payload })
}

export function getMe() {
  return apiRequest('GET', API_ROUTES.me)
}
