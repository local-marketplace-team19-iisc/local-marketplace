import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import './orders.css'
import { useProducts } from '../hooks/useProducts'
import { listOrders } from '../services/orderService'
import { formatPrice, formatDate, toErrorMessage } from '../utils/helpers'
import Loader from '../components/common/Loader'
import Button from '../components/common/Button'

// Cart + checkout + order history (protected route). A cart may span multiple vendors;
// placing it returns a single order number (master SPEC §3).
function OrdersPage() {
  const { cart, cartTotal, cartCount, removeFromCart, placeOrder, loading, error } = useProducts()
  const [orders, setOrders] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState(null)
  const [placedOrder, setPlacedOrder] = useState(null)

  const loadOrders = useCallback(async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const { orders: list } = await listOrders()
      setOrders(list || [])
    } catch (err) {
      setHistoryError(toErrorMessage(err))
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    loadOrders()
  }, [loadOrders])

  async function onPlaceOrder() {
    try {
      const order = await placeOrder()
      setPlacedOrder(order)
      loadOrders()
    } catch {
      /* error surfaced via product context `error` */
    }
  }

  return (
    <div className="container">
      <h1 className="page-title">Your cart &amp; orders</h1>

      {placedOrder ? (
        <div className="form-banner form-banner--info" role="status">
          <strong>Order placed — {placedOrder.orderNumber}</strong>
          <div>
            {placedOrder.items.length} item(s) from {placedOrder.vendors.join(', ')} ·
            total {formatPrice(placedOrder.total)}
          </div>
        </div>
      ) : null}

      {/* ---- Cart ---- */}
      <section className="orders-section">
        <h2>Cart ({cartCount})</h2>
        {error ? <div className="form-banner form-banner--error" role="alert">{error}</div> : null}
        {cart.length === 0 ? (
          <p className="product-list__empty">
            Your cart is empty. <Link to="/search">Browse products</Link>.
          </p>
        ) : (
          <>
            <ul className="cart-list">
              {cart.map(({ product, qty }) => (
                <li key={product.id} className="cart-item">
                  <div>
                    <div className="cart-item__name">{product.name}</div>
                    <div className="cart-item__meta">
                      {product.vendor} · {formatPrice(product.price)} × {qty}
                    </div>
                  </div>
                  <div className="cart-item__right">
                    <span className="cart-item__line">{formatPrice(product.price * qty)}</span>
                    <Button size="sm" variant="ghost" onClick={() => removeFromCart(product.id)}>Remove</Button>
                  </div>
                </li>
              ))}
            </ul>
            <div className="cart-total">
              <span>Total</span>
              <strong>{formatPrice(cartTotal)}</strong>
            </div>
            <Button variant="primary" size="lg" loading={loading} onClick={onPlaceOrder}>
              Place order
            </Button>
          </>
        )}
      </section>

      {/* ---- Order history ---- */}
      <section className="orders-section">
        <h2>Order history</h2>
        {historyError ? <div className="form-banner form-banner--error" role="alert">{historyError}</div> : null}
        {historyLoading ? (
          <Loader label="Loading orders…" />
        ) : orders.length === 0 ? (
          <p className="product-list__empty">No past orders yet.</p>
        ) : (
          <ul className="order-history">
            {orders.map((o) => (
              <li key={o.orderNumber} className="order-history__item">
                <div className="order-history__head">
                  <strong>{o.orderNumber}</strong>
                  <span className="cart-item__meta">{formatDate(o.placedAt)}</span>
                </div>
                <div className="cart-item__meta">
                  {o.items.map((it) => `${it.name} ×${it.qty}`).join(', ')}
                </div>
                <div className="order-history__foot">
                  <span className="cart-item__meta">{o.vendors.join(', ')}</span>
                  <strong>{formatPrice(o.total)}</strong>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export default OrdersPage
