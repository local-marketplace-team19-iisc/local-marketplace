// Mock request dispatcher (D3). Mirrors the assumed REST contract (spec.md §6) and is
// reached only when VITE_USE_MOCKS=true. Returns the same data shapes the real backend
// is expected to return, and throws ApiError on failure (same as the fetch client).

import { MOCK_DELAY_MS, ROLES, PRODUCT_CATEGORIES } from '../../utils/constants'
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

// Normalize a request body: FormData (image/extraction uploads) → plain object whose
// `image` value is a File-like with a `.name`. JSON bodies pass through.
function readBody(body) {
  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    const out = {}
    for (const [k, v] of body.entries()) out[k] = v
    return out
  }
  return body || {}
}

function fileName(f) {
  return f && f.name ? String(f.name) : ''
}

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
  if (method === 'POST' && path === '/api/search/image') return searchImage(readBody(body))

  // ---- NLP / image extraction ----
  if (method === 'POST' && path === '/api/extract/product') return extractProductFields(readBody(body))

  // ---- Chatbot ----
  if (method === 'POST' && path === '/api/chat') return chat(readBody(body))

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

// ---------- Image search (D8) ----------
// NOTE: this is NOT real vision — the mock derives a keyword from the image filename and
// reuses cheapest-first matching; with no match it returns in-stock items as "similar".
function searchImage(body) {
  const fname = fileName(body.image).toLowerCase()
  const inStock = db.products.map(withAvailability).filter((p) => p.availability)
  let results = []
  if (fname) {
    results = inStock.filter((p) => {
      const words = p.name.toLowerCase().split(/\W+/).filter(Boolean)
      return words.some((w) => fname.includes(w)) || fname.includes(p.category.toLowerCase())
    })
  }
  if (results.length === 0) results = inStock // fallback: "visually similar"
  results = [...results].sort((a, b) => a.price - b.price).slice(0, 8)
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

// ---------- Product field extraction (D5/D6) ----------
// NOTE: heuristic only (not real NLP/vision). Parses price/stock/category/name from the
// prompt; from an image, derives a candidate name from the filename.
function extractProductFields(body) {
  const prompt = (body.prompt || '').toString()
  const fname = fileName(body.image)

  let name = ''
  let price = null
  let stock = null
  let category = ''

  if (prompt) {
    const priceMatch = prompt.match(/(?:₹|rs\.?\s*)(\d+(?:\.\d{1,2})?)/i) || prompt.match(/(\d+(?:\.\d{1,2})?)\s*(?:rs|rupees|₹)/i)
    if (priceMatch) price = Number(priceMatch[1])
    const stockMatch = prompt.match(/(\d+)\s*(?:units|pcs|pieces|qty|in\s*stock|stock)/i)
    if (stockMatch) stock = Number(stockMatch[1])
    category = PRODUCT_CATEGORIES.find((c) => prompt.toLowerCase().includes(c.toLowerCase())) || ''
    name = prompt
      // numbers with an optional unit suffix (100g, 1kg, 750ml, ₹58, 30)
      .replace(/(?:₹|rs\.?\s*)?\d+(?:\.\d{1,2})?\s*(?:g|kg|gm|gms|ml|l|ltr|kgs)?\b/gi, ' ')
      .replace(/\b(units|pcs|pieces|qty|in\s*stock|stock|price|category|rupees|rs)\b/gi, ' ')
      .replace(/[,.]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
    if (category) name = name.replace(new RegExp(`\\b${category}\\b`, 'ig'), '').replace(/\s+/g, ' ').trim()
    if (!name) name = prompt.trim()
  }

  if (!name && fname) {
    name = fname
      .replace(/\.[a-z0-9]+$/i, '')
      .replace(/[-_]+/g, ' ')
      .replace(/\b\d+\b/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }

  if (!category) {
    const hay = `${name} ${fname}`.toLowerCase()
    category = PRODUCT_CATEGORIES.find((c) => hay.includes(c.toLowerCase())) || PRODUCT_CATEGORIES[0]
  }

  return {
    product: {
      name: name || 'New product',
      price,
      stock,
      category,
      description: prompt || (fname ? `Extracted from image: ${fname}` : ''),
    },
  }
}

// ---------- Chatbot handler ----------
function chat({ message, sessionId, image } = {}) {
  const text = (message || '').toString().toLowerCase().trim()
  const fname = fileName(image).toLowerCase()
  // Voice arrives already transcribed into `message`. For an image-only message, derive a
  // keyword from the filename (mock — not real vision).
  const keyword = text || fname.replace(/\.[a-z0-9]+$/i, '').replace(/[-_]+/g, ' ').trim()

  const inStock = db.products.map(withAvailability).filter((p) => p.availability)
  let listings = keyword
    ? inStock.filter((p) => p.name.toLowerCase().includes(keyword) || p.category.toLowerCase().includes(keyword))
    : []
  if (listings.length === 0 && image) listings = inStock // image fallback: "visually similar"
  listings = [...listings]
    .sort((a, b) => a.price - b.price)
    .slice(0, 5)
    .map((p) => ({ id: p.id, name: p.name, price: p.price, vendor: p.vendor, rating: p.rating, availability: p.availability }))

  const label = text ? `"${message}"` : image ? `your image (${fileName(image)})` : ''
  const reply = !text && !image
    ? 'Tell me what you are looking for and I will find nearby in-stock options.'
    : listings.length
      ? `I found ${listings.length} in-stock option(s) for ${label}, cheapest first.`
      : `Sorry, I couldn't find in-stock listings for ${label}. Try another item.`

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
