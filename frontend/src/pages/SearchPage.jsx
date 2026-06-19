import { useEffect, useState, useCallback } from 'react'
import './search.css'
import '../assets/styles/forms.css'
import { searchProducts, searchByImage } from '../services/searchService'
import ProductList from '../components/products/ProductList'
import Loader from '../components/common/Loader'
import Button from '../components/common/Button'
import VoiceButton from '../components/common/VoiceButton'
import { toErrorMessage } from '../utils/helpers'

// Customer product search (AC-09). Results show name/price/vendor/rating/availability
// via ProductCard (AC-10) and arrive cheapest-first from the API.
function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searched, setSearched] = useState(false)
  const [image, setImage] = useState(null)

  const runSearch = useCallback(async (q) => {
    setLoading(true)
    setError(null)
    try {
      const { results: found } = await searchProducts(q)
      setResults(found || [])
    } catch (err) {
      setError(toErrorMessage(err))
      setResults([])
    } finally {
      setLoading(false)
      setSearched(true)
    }
  }, [])

  // Initial load lists all in-stock products.
  useEffect(() => {
    runSearch('')
  }, [runSearch])

  function onSubmit(e) {
    e.preventDefault()
    runSearch(query.trim())
  }

  // Image-based search (AC-09, D8). Mocked vision in dev.
  async function onImageSearch() {
    if (!image) return
    setLoading(true)
    setError(null)
    try {
      const { results: found } = await searchByImage(image)
      setResults(found || [])
    } catch (err) {
      setError(toErrorMessage(err))
      setResults([])
    } finally {
      setLoading(false)
      setSearched(true)
    }
  }

  return (
    <div className="container">
      <h1 className="page-title">Search products</h1>

      <form className="search-bar" onSubmit={onSubmit} role="search">
        <label className="visually-hidden" htmlFor="search-input">Search products</label>
        <input
          id="search-input"
          className="search-bar__input"
          type="search"
          placeholder="Try “tomatoes”, “milk”, “bakery”…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <VoiceButton onText={(t) => { setQuery(t); runSearch(t) }} title="Search by voice" disabled={loading} />
        <Button type="submit" variant="primary" loading={loading}>Search</Button>
      </form>

      <div className="search-image">
        <label className="form-label" htmlFor="image-search">Or search by image</label>
        <div className="search-image__row">
          <input
            id="image-search"
            className="form-input"
            type="file"
            accept="image/*"
            onChange={(e) => setImage(e.target.files?.[0] || null)}
          />
          <Button type="button" variant="secondary" disabled={!image} loading={loading} onClick={onImageSearch}>
            <img src="/image.gif" alt="" aria-hidden="true" className="icon-gif" /> Search by image
          </Button>
        </div>
      </div>

      {error ? <div className="form-banner form-banner--error" role="alert">{error}</div> : null}

      {loading ? (
        <Loader label="Searching products…" fullPage />
      ) : (
        <ProductList
          products={results}
          emptyMessage={searched ? 'No matching in-stock products found.' : 'Start typing to search.'}
        />
      )}
    </div>
  )
}

export default SearchPage
