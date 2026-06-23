// Product/catalog state via Context + useReducer (D2). Owns the catalog, vendor CRUD,
// the favorites list, the multi-vendor cart, and order placement/listing. UI components
// read from here and call these actions — they hold no business logic themselves (C-04).

import { createContext, useReducer } from 'react'
import * as productService from '../services/productService'
import * as searchService from '../services/searchService'
import * as orderService from '../services/orderService'
import { toErrorMessage } from '../utils/helpers'

const initialState = {
  products: [],
  searchResults: [],
  favorites: [],
  cart: [], // [{ product, qty }]
  orders: [],
  loading: false,
  error: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'LOADING':
      return { ...state, loading: true, error: null }
    case 'ERROR':
      return { ...state, loading: false, error: action.error }
    case 'SET_PRODUCTS':
      return { ...state, loading: false, products: action.products }
    case 'SET_RESULTS':
      return { ...state, loading: false, searchResults: action.results }
    case 'SET_ORDERS':
      return { ...state, loading: false, orders: action.orders }
    case 'UPSERT_PRODUCT': {
      const exists = state.products.some((p) => p.id === action.product.id)
      const products = exists
        ? state.products.map((p) => (p.id === action.product.id ? action.product : p))
        : [...state.products, action.product]
      return { ...state, loading: false, products }
    }
    case 'REMOVE_PRODUCT':
      return { ...state, loading: false, products: state.products.filter((p) => p.id !== action.id) }
    case 'TOGGLE_FAVORITE': {
      const isFav = state.favorites.some((p) => p.id === action.product.id)
      const favorites = isFav
        ? state.favorites.filter((p) => p.id !== action.product.id)
        : [...state.favorites, action.product]
      return { ...state, favorites }
    }
    case 'ADD_TO_CART': {
      const existing = state.cart.find((c) => c.product.id === action.product.id)
      const cart = existing
        ? state.cart.map((c) =>
            c.product.id === action.product.id ? { ...c, qty: c.qty + action.qty } : c,
          )
        : [...state.cart, { product: action.product, qty: action.qty }]
      return { ...state, cart }
    }
    case 'REMOVE_FROM_CART':
      return { ...state, cart: state.cart.filter((c) => c.product.id !== action.id) }
    case 'CLEAR_CART':
      return { ...state, cart: [] }
    default:
      return state
  }
}

export const ProductContext = createContext(null)

export function ProductProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  async function run(work, onResult) {
    dispatch({ type: 'LOADING' })
    try {
      const data = await work()
      onResult(data)
      return data
    } catch (err) {
      dispatch({ type: 'ERROR', error: toErrorMessage(err) })
      throw err
    }
  }

  const fetchProducts = (params) =>
    run(() => productService.listProducts(params), (d) => dispatch({ type: 'SET_PRODUCTS', products: d.products || [] }))

  const fetchProduct = (id) => productService.getProduct(id).then((d) => d.product)

  const searchProducts = (query) =>
    // Feature 008 — backend now returns `{ products, meta }` (SBERT search).
    // Tolerate both shapes so this code survives the old mock fixtures too.
    run(
      () => searchService.searchProducts(query),
      (d) => dispatch({ type: 'SET_RESULTS', results: d.products || d.results || [] }),
    )

  const addProduct = (body) =>
    run(() => productService.createProduct(body), (d) => dispatch({ type: 'UPSERT_PRODUCT', product: d.product }))

  const editProduct = (id, body) =>
    run(() => productService.updateProduct(id, body), (d) => dispatch({ type: 'UPSERT_PRODUCT', product: d.product }))

  const removeProduct = (id) =>
    run(() => productService.deleteProduct(id), () => dispatch({ type: 'REMOVE_PRODUCT', id }))

  const fetchOrders = () =>
    run(() => orderService.listOrders(), (d) => dispatch({ type: 'SET_ORDERS', orders: d.orders || [] }))

  const placeOrder = () => {
    const items = state.cart.map((c) => ({ productId: c.product.id, vendorId: c.product.vendorId, qty: c.qty }))
    return run(
      () => orderService.placeOrder(items),
      (d) => {
        dispatch({ type: 'CLEAR_CART' })
        dispatch({ type: 'SET_ORDERS', orders: [d.order, ...state.orders] })
      },
    ).then((d) => d.order)
  }

  const toggleFavorite = (product) => dispatch({ type: 'TOGGLE_FAVORITE', product })
  const isFavorite = (id) => state.favorites.some((p) => p.id === id)
  const addToCart = (product, qty = 1) => dispatch({ type: 'ADD_TO_CART', product, qty })
  const removeFromCart = (id) => dispatch({ type: 'REMOVE_FROM_CART', id })
  const clearCart = () => dispatch({ type: 'CLEAR_CART' })

  const cartTotal = state.cart.reduce((sum, c) => sum + c.product.price * c.qty, 0)
  const cartCount = state.cart.reduce((sum, c) => sum + c.qty, 0)

  const value = {
    ...state,
    cartTotal,
    cartCount,
    fetchProducts,
    fetchProduct,
    searchProducts,
    addProduct,
    editProduct,
    removeProduct,
    fetchOrders,
    placeOrder,
    toggleFavorite,
    isFavorite,
    addToCart,
    removeFromCart,
    clearCart,
  }

  return <ProductContext.Provider value={value}>{children}</ProductContext.Provider>
}
