// In-memory mock dataset + token helpers (D3). Mutable for the session so vendor CRUD
// and order placement behave realistically. NOT a security model — mock only.

import { ROLES } from '../../utils/constants'

let userSeq = 2
let productSeq = 8
let orderSeq = 0

export const db = {
  // Demo accounts (documented in FRONTEND_DOCUMENTATION.md §4). Passwords are mock-only.
  users: [
    { id: 'u1', name: 'Demo Customer', email: 'customer@demo.com', password: 'demo1234', role: ROLES.CUSTOMER },
    { id: 'u2', name: 'Demo Vendor', email: 'vendor@demo.com', password: 'demo1234', role: ROLES.VENDOR, vendorId: 'v1', vendor: "Demo Vendor's Store" },
  ],
  products: [
    { id: 'p1', name: 'Organic Bananas (1 dozen)', price: 59.0, vendorId: 'v1', vendor: "Demo Vendor's Store", rating: 4.5, stock: 40, category: 'Fruits', description: 'Fresh organic bananas.' },
    { id: 'p2', name: 'Full Cream Milk 1L', price: 64.5, vendorId: 'v1', vendor: "Demo Vendor's Store", rating: 4.2, stock: 25, category: 'Dairy', description: 'Pasteurised full cream milk.' },
    { id: 'p3', name: 'Whole Wheat Bread', price: 45.0, vendorId: 'v2', vendor: 'Green Basket', rating: 4.0, stock: 18, category: 'Bakery', description: 'Soft whole wheat loaf.' },
    { id: 'p4', name: 'Tomatoes 1kg', price: 32.0, vendorId: 'v2', vendor: 'Green Basket', rating: 3.9, stock: 60, category: 'Vegetables', description: 'Farm-fresh tomatoes.' },
    { id: 'p5', name: 'Tomatoes 1kg', price: 28.5, vendorId: 'v3', vendor: 'Daily Mart', rating: 4.1, stock: 50, category: 'Vegetables', description: 'Locally sourced tomatoes.' },
    { id: 'p6', name: 'Dish Wash Liquid 500ml', price: 99.0, vendorId: 'v3', vendor: 'Daily Mart', rating: 4.4, stock: 30, category: 'Household', description: 'Lemon dishwash gel.' },
    { id: 'p7', name: 'Cola 750ml', price: 40.0, vendorId: 'v2', vendor: 'Green Basket', rating: 3.8, stock: 0, category: 'Beverages', description: 'Chilled soft drink.' },
    { id: 'p8', name: 'A4 Notebook 200 pages', price: 75.0, vendorId: 'v3', vendor: 'Daily Mart', rating: 4.6, stock: 12, category: 'Stationery', description: 'Ruled notebook.' },
  ],
  orders: [],
}

export function nextUserId() {
  userSeq += 1
  return `u${userSeq}`
}
export function nextProductId() {
  productSeq += 1
  return `p${productSeq}`
}
export function nextOrderNumber() {
  orderSeq += 1
  return `ORD-${Date.now().toString(36).toUpperCase()}-${String(orderSeq).padStart(3, '0')}`
}

// Mock token = `mock-token.<userId>`. Decodes back to the user (in-memory only).
export function makeToken(user) {
  return `mock-token.${user.id}`
}
export function parseToken(token) {
  if (!token || !token.startsWith('mock-token.')) return null
  const id = token.slice('mock-token.'.length)
  return db.users.find((u) => u.id === id) || null
}

// Strip the password before returning a user over the "wire".
export function publicUser(user) {
  if (!user) return null
  const { password: _password, ...rest } = user
  return rest
}

// availability is derived from stock — keep it consistent everywhere.
export function withAvailability(product) {
  return { ...product, availability: product.stock > 0 }
}
