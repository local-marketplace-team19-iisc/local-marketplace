import { useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import './Navbar.css'
import logo from '../../assets/images/logo.svg'
import { useAuth } from '../../hooks/useAuth'
import { useProducts } from '../../hooks/useProducts'
import { ROLES } from '../../utils/constants'
import { classNames } from '../../utils/helpers'

// Top navigation. Links adapt to auth state and role (vendor sees the dashboard).
// Collapses to a toggle menu on small screens (AC-02/AC-07).
function Navbar() {
  const { isAuthenticated, user, logout } = useAuth()
  const { cartCount } = useProducts()
  const navigate = useNavigate()
  // Resolve once: `pathname` for the home-page dark-navbar variant from
  // upstream, and the full `location` for the query-aware vendor-link
  // active predicates added in this branch (?tab=orders).
  const location = useLocation()
  const { pathname } = location
  const [open, setOpen] = useState(false)
  const isHome = pathname === '/'

  const close = () => setOpen(false)

  function handleLogout() {
    logout()
    close()
    navigate('/login')
  }

  const linkClass = ({ isActive }) => classNames('navbar__link', isActive && 'navbar__link--active')

  // Both vendor links (`Products`, `Orders`) share the `/vendor` pathname and
  // are disambiguated by the `?tab=` query. NavLink's default active rule
  // matches on pathname only, so both would light up at the same time. These
  // bespoke predicates fix that by also looking at the current query.
  const vendorProductsActive =
    location.pathname === '/vendor' && new URLSearchParams(location.search).get('tab') !== 'orders'
  const vendorOrdersActive =
    location.pathname === '/vendor' && new URLSearchParams(location.search).get('tab') === 'orders'
  const vendorLinkClass = (active) => classNames('navbar__link', active && 'navbar__link--active')
  const username = user?.email ? user.email.split('@')[0] : null
  const userLabel = user?.name || username || user?.vendor

  return (
    <header className={isHome ? 'navbar navbar--dark' : 'navbar'}>
      <div className="navbar__inner container">
        <NavLink to="/" className="navbar__brand" onClick={close}>
          <img src={logo} alt="Local Marketplace" height="28" />
        </NavLink>

        <button
          type="button"
          className="navbar__toggle"
          aria-expanded={open}
          aria-controls="navbar-menu"
          aria-label="Toggle navigation menu"
          onClick={() => setOpen((v) => !v)}
        >
          <span aria-hidden="true">{open ? '✕' : '☰'}</span>
        </button>

        <nav id="navbar-menu" className={classNames('navbar__menu', open && 'navbar__menu--open')}>
          <NavLink to="/search" className={linkClass} onClick={close}>Search</NavLink>
          <NavLink to="/chat" className={linkClass} onClick={close}>Chatbot</NavLink>

          {/* Customer-only links — favourites + cart/orders. Vendors get their
              own dashboard tabs further down, and `/orders` is the customer
              history page (it 403s for vendors at the API layer). */}
          {isAuthenticated && user?.role === ROLES.CUSTOMER && (
            <>
              <NavLink to="/favorites" className={linkClass} onClick={close}>Favorites</NavLink>
              <NavLink to="/orders" className={linkClass} onClick={close}>
                Orders{cartCount > 0 ? ` (cart: ${cartCount})` : ''}
              </NavLink>
            </>
          )}

          {/* Vendor-only links. The Orders link deep-links into VendorPage's
              "Orders" tab via `?tab=orders` (read in VendorPage) so the
              navbar entry and the in-page tab toggle stay in sync. */}
          {isAuthenticated && user?.role === ROLES.VENDOR && (
            <>
              <NavLink to="/dashboard" className={linkClass} onClick={close}>Dashboard</NavLink>
              <NavLink to="/vendor" className={vendorLinkClass(vendorProductsActive)} onClick={close} end>
                Products
              </NavLink>
              <NavLink to="/vendor?tab=orders" className={vendorLinkClass(vendorOrdersActive)} onClick={close}>
                Orders
              </NavLink>
            </>
          )}

          {isAuthenticated ? (
            <>
              {userLabel ? (
                <span className="navbar__user" title={userLabel}>
                  {userLabel}
                </span>
              ) : null}
              <button type="button" className="navbar__link navbar__logout" onClick={handleLogout}>
                Logout
              </button>
            </>
          ) : (
            <NavLink to="/login" className={linkClass} onClick={close}>Login</NavLink>
          )}
        </nav>
      </div>
    </header>
  )
}

export default Navbar
