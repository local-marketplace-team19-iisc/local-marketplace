// Auth state via React Context + useReducer (D2 — Context API, not Redux).
// The JWT lives in memory only (C-08/C-09): it is pushed into apiClient and never
// written to browser storage, so a page refresh ends the session by design.

import { createContext, useReducer } from 'react'
import * as authService from '../services/authService'
import { setAuthToken } from '../services/apiClient'
import { toErrorMessage } from '../utils/helpers'

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

  async function authenticate(action, payload) {
    dispatch({ type: 'AUTH_START' })
    try {
      const { token, user } = await action(payload)
      setAuthToken(token) // in-memory only (C-09)
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
