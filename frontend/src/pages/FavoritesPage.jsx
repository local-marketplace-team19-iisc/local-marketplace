import { useProducts } from '../hooks/useProducts'
import ProductList from '../components/products/ProductList'

// Customer favorites (protected route). Favorites live in the Product context for the
// session.
function FavoritesPage() {
  const { favorites } = useProducts()
  return (
    <div className="container">
      <h1 className="page-title">Your favorites</h1>
      <ProductList products={favorites} emptyMessage="You haven't favorited any products yet." />
    </div>
  )
}

export default FavoritesPage
