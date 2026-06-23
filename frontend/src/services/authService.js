// Auth REST calls (C-03). Thin wrappers over apiClient — no business logic (C-04).
import { apiRequest, setAuthToken } from './apiClient'
import { API_ROUTES } from '../utils/constants'

// The mock layer returns { token, user } directly. The real 003 backend returns
// { access_token, refresh_token, user_id, user_type } and exposes the profile via
// GET /api/auth/me. authContext expects { token, user }, so adapt the real shape
// here (the integration seam — D3). Mock responses pass through unchanged.
async function toSession(resp) {
  if (resp && resp.token && resp.user) return resp // mock contract
  const token = resp.access_token
  setAuthToken(token) // authorize the immediate /me call
  let me = {}
  try {
    me = await apiRequest('GET', API_ROUTES.me)
  } catch {
    me = {}
  }
  const user = {
    id: me.id ?? resp.user_id,
    email: me.email,
    role: me.user_type ?? resp.user_type,
    vendorId: me.vendor_id ?? resp.vendor_id ?? null,
    vendor: me.shop_name ?? null,
    name: me.shop_name ?? me.email ?? '',
  }
  return { token, user }
}

export async function login(payload) {
  return toSession(await apiRequest('POST', API_ROUTES.login, { body: payload }))
}

export async function register(payload) {
  return toSession(await apiRequest('POST', API_ROUTES.register, { body: payload }))
}

export function getMe() {
  return apiRequest('GET', API_ROUTES.me)
}
