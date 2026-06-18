import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import './Navbar.css'
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
  const [open, setOpen] = useState(false)

  const close = () => setOpen(false)

  function handleLogout() {
    logout()
    close()
    navigate('/login')
  }

  const linkClass = ({ isActive }) => classNames('navbar__link', isActive && 'navbar__link--active')

  return (
    <header className="navbar">
      <div className="navbar__inner container">
        <NavLink to="/" className="navbar__brand" onClick={close}>
          <img src="/logo.svg" alt="Local Marketplace" height="28" />
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

          {isAuthenticated && (
            <>
              <NavLink to="/favorites" className={linkClass} onClick={close}>Favorites</NavLink>
              <NavLink to="/orders" className={linkClass} onClick={close}>
                Orders{cartCount > 0 ? ` (cart: ${cartCount})` : ''}
              </NavLink>
            </>
          )}

          {isAuthenticated && user?.role === ROLES.VENDOR && (
            <>
              <NavLink to="/dashboard" className={linkClass} onClick={close}>Dashboard</NavLink>
              <NavLink to="/vendor" className={linkClass} onClick={close}>Products</NavLink>
            </>
          )}

          {isAuthenticated ? (
            <button type="button" className="navbar__link navbar__logout" onClick={handleLogout}>
              Logout{user?.name ? ` (${user.name})` : ''}
            </button>
          ) : (
            <NavLink to="/login" className={linkClass} onClick={close}>Login</NavLink>
          )}
        </nav>
      </div>
    </header>
  )
}

export default Navbar
