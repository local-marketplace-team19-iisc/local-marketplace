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
import { registerUnauthorizedHandler, setAuthToken } from '../services/apiClient'
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
  // Guard against the mid-session-expiry handler firing more than once for
  // the same expired token (e.g. several concurrent requests all returning
  // 401). First call wipes; the rest see a cleared token and become no-ops.
  const expiredRef = useRef(false)

  // Idempotent session wipe — called from both the rehydrate catch path and
  // the mid-session 401 interceptor. Cleans apiClient + sessionStorage +
  // reducer in the same order every time so there's only one source of truth.
  function clearSession() {
    setAuthToken(null)
    writeCachedSession(null)
    dispatch({ type: 'LOGOUT' })
  }

  // Rehydrate on mount: pick up any cached token, then verify it server-side.
  useEffect(() => {
    if (restoredRef.current) return
    restoredRef.current = true

    const cached = readCachedSession()
    if (!cached) return

    setAuthToken(cached.token)
    dispatch({ type: 'AUTH_START' })

    // Note: we deliberately do NOT cancel the in-flight `/auth/me` call when
    // React 18 StrictMode unmounts the effect on its dev-only second
    // invocation. An earlier version had a `cancelled` flag that short-
    // circuited both `.then` and `.catch`, which on the first mount left
    // `status` pinned at 'loading' forever — disabling the Login / Register
    // submit buttons on a freshly-opened tab that still had a stale
    // session-storage cache. The `restoredRef` guard above already prevents
    // a duplicate fetch on the second mount; letting the original promise
    // settle is harmless and guarantees status converges to either
    // 'authenticated' or 'idle'.
    authService
      .getMe()
      .then((me) => {
        const user = userFromMe(me)
        dispatch({ type: 'AUTH_SUCCESS', token: cached.token, user })
        // Refresh the cached user dict in case backend has newer fields.
        writeCachedSession({ token: cached.token, user })
      })
      .catch(() => {
        // Token gone bad: wipe quietly. No error banner — the user is simply
        // unauthenticated, and protected routes will redirect them to login.
        // Mark expiredRef so the apiClient interceptor (which also fires for
        // this same 401) doesn't try to redirect on top of us.
        expiredRef.current = true
        clearSession()
      })
  }, [])

  // Global mid-session expiry interceptor. apiClient calls the registered
  // handler whenever an authenticated request returns 401. We wipe the
  // session and bounce to /login with a `next=` query so login can send the
  // user back to whatever they were doing.
  //
  // Design notes:
  //   * We avoid redirecting if the user is already on /login or /register
  //     (a login failure also surfaces as 401 and is handled locally with a
  //     banner; we mustn't yank them off their own page).
  //   * We use `window.location.assign` rather than react-router's navigate
  //     because the interceptor can fire from anywhere — including modules
  //     loaded before the Router is mounted, or background fetches that
  //     completed after a navigation. Hard navigation is the only thing
  //     guaranteed to work in every case.
  //   * The `expiredRef` guard means a single expired token only triggers
  //     one redirect, even when 4 components on the page all fired their
  //     `useEffect`-driven fetch at once.
  useEffect(() => {
    registerUnauthorizedHandler(() => {
      if (expiredRef.current) return
      expiredRef.current = true

      const path = window.location.pathname || '/'
      const onAuthPage = path.startsWith('/login') || path.startsWith('/register')

      clearSession()

      if (!onAuthPage) {
        const next = encodeURIComponent(path + window.location.search)
        window.location.assign(`/login?next=${next}&reason=expired`)
      }
    })
    return () => registerUnauthorizedHandler(null)
  }, [])

  async function authenticate(action, payload) {
    dispatch({ type: 'AUTH_START' })
    try {
      const { token, user } = await action(payload)
      setAuthToken(token) // push into apiClient first…
      writeCachedSession({ token, user }) // …then mirror to sessionStorage for reload survival.
      // Fresh token — re-arm the mid-session expiry guard so the next
      // expiry can trigger another redirect.
      expiredRef.current = false
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
