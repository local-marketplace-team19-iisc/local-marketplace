import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import '../assets/styles/forms.css'
import './auth.css'
import { useAuth } from '../hooks/useAuth'
import { validateLoginForm } from '../utils/validators'
import Button from '../components/common/Button'

// Login page (AC-07). On success, redirects to the route the user was sent here from
// (ProtectedRoute → AC-08), defaulting to home.
function LoginPage() {
  const { login, status, error } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/'

  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState({})
  const loading = status === 'loading'

  function update(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  async function onSubmit(e) {
    e.preventDefault()
    const found = validateLoginForm(form)
    setErrors(found)
    if (Object.keys(found).length > 0) return
    try {
      await login(form)
      navigate(from, { replace: true })
    } catch {
      /* error surfaced via auth context `error` */
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card__title">Welcome back</h1>
        <p className="auth-card__subtitle">Log in to your Local Marketplace account.</p>

        {error ? <div className="form-banner form-banner--error" role="alert">{error}</div> : null}

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

          <Button type="submit" variant="primary" className="btn--block" loading={loading}>
            Log in
          </Button>
        </form>

        <p className="form-hint" style={{ marginTop: '14px' }}>
          Demo accounts: <code>customer@demo.com</code> / <code>vendor@demo.com</code> — password <code>demo1234</code>.
        </p>
        <p className="auth-card__footer">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </div>
  )
}

export default LoginPage
