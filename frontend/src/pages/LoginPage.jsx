import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import '../assets/styles/forms.css'
import './auth.css'
import { useAuth } from '../hooks/useAuth'
import { validateLoginForm } from '../utils/validators'
import { toErrorMessage } from '../utils/helpers'
import Button from '../components/common/Button'

// Login page (AC-07). On success, redirects to:
//   1. `?next=` query string (set by the mid-session 401 interceptor in
//      AuthProvider when an expired token boots the user back here), OR
//   2. `location.state.from.pathname` (set by ProtectedRoute when the
//      user navigated to a guarded route without being signed in), OR
//   3. `/search` — the searchable catalogue is the most useful default
//      landing surface for a signed-in user (per product spec).
//
// The `?reason=expired` query param surfaces an info banner so the user
// understands why they were sent back here.
function LoginPage() {
  // We deliberately do NOT read `status` from the auth context here. It
  // also flips to 'loading' during the mount-time `/auth/me` rehydrate
  // (D-004-16), which used to leak through and disable the Login button
  // on a freshly-opened tab with a stale sessionStorage cache. The form
  // tracks its own `submitting` state instead.
  const { login, error } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const searchParams = new URLSearchParams(location.search)
  const nextParam = searchParams.get('next')
  const expired = searchParams.get('reason') === 'expired'
  // Decode the path the interceptor stashed; reject anything that doesn't
  // look like a same-origin path to prevent open-redirect on /login?next=…
  let nextFromQuery = null
  if (nextParam) {
    try {
      const decoded = decodeURIComponent(nextParam)
      if (decoded.startsWith('/') && !decoded.startsWith('//')) {
        nextFromQuery = decoded
      }
    } catch {
      /* ignore malformed next param */
    }
  }
  // Default post-login destination is `/search` (per product spec — the
  // user lands directly on the searchable catalogue and can start using
  // the SBERT-backed search/voice flows immediately). `?next=` from the
  // mid-session expiry redirect still wins, as does `location.state.from`
  // set by ProtectedRoute when the user originally bumped into a guarded
  // route.
  const from = nextFromQuery || location.state?.from?.pathname || '/search'

  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [statusBanner, setStatusBanner] = useState(
    expired
      ? { type: 'error', message: 'Your session expired — please log in again.' }
      : null,
  )
  // Local submitting state — reflects ONLY this form's in-flight POST.
  const [submitting, setSubmitting] = useState(false)

  function update(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  async function onSubmit(e) {
    e.preventDefault()
    const found = validateLoginForm(form)
    setErrors(found)
    setStatusBanner(null)
    if (Object.keys(found).length > 0) return
    setSubmitting(true)
    try {
      const user = await login(form)
      // Navigate IMMEDIATELY — do not setTimeout.
      //
      // Why: `AppProviders` wraps the routed app in a `PerIdentityProviders`
      // keyed by `user?.id ?? 'guest'`. The moment `login()` succeeds the
      // key flips from 'guest' to the real user id, which forces React to
      // unmount the entire children subtree (including this component) and
      // remount a fresh copy. Any deferred work scheduled from this render
      // — a `setTimeout`, a `Promise.then` that touches local state — fires
      // against an unmounted component and is silently lost.
      //
      // The 900ms "Status OK" banner-then-redirect dance used to live here
      // ran straight into that. The user saw a flash of the success banner,
      // the providers remounted, LoginPage was rebuilt fresh (empty form,
      // no banner, no submitting flag), and the queued `navigate(from)`
      // never fired. Symptom: stuck on the login card with no feedback.
      //
      // Synchronous `navigate()` happens in the same task as `setAuthToken`
      // + the auth reducer dispatch, so the URL change and the identity
      // change land together: by the time PerIdentityProviders re-renders
      // with the new key, the route has already moved to `from`, and what
      // remounts is the destination page (HomePage etc.), not a fresh
      // LoginPage. HomePage reads `location.state.authStatus` to show the
      // success banner on the page the user just arrived at.
      navigate(from, {
        replace: true,
        state: {
          authStatus: `Status OK: logged in successfully as ${user?.role || 'user'}.`,
        },
      })
    } catch (err) {
      setStatusBanner({
        type: 'error',
        message: `Status Failed: ${toErrorMessage(err, 'Unable to login.')}`,
      })
      setSubmitting(false)
    }
    // NOTE: on the success path we deliberately do NOT clear `submitting`.
    // The component is about to unmount; flipping state on an unmounted
    // component is a no-op and would just log a dev-mode warning.
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card__title">Welcome back</h1>
        <p className="auth-card__subtitle">Log in to your Local Marketplace account.</p>

        {error && !statusBanner ? (
          <div className="form-banner form-banner--error" role="alert">Status Failed: {error}</div>
        ) : null}
        {statusBanner ? (
          <div className={`form-banner form-banner--${statusBanner.type}`} role={statusBanner.type === 'success' ? 'status' : 'alert'}>
            {statusBanner.message}
          </div>
        ) : null}

        <form onSubmit={onSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="email">Email</label>
            <input
              className="form-input"
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={update}
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? 'email-error' : undefined}
            />
            {errors.email ? <span className="form-error" id="email-error">{errors.email}</span> : null}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              className="form-input"
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={form.password}
              onChange={update}
              aria-invalid={Boolean(errors.password)}
              aria-describedby={errors.password ? 'password-error' : undefined}
            />
            {errors.password ? <span className="form-error" id="password-error">{errors.password}</span> : null}
          </div>

          <Button type="submit" variant="primary" className="btn--block" loading={submitting}>
            Log in
          </Button>
        </form>

        <p className="form-hint" style={{ marginTop: '14px' }}>
          No demo accounts are seeded — use <Link to="/register">Create an account</Link>{' '}
          to sign up as a customer or vendor in seconds.
        </p>
        <p className="auth-card__footer">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </div>
  )
}

export default LoginPage
