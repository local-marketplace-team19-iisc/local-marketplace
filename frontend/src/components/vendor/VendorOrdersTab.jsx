// Vendor order-history tab. Reads `/api/vendor/orders` — backend partitions
// each order so we only ever see THIS vendor's line items, even if the
// customer's checkout also included items from other shops.
//
// One row per order. Each row expands to show the lines the vendor fulfilled.
// We deliberately do NOT show other vendors on the same order beyond a
// count ("+2 other vendors on this order") — privacy decision logged in
// docs/architecture.md as D-007-1.

import { useEffect, useState } from 'react'
import { listVendorOrders } from '../../services/vendorOrderService'
import { formatPrice, toErrorMessage } from '../../utils/helpers'
import Loader from '../common/Loader'
import Button from '../common/Button'

function formatPlacedAt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

// Collapsed-row summary of the vendor's line items.
//   1 line:   "Parle-G ×2"
//   2 lines:  "Parle-G ×2, Amul Milk ×1"
//   3+ lines: "Parle-G ×2, Amul Milk ×1 (+1 more)"
// We cap at two names so the cell doesn't blow the grid column out on
// large orders; the full breakdown is one click away in the expanded body.
const SUMMARY_MAX = 2
function summarizeProducts(items) {
  if (!items || items.length === 0) return ''
  const head = items
    .slice(0, SUMMARY_MAX)
    .map((ln) => `${ln.name} ×${ln.qty}`)
    .join(', ')
  const extra = items.length - SUMMARY_MAX
  return extra > 0 ? `${head} (+${extra} more)` : head
}

function OrderRow({ order }) {
  const [open, setOpen] = useState(false)
  const totalQty = order.items.reduce((sum, ln) => sum + ln.qty, 0)
  const lineCount = order.items.length
  const otherShops = order.otherVendorsCount
  const productsSummary = summarizeProducts(order.items)
  return (
    <div className="vendor-order" role="row">
      <button
        type="button"
        className="vendor-order__head"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="vendor-order__num">{order.orderNumber}</span>
        <span className="vendor-order__customer">
          {order.customer?.email || order.customer?.id || 'Customer'}
        </span>
        <span className="vendor-order__placed">{formatPlacedAt(order.placedAt)}</span>
        <span className="vendor-order__products" title={productsSummary}>
          {productsSummary}
        </span>
        <span className="vendor-order__subtotal">{formatPrice(order.vendorSubtotal)}</span>
        <span className={`badge badge--${order.status === 'placed' ? 'ok' : 'off'}`}>
          {order.status}
        </span>
        <span className="vendor-order__chevron" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
      </button>
      {open ? (
        <div className="vendor-order__body">
          {/* Quiet footnote: the line/item counts are useful here (e.g.
              "3 of your products, 7 items total") but were noise in the
              collapsed row. */}
          <p className="vendor-order__counts">
            {lineCount} of your product{lineCount === 1 ? '' : 's'} · {totalQty} item
            {totalQty === 1 ? '' : 's'} total
          </p>
          {otherShops > 0 ? (
            <p className="vendor-order__shared">
              This order also includes items from {otherShops} other vendor
              {otherShops === 1 ? '' : 's'}. Only your line items are shown below.
            </p>
          ) : null}
          <div className="vendor-order__items" role="table">
            <div className="vendor-order__item vendor-order__item--head" role="row">
              <span role="columnheader">Product</span>
              <span role="columnheader">Brand</span>
              <span role="columnheader">Qty</span>
              <span role="columnheader">Unit price</span>
              <span role="columnheader">Line total</span>
            </div>
            {order.items.map((ln) => (
              <div className="vendor-order__item" role="row" key={ln.id}>
                <span role="cell" data-label="Product">{ln.name}</span>
                <span role="cell" data-label="Brand">{ln.brand}</span>
                <span role="cell" data-label="Qty">{ln.qty}</span>
                <span role="cell" data-label="Unit price">{formatPrice(ln.unitPrice)}</span>
                <span role="cell" data-label="Line total">{formatPrice(ln.lineTotal)}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function VendorOrdersTab() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { orders: all } = await listVendorOrders()
      setOrders(all || [])
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <Loader label="Loading your orders…" fullPage />

  return (
    <div>
      <div className="vendor-head">
        <h2 className="page-title">Orders for you</h2>
        <Button variant="secondary" size="sm" onClick={load}>
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="form-banner form-banner--error" role="alert">
          {error}
        </div>
      ) : null}

      {orders.length === 0 ? (
        <p className="product-list__empty">
          No orders yet. When customers buy your products, they&apos;ll appear here.
        </p>
      ) : (
        <div className="vendor-orders" role="table" aria-label="Your orders">
          {orders.map((o) => (
            <OrderRow order={o} key={o.orderNumber} />
          ))}
        </div>
      )}
    </div>
  )
}

export default VendorOrdersTab
