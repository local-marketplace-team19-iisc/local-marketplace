// Auth state via React Context + useReducer (D2 — Context API, not Redux).
//
// JWT persistence model (revised 2026-06-23):
//   * The JWT is cached in `sessionStorage` — per-tab only, wiped automatically
//     when the tab closes. This is the closest match to the original
//     "in-memory only" intent (architecture D16 / Constitution C-09) that still
//     survives a manual reload, an HMR module replacement during dev, or a
//     fast deep-link from another route. localStorage would survive too long
//     (and is explicitly forbidden by C-09); sessionStorage scopes the token
//     to the same window and dies with it.
//   * On AuthProvider mount we read sessionStorage, push the token into
//     apiClient, and call `GET /auth/me` to verify it server-side. A 401
//     means the token was revoked/expired/forged — we silently clear the
//     cache and the user lands back on `idle` (no error banner, the route
//     guard sends them to login as before).
//   * The eventual production target remains an httpOnly refresh cookie
//     issued by the backend (D2/D16); when that lands the sessionStorage
//     branch goes away in one place.

import { createContext, useEffect, useReducer, useRef } from 'react'
import * as authService from '../services/authService'
import { setAuthToken } from '../services/apiClient'
import { toErrorMessage } from '../utils/helpers'

const SESSION_KEY = 'lm:auth'

function readCachedSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.token) return null
    return parsed
  } catch {
    return null
  }
}

function writeCachedSession(value) {
  try {
    if (value && value.token) sessionStorage.setItem(SESSION_KEY, JSON.stringify(value))
    else sessionStorage.removeItem(SESSION_KEY)
  } catch {
    /* sessionStorage unavailable (private mode, SSR) — fall back to memory only */
  }
}

// Project the `/auth/me` response into the same user shape `authService.login` produces.
function userFromMe(me) {
  return {
    id: me.id,
    email: me.email,
    role: me.user_type,
    vendorId: me.vendor_id || null,
    vendor: me.shop_name || null,
  }
}

const initialState = { user: null, token: null, status: 'idle', error: null }

function reducer(state, action) {
  switch (action.type) {
    case 'AUTH_START':
      return { ...state, status: 'loading', error: null }
    case 'AUTH_SUCCESS':
      return { user: action.user, token: action.token, status: 'authenticated', error: null }
    case 'AUTH_ERROR':
      return { ...state, status: 'error', error: action.error }
    case 'LOGOUT':
      return { ...initialState }
    default:
      return state
  }
}

export const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  // Single-shot guard so React 18 StrictMode (which mounts → unmounts → remounts
  // every effect in dev) doesn't fire two `/auth/me` calls on first paint.
  const restoredRef = useRef(false)

  // Rehydrate on mount: pick up any cached token, then verify it server-side.
  useEffect(() => {
    if (restoredRef.current) return
    restoredRef.current = true

    const cached = readCachedSession()
    if (!cached) return

    setAuthToken(cached.token)
    dispatch({ type: 'AUTH_START' })

    let cancelled = false
    authService
      .getMe()
      .then((me) => {
        if (cancelled) return
        const user = userFromMe(me)
        dispatch({ type: 'AUTH_SUCCESS', token: cached.token, user })
        // Refresh the cached user dict in case backend has newer fields.
        writeCachedSession({ token: cached.token, user })
      })
      .catch(() => {
        if (cancelled) return
        // Token gone bad: wipe quietly. No error banner — the user is simply
        // unauthenticated, and protected routes will redirect them to login.
        setAuthToken(null)
        writeCachedSession(null)
        dispatch({ type: 'LOGOUT' })
      })

    return () => {
      cancelled = true
    }
  }, [])

  async function authenticate(action, payload) {
    dispatch({ type: 'AUTH_START' })
    try {
      const { token, user } = await action(payload)
      setAuthToken(token) // push into apiClient first…
      writeCachedSession({ token, user }) // …then mirror to sessionStorage for reload survival.
      dispatch({ type: 'AUTH_SUCCESS', token, user })
      return user
    } catch (err) {
      dispatch({ type: 'AUTH_ERROR', error: toErrorMessage(err) })
      throw err
    }
  }

  const login = (credentials) => authenticate(authService.login, credentials)
  const register = (payload) => authenticate(authService.register, payload)

  function logout() {
    setAuthToken(null)
    writeCachedSession(null)
    dispatch({ type: 'LOGOUT' })
  }

  const value = {
    user: state.user,
    token: state.token,
    status: state.status,
    error: state.error,
    isAuthenticated: Boolean(state.user),
    login,
    register,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
