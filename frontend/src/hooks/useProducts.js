// Convenience hook to read the Product context (catalog, cart, favorites, orders).
import { useContext } from 'react'
import { ProductContext } from '../store/productContext'

export function useProducts() {
  const ctx = useContext(ProductContext)
  if (!ctx) throw new Error('useProducts must be used within <ProductProvider>.')
  return ctx
}
