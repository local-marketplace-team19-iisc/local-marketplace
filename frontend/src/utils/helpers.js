import { CURRENCY } from './constants'

// Presentation helpers only (C-04: no business logic).

// Format a numeric amount as ₹ with 2-decimal precision (master SPEC currency rule).
export function formatPrice(amount) {
  const n = Number(amount)
  if (Number.isNaN(n)) return `${CURRENCY}0.00`
  return `${CURRENCY}${n.toFixed(2)}`
}

// Human-readable date for order timestamps etc.
export function formatDate(value) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString()
}

// Conditional className joiner.
export function classNames(...parts) {
  return parts.filter(Boolean).join(' ')
}

// Truncate long text for cards/lists.
export function truncate(text, max = 100) {
  if (!text || text.length <= max) return text || ''
  return `${text.slice(0, max).trimEnd()}…`
}

// Promise-based delay (used by the mock layer).
export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// Lightweight unique id (sessions, message keys) — not cryptographic.
export function uid(prefix = 'id') {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

// Normalize any thrown value into a user-friendly message (AC-04).
export function toErrorMessage(err, fallback = 'Something went wrong. Please try again.') {
  if (!err) return fallback
  if (typeof err === 'string') return err
  return err.message || fallback
}
