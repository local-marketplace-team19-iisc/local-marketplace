// App-wide constants. API endpoints are env-configurable (C-05) and the mock toggle
// implements D3. No business logic lives here — only configuration values.

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const USE_MOCKS =
  String(import.meta.env.VITE_USE_MOCKS).toLowerCase() === 'true'

export const USE_AUTH_MOCKS =
  String(import.meta.env.VITE_USE_AUTH_MOCKS).toLowerCase() === 'true'

// Simulated network latency for the mock layer (ms).
export const MOCK_DELAY_MS = 200

// Currency per master SPEC (₹, 2-decimal precision) — formatting in helpers.formatPrice.
export const CURRENCY = '₹'

export const ROLES = {
  CUSTOMER: 'customer',
  VENDOR: 'vendor',
}

// Pre-defined product category enum (master SPEC §3: vendors must fit a fixed enum).
export const PRODUCT_CATEGORIES = [
  'Groceries',
  'Vegetables',
  'Fruits',
  'Dairy',
  'Bakery',
  'Beverages',
  'Household',
  'Personal Care',
  'Electronics',
  'Stationery',
]

// Assumed REST contract (spec.md §6 / FRONTEND_DOCUMENTATION.md §4). Single source for paths.
export const API_ROUTES = {
  register: '/api/auth/register',
  registerVendor: '/api/auth/register-vendor',
  login: '/api/auth/login',
  me: '/api/auth/me',
  products: '/api/products',
  product: (id) => `/api/products/${id}`,
  productsFromDescription: '/api/products/from-description',
  productsDeleteByDescription: '/api/products/delete-by-description',
  catalogCategories: '/api/catalog/categories',
  catalogSubcategories: '/api/catalog/subcategories',
  search: '/api/search',
  searchImage: '/api/search/image',
  extractProduct: '/api/extract/product',
  chat: '/api/chat',
  orders: '/api/orders',
  vendorOrders: '/api/vendor/orders',
}

// Route paths used across the app (kept in one place; see FRONTEND_DOCUMENTATION.md §3).
export const ROUTES = {
  home: '/',
  login: '/login',
  register: '/register',
  search: '/search',
  product: '/product/:id',
  chatbot: '/chat',
  favorites: '/favorites',
  orders: '/orders',
  dashboard: '/dashboard',
  vendor: '/vendor',
}
