// Central REST client (C-03). All backend access goes through apiRequest so the
// mock toggle (D3) and the in-memory JWT (C-08/C-09) live in exactly one place.

import { API_BASE_URL, USE_MOCKS } from '../utils/constants'
import { ApiError } from './apiError'
import { mockRequest } from './_mocks'

// JWT is held in memory only — never localStorage/sessionStorage (C-09).
let authToken = null
export function setAuthToken(token) {
  authToken = token || null
}
export function getAuthToken() {
  return authToken
}

/**
 * @param {string} method  HTTP verb
 * @param {string} path    e.g. '/api/products'
 * @param {{body?: object, params?: object}} [options]
 */
export async function apiRequest(method, path, { body, params } = {}) {
  if (USE_MOCKS) {
    return mockRequest(method, path, { body, params, token: authToken })
  }

  const url = new URL(path, API_BASE_URL)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    })
  }

  const headers = { 'Content-Type': 'application/json' }
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  let res
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('Network error — please check your connection.', 0)
  }

  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new ApiError(
      (data && data.message) || `Request failed (${res.status}).`,
      res.status,
      data,
    )
  }
  return data
}
