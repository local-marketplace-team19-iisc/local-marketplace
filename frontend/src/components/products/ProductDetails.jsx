import { useState } from 'react'
import './ProductDetails.css'
import { useProducts } from '../../hooks/useProducts'
import { formatPrice } from '../../utils/helpers'
import Button from '../common/Button'

// Full product view used by ProductPage. Supports quantity selection, favorite toggle,
// and add-to-cart.
function ProductDetails({ product }) {
  const { isFavorite, toggleFavorite, addToCart } = useProducts()
  const [qty, setQty] = useState(1)
  const fav = isFavorite(product.id)
  const available = product.availability !== false
  const maxQty = typeof product.stock === 'number' ? product.stock : 99

  return (
    <div className="product-details">
      <div className="product-details__main">
        <h1 className="product-details__name">{product.name}</h1>
        <div className="product-details__price">{formatPrice(product.price)}</div>
        <p className="product-details__meta">
          Sold by <strong>{product.vendor}</strong>
          {product.rating ? <span> · ★ {product.rating}</span> : null}
          {product.category ? <span> · {product.category}</span> : null}
        </p>
        <span className={available ? 'badge badge--ok' : 'badge badge--off'}>
          {available ? `In stock${typeof product.stock === 'number' ? ` (${product.stock})` : ''}` : 'Out of stock'}
        </span>
        {product.description ? <p className="product-details__desc">{product.description}</p> : null}
      </div>

      <div className="product-details__buy">
        <label className="product-details__qty">
          <span>Qty</span>
          <input
            type="number"
            min="1"
            max={maxQty}
            value={qty}
            onChange={(e) => setQty(Math.max(1, Math.min(maxQty, Number(e.target.value) || 1)))}
            disabled={!available}
          />
        </label>
        <Button variant="primary" disabled={!available} onClick={() => addToCart(product, qty)}>
          Add to cart
        </Button>
        <Button variant="secondary" aria-pressed={fav} onClick={() => toggleFavorite(product)}>
          {fav ? '♥ Favorited' : '♡ Favorite'}
        </Button>
      </div>
    </div>
  )
}

export default ProductDetails
