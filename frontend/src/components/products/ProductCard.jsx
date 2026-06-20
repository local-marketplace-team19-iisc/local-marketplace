import { Link } from 'react-router-dom'
import './ProductCard.css'
import { useProducts } from '../../hooks/useProducts'
import { formatPrice } from '../../utils/helpers'
import Button from '../common/Button'

// Product summary card. Shows the AC-10 fields (name, price, vendor, rating,
// availability) and offers favorite + add-to-cart actions. Works for both catalog
// products and search results (which omit stock — availability drives the UI).
function ProductCard({ product }) {
  const { isFavorite, toggleFavorite, addToCart } = useProducts()
  const fav = isFavorite(product.id)
  const available = product.availability !== false

  return (
    <article className="product-card">
      <div className="product-card__body">
        <Link to={`/product/${product.id}`} className="product-card__name">{product.name}</Link>
        <div className="product-card__price">{formatPrice(product.price)}</div>
        <div className="product-card__meta">
          <span>{product.vendor}</span>
          {product.rating ? <span aria-label={`Rated ${product.rating} out of 5`}>★ {product.rating}</span> : null}
        </div>
        <span className={available ? 'badge badge--ok' : 'badge badge--off'}>
          {available ? 'In stock' : 'Out of stock'}
        </span>
      </div>
      <div className="product-card__actions">
        <Button size="sm" variant="primary" disabled={!available} onClick={() => addToCart(product)}>
          Add to cart
        </Button>
        <button
          type="button"
          className="product-card__fav"
          aria-pressed={fav}
          aria-label={fav ? 'Remove from favorites' : 'Add to favorites'}
          onClick={() => toggleFavorite(product)}
        >
          {fav ? '♥' : '♡'}
        </button>
      </div>
    </article>
  )
}

export default ProductCard
