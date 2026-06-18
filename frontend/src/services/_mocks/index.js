// Mock request dispatcher (D3). Mirrors the assumed REST contract (spec.md §6) and is
// reached only when VITE_USE_MOCKS=true. Returns the same data shapes the real backend
// is expected to return, and throws ApiError on failure (same as the fetch client).

import { MOCK_DELAY_MS, ROLES } from '../../utils/constants'
import { sleep } from '../../utils/helpers'
import { ApiError } from '../apiError'
import {
  db,
  nextUserId,
  nextProductId,
  nextOrderNumber,
  makeToken,
  parseToken,
  publicUser,
  withAvailability,
} from './mockData'

const PRODUCT_ID_RE = /^\/api\/products\/(.+)$/

function requireAuth(token) {
  const user = parseToken(token)
  if (!user) throw new ApiError('Authentication required.', 401)
  return user
}

function requireVendor(token) {
  const user = requireAuth(token)
  if (user.role !== ROLES.VENDOR) throw new ApiError('Vendor account required.', 403)
  return user
}

export async function mockRequest(method, path, { body, params, token } = {}) {
  await sleep(MOCK_DELAY_MS)

  // ---- Auth ----
  if (method === 'POST' && path === '/api/auth/register') return register(body)
  if (method === 'POST' && path === '/api/auth/login') return login(body)
  if (method === 'GET' && path === '/api/auth/me') {
    return { user: publicUser(requireAuth(token)) }
  }

  // ---- Products ----
  if (method === 'GET' && path === '/api/products') return listProducts(params)
  if (method === 'POST' && path === '/api/products') return createProduct(requireVendor(token), body)

  const productMatch = path.match(PRODUCT_ID_RE)
  if (productMatch) {
    const id = productMatch[1]
    if (method === 'GET') return getProduct(id)
    if (method === 'PUT') return updateProduct(requireVendor(token), id, body)
    if (method === 'DELETE') return deleteProduct(requireVendor(token), id)
  }

  // ---- Search ----
  if (method === 'GET' && path === '/api/search') return search(params)

  // ---- Chatbot ----
  if (method === 'POST' && path === '/api/chat') return chat(body)

  // ---- Orders ----
  if (method === 'GET' && path === '/api/orders') return listOrders(requireAuth(token))
  if (method === 'POST' && path === '/api/orders') return placeOrder(requireAuth(token), body)

  throw new ApiError(`No mock handler for ${method} ${path}.`, 404)
}

// ---------- Auth handlers ----------
function register({ name, email, password, role } = {}) {
  if (!name || !email || !password) throw new ApiError('Name, email and password are required.', 400)
  if (db.users.some((u) => u.email === email)) throw new ApiError('An account with this email already exists.', 409)
  const isVendor = role === ROLES.VENDOR
  const user = {
    id: nextUserId(),
    name,
    email,
    password,
    role: isVendor ? ROLES.VENDOR : ROLES.CUSTOMER,
    ...(isVendor ? { vendorId: `v-${Date.now().toString(36)}`, vendor: `${name}'s Store` } : {}),
  }
  db.users.push(user)
  return { token: makeToken(user), user: publicUser(user) }
}

function login({ email, password } = {}) {
  const user = db.users.find((u) => u.email === email && u.password === password)
  if (!user) throw new ApiError('Invalid email or password.', 401)
  return { token: makeToken(user), user: publicUser(user) }
}

// ---------- Product handlers ----------
function listProducts(params = {}) {
  const query = (params.query || '').toString().toLowerCase()
  let items = db.products.map(withAvailability)
  if (query) {
    items = items.filter(
      (p) => p.name.toLowerCase().includes(query) || p.category.toLowerCase().includes(query),
    )
  }
  return { products: items }
}

function getProduct(id) {
  const product = db.products.find((p) => p.id === id)
  if (!product) throw new ApiError('Product not found.', 404)
  return { product: withAvailability(product) }
}

function createProduct(vendor, body = {}) {
  const product = {
    id: nextProductId(),
    name: body.name,
    price: Number(body.price),
    stock: Number(body.stock),
    category: body.category,
    description: body.description || '',
    rating: 0,
    vendorId: vendor.vendorId,
    vendor: vendor.vendor,
  }
  db.products.push(product)
  return { product: withAvailability(product) }
}

function updateProduct(vendor, id, body = {}) {
  const product = db.products.find((p) => p.id === id)
  if (!product) throw new ApiError('Product not found.', 404)
  if (product.vendorId !== vendor.vendorId) throw new ApiError('You can only edit your own products.', 403)
  Object.assign(product, {
    name: body.name ?? product.name,
    price: body.price !== undefined ? Number(body.price) : product.price,
    stock: body.stock !== undefined ? Number(body.stock) : product.stock,
    category: body.category ?? product.category,
    description: body.description ?? product.description,
  })
  return { product: withAvailability(product) }
}

function deleteProduct(vendor, id) {
  const idx = db.products.findIndex((p) => p.id === id)
  if (idx === -1) throw new ApiError('Product not found.', 404)
  if (db.products[idx].vendorId !== vendor.vendorId) throw new ApiError('You can only delete your own products.', 403)
  db.products.splice(idx, 1)
  return { success: true, id }
}

// ---------- Search handler (cheapest-first per master SPEC ranking) ----------
function search(params = {}) {
  const q = (params.q || '').toString().toLowerCase()
  let results = db.products.map(withAvailability).filter((p) => p.availability)
  if (q) {
    results = results.filter(
      (p) => p.name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q),
    )
  }
  results = [...results].sort((a, b) => a.price - b.price)
  return {
    results: results.map((p) => ({
      id: p.id,
      name: p.name,
      price: p.price,
      vendor: p.vendor,
      rating: p.rating,
      availability: p.availability,
    })),
  }
}

// ---------- Chatbot handler ----------
function chat({ message, sessionId } = {}) {
  const text = (message || '').toString().toLowerCase().trim()
  const listings = db.products
    .map(withAvailability)
    .filter((p) => p.availability && (p.name.toLowerCase().includes(text) || p.category.toLowerCase().includes(text)))
    .sort((a, b) => a.price - b.price)
    .slice(0, 5)
    .map((p) => ({ id: p.id, name: p.name, price: p.price, vendor: p.vendor, rating: p.rating, availability: p.availability }))

  const reply = !text
    ? 'Tell me what you are looking for and I will find nearby in-stock options.'
    : listings.length
      ? `I found ${listings.length} in-stock option(s) for "${message}", cheapest first.`
      : `Sorry, I couldn't find in-stock listings matching "${message}". Try another item.`

  return { reply, listings, sessionId }
}

// ---------- Order handlers ----------
function listOrders(user) {
  return { orders: db.orders.filter((o) => o.userId === user.id) }
}

function placeOrder(user, { items } = {}) {
  if (!Array.isArray(items) || items.length === 0) throw new ApiError('Your cart is empty.', 400)

  const lines = []
  let total = 0
  for (const item of items) {
    const product = db.products.find((p) => p.id === item.productId)
    if (!product) throw new ApiError(`Product ${item.productId} no longer exists.`, 409)
    const qty = Number(item.qty) || 1
    if (product.stock < qty) throw new ApiError(`Only ${product.stock} of "${product.name}" left in stock.`, 409)
    product.stock -= qty // deterministic inventory decrement (master SPEC)
    const lineTotal = product.price * qty
    total += lineTotal
    lines.push({ productId: product.id, name: product.name, vendor: product.vendor, qty, price: product.price, lineTotal })
  }

  const order = {
    orderNumber: nextOrderNumber(),
    userId: user.id,
    items: lines,
    total: Number(total.toFixed(2)),
    vendors: [...new Set(lines.map((l) => l.vendor))],
    placedAt: new Date().toISOString(),
  }
  db.orders.unshift(order)
  return { order }
}
