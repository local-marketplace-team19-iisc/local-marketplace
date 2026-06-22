import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import '../assets/styles/forms.css'
import './auth.css'
import { useAuth } from '../hooks/useAuth'
import { validateRegisterForm } from '../utils/validators'
import { ROLES } from '../utils/constants'
import { classNames } from '../utils/helpers'
import Button from '../components/common/Button'

// Registration page (AC-06). Customers and vendors register here; vendors land on the
// vendor dashboard, customers on home.
function RegisterPage() {
  const { register, status, error } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({ name: '', email: '', password: '', role: ROLES.CUSTOMER })
  const [errors, setErrors] = useState({})
  const loading = status === 'loading'

  function update(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }
  function setRole(role) {
    setForm((f) => ({ ...f, role }))
  }

  async function onSubmit(e) {
    e.preventDefault()
    const found = validateRegisterForm(form)
    setErrors(found)
    if (Object.keys(found).length > 0) return
    try {
      const user = await register(form)
      navigate(user?.role === ROLES.VENDOR ? '/vendor' : '/', { replace: true })
    } catch {
      /* error surfaced via auth context `error` */
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card__title">Create your account</h1>
        <p className="auth-card__subtitle">Join as a customer to shop, or as a vendor to sell.</p>

        {error ? <div className="form-banner form-banner--error" role="alert">{error}</div> : null}

        <form onSubmit={onSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="name">Full name</label>
            <input
              className="form-input"
              id="name"
              name="name"
              type="text"
              autoComplete="name"
              value={form.name}
              onChange={update}
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'name-error' : undefined}
            />
            {errors.name ? <span className="form-error" id="name-error">{errors.name}</span> : null}
          </div>

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
              autoComplete="new-password"
              value={form.password}
              onChange={update}
              aria-invalid={Boolean(errors.password)}
              aria-describedby={errors.password ? 'password-error' : 'password-hint'}
            />
            {errors.password ? (
              <span className="form-error" id="password-error">{errors.password}</span>
            ) : (
              <span className="form-hint" id="password-hint">At least 8 characters.</span>
            )}
          </div>

          <div className="form-group">
            <span className="form-label" id="role-label">Account type</span>
            <div className="auth-role" role="radiogroup" aria-labelledby="role-label">
              {[
                { value: ROLES.CUSTOMER, label: 'Customer' },
                { value: ROLES.VENDOR, label: 'Vendor' },
              ].map((opt) => (
                <label
                  key={opt.value}
                  className={classNames('auth-role__option', form.role === opt.value && 'auth-role__option--active')}
                >
                  <input
                    type="radio"
                    name="role"
                    value={opt.value}
                    checked={form.role === opt.value}
                    onChange={() => setRole(opt.value)}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          <Button type="submit" variant="primary" className="btn--block" loading={loading}>
            Create account
          </Button>
        </form>

        <p className="auth-card__footer">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  )
}

export default RegisterPage
