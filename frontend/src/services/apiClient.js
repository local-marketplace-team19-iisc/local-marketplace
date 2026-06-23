// Central REST client (C-03). All backend access goes through apiRequest so the
// mock toggle (D3) and the in-memory JWT (C-08/C-09) live in exactly one place.

import { API_BASE_URL, USE_AUTH_MOCKS, USE_MOCKS } from '../utils/constants'
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
  const isAuthRequest = path.startsWith('/api/auth/')
  if ((isAuthRequest && USE_AUTH_MOCKS) || (!isAuthRequest && USE_MOCKS)) {
    return mockRequest(method, path, { body, params, token: authToken })
  }

  const url = new URL(path, API_BASE_URL)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    })
  }

  // multipart/form-data (image upload / extraction): let the browser set the boundary
  // Content-Type and send the FormData as-is; otherwise send JSON.
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData
  const headers = {}
  if (!isForm) headers['Content-Type'] = 'application/json'
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  let res
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    })
  } catch {
    throw new ApiError('Network error — please check your connection.', 0)
  }

  const data = await res.json().catch(() => null)
  if (!res.ok) {
    // FastAPI returns errors as `{detail: ...}`. Detail can be a plain string
    // ("Forbidden"), an object (`{message, lines, ...}` for our richer 409s),
    // or — for validation errors — an array of issue objects. We always want
    // a human-readable string on the Error so UI banners render correctly; the
    // raw payload stays available on `err.data` for callers that need it.
    const detail = data?.detail
    let message
    if (typeof detail === 'string') {
      message = detail
    } else if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
      message = detail.message
    } else if (Array.isArray(detail) && detail[0]?.msg) {
      message = detail[0].msg
    } else if (typeof data?.message === 'string') {
      message = data.message
    } else {
      message = `Request failed (${res.status}).`
    }
    throw new ApiError(message, res.status, data)
  }
  return data
}
