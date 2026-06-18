import './ProductList.css'
import ProductCard from './ProductCard'

// Responsive grid of product cards with a friendly empty state (AC-04).
function ProductList({ products, emptyMessage = 'No products found.' }) {
  if (!products || products.length === 0) {
    return <p className="product-list__empty">{emptyMessage}</p>
  }
  return (
    <div className="product-list">
      {products.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  )
}

export default ProductList
