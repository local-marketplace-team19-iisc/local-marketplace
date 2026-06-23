import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import '../assets/styles/forms.css'
import './auth.css'
import { useAuth } from '../hooks/useAuth'
import { validateRegisterForm } from '../utils/validators'
import { ROLES } from '../utils/constants'
import { classNames, toErrorMessage } from '../utils/helpers'
import Button from '../components/common/Button'

// Registration page (AC-06). Customers and vendors register here; vendors land on the
// vendor dashboard, customers on home.
function RegisterPage() {
  // See LoginPage for why we don't read `status` here — the auth context's
  // rehydrate flag would otherwise leak in and disable the submit button.
  const { register, error } = useAuth()
  const navigate = useNavigate()

  // V1 vendor registration only collects shop name + (optional) description.
  // Lat/lon were dropped from the UI because the marketplace doesn't ship
  // a location-based search yet and asking users to type raw coordinates
  // was poor UX. The backend treats `location` as optional and stores a
  // (0, 0) placeholder until we add a real geocoding step.
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    password_confirm: '',
    role: ROLES.CUSTOMER,
    shop_name: '',
    shop_description: '',
  })
  const [errors, setErrors] = useState({})
  const [statusBanner, setStatusBanner] = useState(null)
  const [submitting, setSubmitting] = useState(false)

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
    setStatusBanner(null)
    if (Object.keys(found).length > 0) return
    setSubmitting(true)
    try {
      const user = await register(form)
      // Navigate immediately, no setTimeout. The `PerIdentityProviders`
      // unmount-on-identity-change pattern means deferred navigations
      // schedule against a component that's about to be torn down. See
      // the matching comment in LoginPage.onSubmit for the full story.
      navigate(user?.role === ROLES.VENDOR ? '/vendor' : '/search', {
        replace: true,
        state: {
          authStatus: `Status OK: registration successful. Logged in as ${user?.role || 'user'}.`,
        },
      })
    } catch (err) {
      setStatusBanner({
        type: 'error',
        message: `Status Failed: ${toErrorMessage(err, 'Unable to register.')}`,
      })
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card__title">Create your account</h1>
        <p className="auth-card__subtitle">Join as a customer to shop, or as a vendor to sell.</p>

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
            <label className="form-label" htmlFor="password_confirm">Confirm password</label>
            <input
              className="form-input"
              id="password_confirm"
              name="password_confirm"
              type="password"
              autoComplete="new-password"
              value={form.password_confirm}
              onChange={update}
              aria-invalid={Boolean(errors.password_confirm)}
              aria-describedby={errors.password_confirm ? 'password-confirm-error' : undefined}
            />
            {errors.password_confirm ? (
              <span className="form-error" id="password-confirm-error">{errors.password_confirm}</span>
            ) : null}
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

          {form.role === ROLES.VENDOR ? (
            <>
              <div className="form-group">
                <label className="form-label" htmlFor="shop_name">Shop name</label>
                <input
                  className="form-input"
                  id="shop_name"
                  name="shop_name"
                  type="text"
                  value={form.shop_name}
                  onChange={update}
                  aria-invalid={Boolean(errors.shop_name)}
                  aria-describedby={errors.shop_name ? 'shop-name-error' : undefined}
                />
                {errors.shop_name ? <span className="form-error" id="shop-name-error">{errors.shop_name}</span> : null}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="shop_description">Shop description</label>
                <textarea
                  className="form-input"
                  id="shop_description"
                  name="shop_description"
                  rows="3"
                  value={form.shop_description}
                  onChange={update}
                />
              </div>
            </>
          ) : null}

          <Button type="submit" variant="primary" className="btn--block" loading={submitting}>
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
