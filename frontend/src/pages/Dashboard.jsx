import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import './vendor.css'
import { useAuth } from '../hooks/useAuth'
import { listProducts } from '../services/productService'
import { formatPrice, toErrorMessage } from '../utils/helpers'
import Loader from '../components/common/Loader'

// Vendor overview: at-a-glance inventory stats and a link to manage listings.
// Vendor-gated by ProtectedRoute.
function Dashboard() {
  const { user } = useAuth()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { products: all } = await listProducts()
      setProducts(all.filter((p) => p.vendorId === user?.vendorId))
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [user?.vendorId])

  useEffect(() => {
    load()
  }, [load])

  const totalProducts = products.length
  const outOfStock = products.filter((p) => p.stock <= 0).length
  const units = products.reduce((sum, p) => sum + p.stock, 0)
  const inventoryValue = products.reduce((sum, p) => sum + p.price * p.stock, 0)

  const stats = [
    { label: 'Products', value: totalProducts },
    { label: 'Units in stock', value: units },
    { label: 'Out of stock', value: outOfStock },
    { label: 'Inventory value', value: formatPrice(inventoryValue) },
  ]

  return (
    <div className="container">
      <div className="vendor-head">
        <h1 className="page-title">Dashboard{user?.vendor ? ` · ${user.vendor}` : ''}</h1>
        <Link className="btn btn--primary btn--md" to="/vendor">Manage products</Link>
      </div>

      {error ? <div className="form-banner form-banner--error" role="alert">{error}</div> : null}

      {loading ? (
        <Loader label="Loading dashboard…" fullPage />
      ) : (
        <div className="dashboard-stats">
          {stats.map((s) => (
            <div className="stat-card" key={s.label}>
              <div className="stat-card__value">{s.value}</div>
              <div className="stat-card__label">{s.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Dashboard
