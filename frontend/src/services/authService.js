// Auth REST calls (C-03). Thin wrappers over apiClient — no business logic (C-04).
import { apiRequest } from './apiClient'
import { API_ROUTES, ROLES } from '../utils/constants'

function toAuthState(data) {
  const role = data.user_type
  return {
    token: data.access_token,
    refreshToken: data.refresh_token,
    user: {
      id: data.user_id,
      email: data.email,
      role,
      vendorId: data.vendor_id || null,
      vendor: data.shop_name || null,
    },
  }
}

export function register(payload) {
  const isVendor = payload.role === ROLES.VENDOR
  // V1 vendor registration omits `location` — see RegisterPage.jsx and
  // RegisterVendorRequest in backend/app/schemas/auth.py. The backend
  // treats a missing `location` as `(0, 0)` so we don't have to send a
  // placeholder from here.
  const body = isVendor
    ? {
        email: payload.email,
        password: payload.password,
        password_confirm: payload.password_confirm,
        shop_name: payload.shop_name || payload.name,
        shop_description: payload.shop_description || '',
      }
    : {
        email: payload.email,
        password: payload.password,
        password_confirm: payload.password_confirm,
        full_name: payload.name,
      }

  return apiRequest('POST', isVendor ? API_ROUTES.registerVendor : API_ROUTES.register, { body })
    .then(toAuthState)
}

export function login(payload) {
  return apiRequest('POST', API_ROUTES.login, { body: payload }).then(toAuthState)
}

export function getMe() {
  return apiRequest('GET', API_ROUTES.me)
}
