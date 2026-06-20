import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getProduct } from '../services/productService'
import ProductDetails from '../components/products/ProductDetails'
import Loader from '../components/common/Loader'
import { toErrorMessage } from '../utils/helpers'

// Single product page. Fetches by route param; renders details once loaded.
function ProductPage() {
  const { id } = useParams()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    getProduct(id)
      .then(({ product: p }) => {
        if (active) setProduct(p)
      })
      .catch((err) => {
        if (active) setError(toErrorMessage(err))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [id])

  return (
    <div className="container">
      <p style={{ margin: '16px 0' }}>
        <Link to="/search">← Back to search</Link>
      </p>
      {loading ? (
        <Loader label="Loading product…" fullPage />
      ) : error ? (
        <div className="form-banner form-banner--error" role="alert">{error}</div>
      ) : product ? (
        <ProductDetails product={product} />
      ) : null}
    </div>
  )
}

export default ProductPage
